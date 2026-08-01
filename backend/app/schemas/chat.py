"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 对话相关请求/响应模型
"""
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.knowledge import KbSourceVO
from app.schemas.tool import ChatToolCallVO


class ChatImageVO(BaseModel):
    """聊天图片附件元数据，不向前端暴露存储路径。"""

    image_id: str
    file_name: str
    content_type: str
    size: int


class ChatRequest(BaseModel):
    """RAG/Agent 对话请求。userId 一律忽略，以 JWT 为准。"""

    message: str = Field(default="", max_length=100_000, description="用户消息")
    session_id: str | None = Field(default=None, description="会话ID，为空时创建新会话")
    model: str | None = Field(default=None, description="大模型名称")
    images: list[ChatImageVO] = Field(default_factory=list, max_length=10, description="聊天图片")
    skill_names: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="本轮主动激活的 Skill 名称",
    )

    @model_validator(mode="after")
    def validate_content(self) -> "ChatRequest":
        """文本与图片至少提供一种。"""
        if not self.message.strip() and not self.images:
            raise ValueError("消息和图片不能同时为空")
        return self


class HistoryRequest(BaseModel):
    """获取会话历史请求。"""

    session_id: str


class DeleteSessionRequest(BaseModel):
    """删除会话请求，支持单个或批量。"""

    session_id: str | None = None
    session_ids: list[str] | None = None


class ChatReasoningVO(BaseModel):
    """主 Agent 单轮思考过程。"""

    reasoning_id: str
    phase: str
    round_number: int
    content: str


class ChatMessageVO(BaseModel):
    """消息返回体。"""

    id: int
    session_id: str
    role: str
    content: str | None
    images: list[ChatImageVO] = Field(default_factory=list)
    skill_names: list[str] = Field(default_factory=list)
    sources: list[KbSourceVO] = Field(default_factory=list)
    reasoning: list[ChatReasoningVO] = Field(default_factory=list)
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
