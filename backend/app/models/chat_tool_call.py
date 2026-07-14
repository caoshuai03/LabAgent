"""
@author: caoshuai.cs
@date: 2026-07-15 00:41
@description: Agent 工具调用记录 ORM 模型
"""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChatToolCall(Base):
    """Agent 工具调用记录。"""

    __tablename__ = "chat_tool_call"
    __table_args__ = (
        UniqueConstraint("session_id", "tool_call_id", name="uq_chat_tool_call_session_call"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True, comment="会话ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="用户ID")
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True, comment="助手消息ID")
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="链路ID")
    tool_call_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="工具调用ID")
    interrupt_id: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="LangGraph中断ID")
    round: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="Agent轮次")
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="工具名")
    tool_source: Mapped[str] = mapped_column(String(50), nullable=False, comment="工具来源")
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, comment="风险等级")
    arguments: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, comment="脱敏参数")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", comment="执行状态")
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="结果摘要")
    output_preview: Mapped[str | None] = mapped_column(Text, nullable=True, comment="脱敏截断后的输出预览")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="开始时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="结束时间")
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="执行耗时")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False, comment="创建时间"
    )
