"""
@author: caoshuai.cs
@date: 2026-08-02
@description: Redis 通用缓存服务，提供异步连接复用、JSON 缓存与故障降级
"""
import json
import logging
import time
from typing import Any

from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger("labagent")
_FAILURE_COOLDOWN_SECONDS = 30


class CacheService:
    """复用异步 Redis 连接，并在缓存故障时透明回源。"""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._disabled_until = 0.0

    async def initialize(self) -> None:
        """初始化连接池并验证 Redis 可用性，失败不阻断应用启动。"""
        if self._redis is not None:
            return
        client = Redis.from_url(
            settings.redis_cache_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=settings.redis_cache_timeout_seconds,
            socket_timeout=settings.redis_cache_timeout_seconds,
        )
        self._redis = client
        try:
            await client.ping()
        except Exception:  # noqa: BLE001 - 缓存不可用必须降级到数据源
            self._mark_failure("Redis 缓存初始化失败，接口将直接回源")
            return

    async def close(self) -> None:
        """关闭 Redis 连接池。"""
        client = self._redis
        self._redis = None
        self._disabled_until = 0.0
        if client is not None:
            await client.aclose()

    async def get_json(self, key: str) -> Any | None:
        """读取 JSON 数据，未命中或 Redis 异常时返回 None。"""
        client = self._available_client()
        if client is None:
            return None
        try:
            value = await client.get(key)
            return json.loads(value) if value is not None else None
        except Exception:  # noqa: BLE001 - 缓存读取失败时回源
            self._mark_failure("Redis 缓存读取失败: key=%s", key)
            return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        """写入 JSON 数据，失败只记录告警。"""
        client = self._available_client()
        if client is None:
            return
        try:
            await client.set(
                key,
                json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                ex=ttl_seconds,
            )
        except Exception:  # noqa: BLE001 - 缓存写入失败不影响业务结果
            self._mark_failure("Redis 缓存写入失败: key=%s", key)

    async def get_version(self, key: str) -> int | None:
        """读取版本号；缓存不可用时返回 None，调用方应绕过缓存。"""
        client = self._available_client()
        if client is None:
            return None
        try:
            value = await client.get(key)
            return int(value) if value is not None else 0
        except (TypeError, ValueError):
            logger.warning("Redis 缓存版本号格式错误: key=%s", key)
            return None
        except Exception:  # noqa: BLE001 - 缓存读取失败时回源
            self._mark_failure("Redis 缓存版本号读取失败: key=%s", key)
            return None

    async def increment_version(self, key: str) -> int | None:
        """递增版本号，使旧版本缓存自然失效。"""
        client = self._available_client()
        if client is None:
            return None
        try:
            return int(await client.incr(key))
        except Exception:  # noqa: BLE001 - 失效失败由短 TTL 兜底
            self._mark_failure("Redis 缓存版本号递增失败: key=%s", key)
            return None

    async def set_version(self, key: str, version: int) -> bool:
        """在关联数据写入完成后发布新版本号。"""
        client = self._available_client()
        if client is None:
            return False
        try:
            await client.set(key, version)
            return True
        except Exception:  # noqa: BLE001 - 发布失败时其他实例继续使用旧版本
            self._mark_failure("Redis 缓存版本号发布失败: key=%s", key)
            return False

    def _available_client(self) -> Redis | None:
        """熔断冷却期间跳过 Redis，冷却结束后自动尝试恢复。"""
        if time.monotonic() < self._disabled_until:
            return None
        return self._redis

    def _mark_failure(self, message: str, *args: Any) -> None:
        """记录首次故障并短暂熔断，避免持续阻塞请求和刷日志。"""
        self._disabled_until = time.monotonic() + _FAILURE_COOLDOWN_SECONDS
        logger.warning(message, *args, exc_info=True)


cache_service = CacheService()
