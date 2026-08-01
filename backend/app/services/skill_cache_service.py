"""
@author: caoshuai.cs
@date: 2026-08-02
@description: Skill 列表与详情的进程内、Redis 两级缓存
"""
import logging
from hashlib import sha256

from app.core.config import settings
from app.schemas.skill import SkillDetailVO, SkillSummaryVO
from app.services.cache_service import cache_service
from app.services.skill_service import SkillError, skill_catalog

logger = logging.getLogger("labagent")

_SKILL_VERSION_KEY = "labagent:skill:version"


class SkillCacheService:
    """按 Redis 版本同步各进程的 Skill API 快照。"""

    def __init__(self) -> None:
        self._version: int | None = None
        self._summaries: list[SkillSummaryVO] | None = None
        self._details: dict[str, SkillDetailVO] = {}

    async def list_summaries(self) -> list[SkillSummaryVO]:
        """优先返回当前版本的进程内快照，再查 Redis，最后回源目录。"""
        version = await cache_service.get_version(_SKILL_VERSION_KEY)
        if version is not None and version == self._version and self._summaries is not None:
            return self._summaries
        if version is not None:
            cached = await cache_service.get_json(self._list_key(version))
            if cached is not None:
                try:
                    summaries = [
                        SkillSummaryVO.model_validate(item)
                        for item in cached
                    ]
                    self._version = version
                    self._summaries = summaries
                    self._details = {}
                    return summaries
                except ValueError:
                    logger.warning("Skill 列表缓存内容无效，已回源")
        summaries = skill_catalog.list_summaries()
        if version is not None:
            self._version = version
            self._summaries = summaries
            self._details = {}
            await cache_service.set_json(
                self._list_key(version),
                [item.model_dump(mode="json") for item in summaries],
                settings.skill_cache_ttl_seconds,
            )
        return summaries

    async def detail(self, name: str) -> SkillDetailVO:
        """获取当前版本 Skill 详情，缓存不存在时回源进程内目录。"""
        version = await cache_service.get_version(_SKILL_VERSION_KEY)
        if version is not None and version == self._version and name in self._details:
            return self._details[name]
        if (
            version is not None
            and version == self._version
            and self._summaries is not None
            and name not in {item.name for item in self._summaries}
        ):
            raise SkillError("Skill 不存在或未通过校验")
        if version is not None:
            cached = await cache_service.get_json(self._detail_key(version, name))
            if cached is not None:
                try:
                    detail = SkillDetailVO.model_validate(cached)
                    if self._version != version:
                        self._summaries = None
                        self._details = {}
                    self._version = version
                    self._details[name] = detail
                    return detail
                except ValueError:
                    logger.warning("Skill 详情缓存内容无效，已回源: name=%s", name)
        detail = skill_catalog.detail(name)
        if version is not None:
            if self._version != version:
                self._summaries = None
                self._details = {}
            self._version = version
            self._details[name] = detail
            await cache_service.set_json(
                self._detail_key(version, name),
                detail.model_dump(mode="json"),
                settings.skill_cache_ttl_seconds,
            )
        return detail

    async def publish_current_catalog(self) -> None:
        """刷新后发布完整 API 快照，使其他实例切换到新版本。"""
        current_version = await cache_service.get_version(_SKILL_VERSION_KEY)
        version = current_version + 1 if current_version is not None else None
        summaries = skill_catalog.list_summaries()
        details: dict[str, SkillDetailVO] = {}
        for summary in summaries:
            try:
                details[summary.name] = skill_catalog.detail(summary.name)
            except SkillError:
                continue
        self._version = version
        self._summaries = summaries
        self._details = details
        if version is None:
            return
        for name, detail in details.items():
            await cache_service.set_json(
                self._detail_key(version, name),
                detail.model_dump(mode="json"),
                settings.skill_cache_ttl_seconds,
            )
        await cache_service.set_json(
            self._list_key(version),
            [item.model_dump(mode="json") for item in summaries],
            settings.skill_cache_ttl_seconds,
        )
        await cache_service.set_version(_SKILL_VERSION_KEY, version)

    @staticmethod
    def _list_key(version: int) -> str:
        return f"labagent:skill:catalog:v1:{version}"

    @staticmethod
    def _detail_key(version: int, name: str) -> str:
        name_hash = sha256(name.encode("utf-8")).hexdigest()[:24]
        return f"labagent:skill:detail:v1:{version}:{name_hash}"


skill_cache_service = SkillCacheService()
