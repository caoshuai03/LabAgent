"""
@author: caoshuai.cs
@date: 2026-07-31 00:00
@description: 聊天图片的安全校验、用户隔离存储与多模态消息内容构造
"""
import base64
import re
import uuid

from minio.error import S3Error

from app.core.config import settings
from app.core.errors import BusinessException, ErrorCode
from app.schemas.chat import ChatImageVO
from app.services.storage_service import StorageService

_SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_IMAGE_EXTENSIONS = {
    "image/jpeg": {"jpg", "jpeg"},
    "image/png": {"png"},
    "image/webp": {"webp"},
}
_IMAGE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def _detect_image_type(data: bytes) -> str | None:
    """按文件签名识别允许的图片类型，禁止仅信任扩展名或请求头。"""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _safe_file_name(file_name: str) -> str:
    """移除路径和响应头控制字符，并限制展示长度。"""
    normalized = file_name.replace("/", "_").replace("\\", "_").replace("\r", "_").replace("\n", "_")
    return normalized.strip()[:255] or "image"


def _validate_file_name(file_name: str, content_type: str) -> str:
    """净化文件名并校验扩展名与实际图片类型一致。"""
    safe_name = _safe_file_name(file_name)
    extension = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    if extension not in _IMAGE_EXTENSIONS[content_type]:
        raise BusinessException(ErrorCode.PARAMS_ERROR, "图片扩展名与实际类型不匹配")
    return safe_name


class ChatImageService:
    """管理按用户隔离的聊天图片对象。"""

    def __init__(self) -> None:
        self.storage = StorageService()

    @staticmethod
    def _object_name(user_id: int, image_id: str) -> str:
        if user_id <= 0 or not _IMAGE_ID_PATTERN.fullmatch(image_id):
            raise BusinessException(ErrorCode.PARAMS_ERROR, "图片标识不合法")
        return f"chat-images/{user_id}/{image_id}"

    @staticmethod
    def _validate_data(data: bytes, declared_type: str | None = None) -> str:
        if not data:
            raise BusinessException(ErrorCode.FILE_ERROR, "图片内容为空")
        max_bytes = settings.chat_image_max_size_mb * 1024 * 1024
        if len(data) > max_bytes:
            raise BusinessException(
                ErrorCode.PARAMS_ERROR,
                f"图片超过大小上限 {settings.chat_image_max_size_mb}MB",
            )
        detected_type = _detect_image_type(data)
        if detected_type not in _SUPPORTED_IMAGE_TYPES:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "仅支持 JPEG、PNG、WebP 图片")
        normalized_type = (declared_type or "").split(";", 1)[0].strip().lower()
        if normalized_type and normalized_type not in _SUPPORTED_IMAGE_TYPES:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "图片类型不受支持")
        if normalized_type and normalized_type != detected_type:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "图片内容与声明类型不匹配")
        return detected_type

    async def upload(
        self,
        user_id: int,
        file_name: str,
        data: bytes,
        content_type: str | None,
    ) -> ChatImageVO:
        """校验并保存单张聊天图片。"""
        detected_type = self._validate_data(data, content_type)
        safe_name = _validate_file_name(file_name, detected_type)
        image_id = uuid.uuid4().hex
        await self.storage.upload(data, self._object_name(user_id, image_id))
        return ChatImageVO(
            image_id=image_id,
            file_name=safe_name,
            content_type=detected_type,
            size=len(data),
        )

    async def get(self, user_id: int, image: ChatImageVO) -> tuple[bytes, str]:
        """读取当前用户图片并重新校验实际类型。"""
        data = await self._read_object(self._object_name(user_id, image.image_id))
        detected_type = self._validate_data(data)
        return data, detected_type

    async def get_by_id(self, user_id: int, image_id: str) -> tuple[bytes, str]:
        """按图片 ID 读取当前用户对象，供历史消息展示。"""
        data = await self._read_object(self._object_name(user_id, image_id))
        return data, self._validate_data(data)

    async def _read_object(self, object_name: str) -> bytes:
        """把对象不存在转换为受控业务异常。"""
        try:
            return await self.storage.get_object(object_name)
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject"}:
                raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "图片不存在") from exc
            raise

    async def build_human_content(
        self,
        user_id: int,
        message: str,
        images: list[ChatImageVO],
    ) -> tuple[str | list[dict[str, object]], list[ChatImageVO]]:
        """重新校验附件元数据，并构造 LangChain 标准多模态内容块。"""
        if not images:
            return message, []
        if len(images) > settings.chat_image_max_count:
            raise BusinessException(
                ErrorCode.PARAMS_ERROR,
                f"单次最多上传 {settings.chat_image_max_count} 张图片",
            )
        content: list[dict[str, object]] = [
            {"type": "text", "text": message.strip() or "请分析这些图片。"}
        ]
        normalized_images: list[ChatImageVO] = []
        for image in images:
            data, content_type = await self.get(user_id, image)
            encoded = base64.b64encode(data).decode("ascii")
            normalized_images.append(
                ChatImageVO(
                    image_id=image.image_id,
                    file_name=_validate_file_name(image.file_name, content_type),
                    content_type=content_type,
                    size=len(data),
                )
            )
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{content_type};base64,{encoded}"},
                }
            )
        return content, normalized_images

    async def validate_images(
        self,
        user_id: int,
        images: list[ChatImageVO],
    ) -> list[ChatImageVO]:
        """校验当前用户图片引用并返回可信元数据，不在图状态中保存图片正文。"""
        if len(images) > settings.chat_image_max_count:
            raise BusinessException(
                ErrorCode.PARAMS_ERROR,
                f"单次最多上传 {settings.chat_image_max_count} 张图片",
            )
        normalized_images: list[ChatImageVO] = []
        for image in images:
            data, content_type = await self.get(user_id, image)
            normalized_images.append(
                ChatImageVO(
                    image_id=image.image_id,
                    file_name=_validate_file_name(image.file_name, content_type),
                    content_type=content_type,
                    size=len(data),
                )
            )
        return normalized_images
