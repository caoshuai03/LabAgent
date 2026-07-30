"""
@author: caoshuai.cs
@date: 2026-07-31
@description: 聊天图片签名校验、用户隔离路径与多模态内容块测试
"""
from unittest.mock import AsyncMock

import pytest

from app.core.errors import BusinessException
from app.schemas.chat import ChatImageVO
from app.services.chat_image_service import ChatImageService

_PNG_DATA = b"\x89PNG\r\n\x1a\n" + b"test-image"


def test_rejects_mismatched_image_type() -> None:
    """请求 MIME 与实际文件签名不一致时拒绝上传。"""
    with pytest.raises(BusinessException, match="图片内容与声明类型不匹配"):
        ChatImageService._validate_data(_PNG_DATA, "image/jpeg")


@pytest.mark.asyncio
async def test_rejects_mismatched_image_extension() -> None:
    """聊天请求伪造附件扩展名时拒绝进入模型链路。"""
    service = ChatImageService()
    service.storage.get_object = AsyncMock(return_value=_PNG_DATA)
    image = ChatImageVO(
        image_id="a" * 32,
        file_name="实验图.exe",
        content_type="image/png",
        size=len(_PNG_DATA),
    )

    with pytest.raises(BusinessException, match="图片扩展名与实际类型不匹配"):
        await service.validate_images(7, [image])


@pytest.mark.asyncio
async def test_builds_user_scoped_multimodal_content() -> None:
    """图片从当前用户目录读取，并转换为 LangChain 标准内容块。"""
    service = ChatImageService()
    service.storage.get_object = AsyncMock(return_value=_PNG_DATA)
    image = ChatImageVO(
        image_id="a" * 32,
        file_name="../实验图.png",
        content_type="image/png",
        size=1,
    )

    content, normalized_images = await service.build_human_content(7, "分析图片", [image])

    service.storage.get_object.assert_awaited_once_with("chat-images/7/" + "a" * 32)
    assert content[0] == {"type": "text", "text": "分析图片"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert normalized_images[0].file_name == ".._实验图.png"
    assert normalized_images[0].size == len(_PNG_DATA)
