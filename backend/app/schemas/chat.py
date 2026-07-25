"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 对话相关请求/响应模型
"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.knowledge import KbSourceVO
from app.schemas.tool import ChatToolCallVO


class ChatRequest(BaseModel):
    """RAG/Agent 对话请求。userId 一律忽略，以 JWT 为准。"""

    message: str | None = Field(default="你好", description="用户消息")
    session_id: str | None = Field(default=None, description="会话ID，为空时创建新会话")
    model: str | None = Field(default=None, description="大模型名称")


class HistoryRequest(BaseModel):
    """获取会话历史请求。"""

    session_id: str


class DeleteSessionRequest(BaseModel):
    """删除会话请求，支持单个或批量。"""

    session_id: str | None = None
    session_ids: list[str] | None = None


class ChatMessageVO(BaseModel):
    """消息返回体。"""

    id: int
    session_id: str
    role: str
    content: str | None
    sources: list[KbSourceVO] = Field(default_factory=list)
    tool_calls: list[ChatToolCallVO] = Field(default_factory=list)
    created_at: datetime


class ChatSessionVO(BaseModel):
    """会话返回体。"""

    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class ConversationTitleVO(BaseModel):
    """会话标题。"""

    session_id: str
    title: str | None
