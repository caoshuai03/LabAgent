"""
@author: caoshuai.cs
@date: 2026-08-02
@description: 知识库分页缓存键与版本失效管理
"""
from hashlib import sha256

from app.services.cache_service import cache_service

KNOWLEDGE_VERSION_KEY = "labagent:knowledge:version"


def build_knowledge_page_key(
    version: int,
    file_name: str | None,
    page: int,
    page_size: int,
) -> str:
    """构造不暴露查询内容的知识库分页缓存键。"""
    normalized_name = (file_name or "").strip()
    name_hash = sha256(normalized_name.encode("utf-8")).hexdigest()[:16]
    return f"labagent:knowledge:page:v1:{version}:{name_hash}:{page}:{page_size}"


async def invalidate_knowledge_cache() -> None:
    """递增知识库版本，旧分页缓存等待 TTL 自动清理。"""
    await cache_service.increment_version(KNOWLEDGE_VERSION_KEY)
