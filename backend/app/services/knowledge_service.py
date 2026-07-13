"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 知识库业务服务——文件上传到 MinIO 并记录、分页查询、删除、下载（解析/向量化留第三阶段）
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import BusinessException, ErrorCode
from app.core.response import PageResult
from app.models.kb_file import KbFile
from app.repositories.kb_file_repository import KbFileRepository
from app.schemas.knowledge import KbFileVO
from app.services.storage_service import StorageService


def _validate_upload(file_name: str, size: int) -> str:
    """校验上传文件：非空、扩展名白名单、大小上限，返回净化后的扩展名。"""
    if not file_name:
        raise BusinessException(ErrorCode.FILE_ERROR, "文件名为空")
    if "." not in file_name:
        raise BusinessException(ErrorCode.PARAMS_ERROR, "文件缺少扩展名")
    ext = file_name.rsplit(".", 1)[-1].lower()
    if ext not in settings.allowed_extension_set:
        raise BusinessException(ErrorCode.PARAMS_ERROR, f"不支持的文件类型：{ext}")
    max_bytes = settings.upload_max_size_mb * 1024 * 1024
    if size > max_bytes:
        raise BusinessException(ErrorCode.PARAMS_ERROR, f"文件超过大小上限 {settings.upload_max_size_mb}MB")
    return ext


class KnowledgeService:
    """知识库文件业务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = KbFileRepository(session)
        self.storage = StorageService()

    async def upload_file(self, file_name: str, data: bytes) -> KbFileVO:
        """校验并上传单个文件到 MinIO，落库文件记录。"""
        ext = _validate_upload(file_name, len(data))
        # 文件名净化：仅保留基础名，加随机前缀防路径穿越与重名
        safe_name = file_name.replace("/", "_").replace("\\", "_")
        object_name = f"{uuid.uuid4().hex}.{ext}"
        url = await self.storage.upload(data, object_name)
        kb_file = await self.repo.add(file_name=safe_name, url=url)
        return self._to_vo(kb_file)

    async def page_query(self, file_name: str | None, page: int, page_size: int) -> PageResult[KbFileVO]:
        """分页查询文件记录。"""
        total, files = await self.repo.page(file_name, page, page_size)
        return PageResult(total=total, records=[self._to_vo(f) for f in files])

    async def delete_files(self, ids: list[int]) -> bool:
        """删除文件记录与对应 MinIO 对象。"""
        if not ids:
            return False
        for file_id in ids:
            kb_file = await self.repo.get_by_id(file_id)
            if kb_file and kb_file.url:
                await self.storage.delete(kb_file.url)
        affected = await self.repo.delete_by_ids(ids)
        return affected > 0

    async def get_file_content(self, file_id: int) -> tuple[str, bytes]:
        """获取文件内容用于下载，返回 (文件名, 字节)。"""
        kb_file = await self.repo.get_by_id(file_id)
        if kb_file is None or not kb_file.url:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "文件不存在")
        data = await self.storage.get_object(kb_file.url)
        return kb_file.file_name or f"file_{file_id}", data

    @staticmethod
    def _to_vo(kb_file: KbFile) -> KbFileVO:
        """ORM 转 VO。"""
        return KbFileVO(
            id=kb_file.id,
            file_name=kb_file.file_name,
            url=kb_file.url,
            create_time=kb_file.create_time,
            update_time=kb_file.update_time,
        )
