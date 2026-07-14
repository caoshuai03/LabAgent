"""
@author: caoshuai.cs
@date: 2026-07-15 00:41
@description: Agent 工具调用记录数据访问层
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_tool_call import ChatToolCall


class ToolCallRepository:
    """工具调用记录数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_call_id(self, session_id: uuid.UUID, tool_call_id: str) -> ChatToolCall | None:
        """按会话和工具调用 ID 查询。"""
        stmt = select(ChatToolCall).where(
            ChatToolCall.session_id == session_id,
            ChatToolCall.tool_call_id == tool_call_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add(self, record: ChatToolCall) -> ChatToolCall:
        """新增工具调用记录。"""
        self.session.add(record)
        await self.session.flush()
        return record

    async def update_by_call_id(
        self, session_id: uuid.UUID, tool_call_id: str, values: dict[str, Any]
    ) -> None:
        """更新工具调用状态。"""
        await self.session.execute(
            update(ChatToolCall)
            .where(
                ChatToolCall.session_id == session_id,
                ChatToolCall.tool_call_id == tool_call_id,
            )
            .values(**values)
        )

    async def list_by_session(self, session_id: uuid.UUID) -> list[ChatToolCall]:
        """按会话查询工具调用记录。"""
        stmt = (
            select(ChatToolCall)
            .where(ChatToolCall.session_id == session_id)
            .order_by(ChatToolCall.created_at.asc(), ChatToolCall.id.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def link_message(self, trace_id: str, message_id: int) -> None:
        """将本次链路的工具记录关联到最终助手消息。"""
        await self.session.execute(
            update(ChatToolCall)
            .where(ChatToolCall.trace_id == trace_id, ChatToolCall.message_id.is_(None))
            .values(message_id=message_id)
        )

    async def cancel_running(self, trace_id: str, finished_at: datetime) -> None:
        """将本次链路未完成的调用标记为已取消。"""
        await self.session.execute(
            update(ChatToolCall)
            .where(
                ChatToolCall.trace_id == trace_id,
                ChatToolCall.status.in_(["pending", "pending_approval", "running"]),
            )
            .values(status="cancelled", finished_at=finished_at)
        )
