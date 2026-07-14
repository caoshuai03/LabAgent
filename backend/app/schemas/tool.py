"""
@author: caoshuai.cs
@date: 2026-07-15 00:41
@description: Agent 工具定义、调用记录与审批请求模型
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentResumeRequest(BaseModel):
    """Agent 人工审批恢复请求。"""

    session_id: str
    interrupt_id: str
    approved: bool


class ToolDefinitionVO(BaseModel):
    """当前用户可见的工具定义。"""

    name: str
    description: str
    source: str
    risk_level: str
    read_only: bool
    requires_approval: bool
    enabled: bool


class ChatToolCallVO(BaseModel):
    """历史消息中的工具调用记录。"""

    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: str
    result_summary: str | None = None
    output_preview: str | None = None
    error_message: str | None = None
    duration_ms: int | None = None
    round: int
    risk_level: str
    created_at: datetime
