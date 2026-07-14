"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 消息表 ORM 模型，对应 chat_message
"""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChatMessage(Base):
    """对话消息表（供前端历史展示与审计）。"""

    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="消息ID")
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, comment="会话ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="用户ID")
    role: Mapped[str] = mapped_column(String(20), nullable=False, comment="角色 user/assistant/system")
    content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="消息内容")
    sources: Mapped[list[dict[str, str | float | None]] | None] = mapped_column(
        JSONB, nullable=True, comment="RAG引用来源"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), comment="创建时间"
    )
