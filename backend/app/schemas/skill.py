"""
@author: caoshuai.cs
@date: 2026-07-30
@description: Skill 列表、详情与刷新结果的 API 响应模型
"""
from pydantic import BaseModel, Field


class SkillSummaryVO(BaseModel):
    """Skill 列表摘要。"""

    name: str
    description: str


class SkillDetailVO(SkillSummaryVO):
    """Skill 详情。"""

    content: str
    license: str | None = None
    compatibility: str | None = None
    allowed_tools: str | None = None
    resources: list[str] = Field(default_factory=list)


class SkillRefreshVO(BaseModel):
    """Skill 目录刷新结果。"""

    loaded_count: int
    skipped_count: int
    diagnostics: list[str] = Field(default_factory=list)
