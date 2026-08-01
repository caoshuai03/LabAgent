"""
@author: caoshuai.cs
@date: 2026-08-02
@description: Skills 与知识库响应缓存命中、回源及版本键测试
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.response import PageResult
from app.schemas.knowledge import KbFileVO
from app.services.cache_service import CacheService
from app.services.knowledge_cache import build_knowledge_page_key
from app.services.knowledge_service import KnowledgeService
from app.services.skill_cache_service import SkillCacheService


def test_knowledge_page_key_hides_search_content() -> None:
    """分页缓存键不应直接暴露用户输入的文件名。"""
    key = build_knowledge_page_key(3, "敏感课程资料.md", 1, 10)

    assert "敏感课程资料" not in key
    assert key.startswith("labagent:knowledge:page:v1:3:")


@pytest.mark.asyncio
async def test_cache_failure_circuit_breaker_skips_repeated_calls() -> None:
    """Redis 故障后冷却期内应直接回源，避免每个请求重复等待。"""
    service = CacheService()
    redis = SimpleNamespace(get=AsyncMock(side_effect=TimeoutError("redis timeout")))
    service._redis = redis

    assert await service.get_json("cache-key") is None
    assert await service.get_json("cache-key") is None

    redis.get.assert_awaited_once_with("cache-key")


@pytest.mark.asyncio
async def test_knowledge_page_cache_hit_skips_database() -> None:
    """知识库分页命中缓存时不应访问 Repository。"""
    now = datetime.now()
    cached = PageResult(
        total=1,
        records=[
            KbFileVO(
                id=1,
                file_name="course.md",
                url=None,
                status="ready",
                create_time=now,
                update_time=now,
            )
        ],
    ).model_dump(mode="json")
    service = KnowledgeService.__new__(KnowledgeService)
    service.repo = SimpleNamespace(page=AsyncMock())
    service.task_repo = SimpleNamespace(latest_by_file_ids=AsyncMock())

    with (
        patch(
            "app.services.knowledge_service.cache_service.get_version",
            AsyncMock(return_value=2),
        ),
        patch(
            "app.services.knowledge_service.cache_service.get_json",
            AsyncMock(return_value=cached),
        ),
    ):
        result = await service.page_query(None, 1, 10)

    assert result.total == 1
    assert result.records[0].file_name == "course.md"
    service.repo.page.assert_not_awaited()


@pytest.mark.asyncio
async def test_skill_cache_uses_redis_snapshot_for_new_version() -> None:
    """进程发现新版本时应使用 Redis 快照更新本地一级缓存。"""
    service = SkillCacheService()
    cached = [{"name": "java-debug-helper", "description": "分析 Java 错误"}]

    with (
        patch(
            "app.services.skill_cache_service.cache_service.get_version",
            AsyncMock(return_value=5),
        ),
        patch(
            "app.services.skill_cache_service.cache_service.get_json",
            AsyncMock(return_value=cached),
        ) as get_json,
    ):
        first = await service.list_summaries()
        second = await service.list_summaries()

    assert first == second
    assert first[0].name == "java-debug-helper"
    get_json.assert_awaited_once()
