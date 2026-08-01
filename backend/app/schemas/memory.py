"""
@author: caoshuai.cs
@date: 2026-07-30 00:00
@description: 用户长期记忆、AGENTS.md 与会话压缩请求响应模型
"""
from datetime import datetime
from pydantic import BaseModel, Field


class AgentsMemoryVO(BaseModel):
    """当前用户可编辑的 AGENTS.md。"""

    content: str
    updated_at: datetime | None = None


class UserProfileMemoryVO(BaseModel):
    """系统沉淀的用户长期 Profile。"""

    content: str
    updated_at: datetime | None = None


class MemorySettingsVO(BaseModel):
    """当前用户长期记忆设置。"""

    long_term_memory_enabled: bool = True


class UpdateAgentsMemoryRequest(BaseModel):
    """更新当前用户 AGENTS.md。"""

    content: str = Field(max_length=32_000)


class UpdateMemorySettingsRequest(BaseModel):
    """更新当前用户长期记忆设置。"""

    long_term_memory_enabled: bool


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


class MemoryExtractionResult(BaseModel):
    """后台长期记忆 Profile 更新模型的结构化输出。"""

    updated_profile: str = Field(default="", max_length=12_000)
    changed: bool = False
