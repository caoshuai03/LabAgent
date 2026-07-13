"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 会话表 ORM 模型，对应 chat_session
"""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChatSession(Base):
    """对话会话表。"""

    __tablename__ = "chat_session"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="会话ID"
    )
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="用户ID")
    title: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="会话标题")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="会话摘要")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), comment="更新时间"
    )
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0, comment="逻辑删除 0-未删除 1-已删除")
