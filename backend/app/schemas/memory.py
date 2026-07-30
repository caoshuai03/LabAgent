"""
@author: caoshuai.cs
@date: 2026-07-30 00:00
@description: 用户长期记忆、AGENTS.md 与会话压缩请求响应模型
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


MemoryType = Literal["fact", "preference", "experience"]


class AgentsMemoryVO(BaseModel):
    """当前用户可编辑的 AGENTS.md。"""

    content: str
    updated_at: datetime | None = None


class UpdateAgentsMemoryRequest(BaseModel):
    """更新当前用户 AGENTS.md。"""

    content: str = Field(max_length=32_000)


class MemoryItemVO(BaseModel):
    """用户长期记忆条目。"""

    memory_id: str
    memory_type: MemoryType
    normalized_key: str | None = None
    title: str
    content: str
    source_session_id: str | None = None
    source_message_ids: list[int] = Field(default_factory=list)
    updated_by: Literal["user", "agent"] = "agent"
    status: Literal["active", "disabled"] = "active"
    created_at: datetime
    updated_at: datetime


class UpdateMemoryItemRequest(BaseModel):
    """编辑或停用一条长期记忆。"""

    title: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, max_length=8_000)
    status: Literal["active", "disabled"] | None = None


class ConversationSummary(BaseModel):
    """当前会话较早消息的结构化压缩摘要。"""

    user_goal: str = ""
    confirmed_facts: list[str] = Field(default_factory=list)
    completed_actions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)


class ConversationCompressionVO(BaseModel):
    """主动压缩结果。"""

    compressed: bool
    compressed_message_count: int = 0
    before_tokens: int
    after_tokens: int
    summary_preview: str = ""


class MemoryCandidate(BaseModel):
    """自动提取出的事实或偏好候选。"""

    normalized_key: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=2_000)
    source_message_ids: list[int] = Field(default_factory=list)


class ExperienceCandidate(BaseModel):
    """自动提取出的可复用历史经验。"""

    title: str = Field(min_length=1, max_length=200)
    problem: str = Field(min_length=1, max_length=2_000)
    solution: list[str] = Field(default_factory=list, max_length=20)
    result: str = Field(min_length=1, max_length=2_000)
    reusable_lesson: str = Field(min_length=1, max_length=2_000)
    source_message_ids: list[int] = Field(default_factory=list)


class MemoryExtractionResult(BaseModel):
    """后台长期记忆提取模型的结构化输出。"""

    facts: list[MemoryCandidate] = Field(default_factory=list, max_length=10)
    preferences: list[MemoryCandidate] = Field(default_factory=list, max_length=10)
    experience: ExperienceCandidate | None = None
