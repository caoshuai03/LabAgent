"""
@author: caoshuai.cs
@date: 2026-07-15 00:41
@description: Agent 工具调用记录生命周期服务
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_tool_call import ChatToolCall
from app.repositories.tool_call_repository import ToolCallRepository
from app.schemas.tool import ChatToolCallVO


class ToolCallService:
    """工具调用记录业务服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.repo = ToolCallRepository(session)

    async def ensure_pending(
        self,
        session_id: uuid.UUID,
        user_id: int,
        trace_id: str,
        tool_call_id: str,
        tool_name: str,
        tool_source: str,
        risk_level: str,
        arguments: dict[str, Any],
        round_number: int,
    ) -> ChatToolCall:
        """幂等创建 pending 记录。"""
        existing = await self.repo.get_by_call_id(session_id, tool_call_id)
        if existing is not None:
            return existing
        return await self.repo.add(
            ChatToolCall(
                session_id=session_id,
                user_id=user_id,
                trace_id=trace_id,
                tool_call_id=tool_call_id,
                round=round_number,
                tool_name=tool_name,
                tool_source=tool_source,
                risk_level=risk_level,
                arguments=arguments,
                status="pending",
            )
        )

    async def update_status(
        self,
        session_id: uuid.UUID,
        tool_call_id: str,
        status: str,
        *,
        interrupt_id: str | None = None,
        result_summary: str | None = None,
        output_preview: str | None = None,
        error_message: str | None = None,
        duration_ms: int | None = None,
        visible: bool | None = None,
    ) -> None:
        """更新状态及执行结果。"""
        values: dict[str, Any] = {"status": status}
        if status == "running":
            values["started_at"] = datetime.now()
        if status in {"success", "failed", "timeout", "rejected", "cancelled"}:
            values["finished_at"] = datetime.now()
        if interrupt_id is not None:
            values["interrupt_id"] = interrupt_id
        if result_summary is not None:
            values["result_summary"] = result_summary
        if output_preview is not None:
            values["output_preview"] = output_preview
        if error_message is not None:
            values["error_message"] = error_message
        if duration_ms is not None:
            values["duration_ms"] = duration_ms
        if visible is not None:
            values["visible"] = visible
        await self.repo.update_by_call_id(session_id, tool_call_id, values)

    async def list_by_session(self, session_id: uuid.UUID) -> list[ChatToolCallVO]:
        """查询会话工具记录 VO。"""
        records = await self.repo.list_by_session(session_id)
        return [ChatToolCallVO.model_validate(record, from_attributes=True) for record in records]

    async def link_message(self, trace_id: str, message_id: int) -> None:
        """关联最终助手消息。"""
        await self.repo.link_message(trace_id, message_id)

    async def cancel_running(self, trace_id: str) -> None:
        """取消本次链路未完成的工具记录。"""
        await self.repo.cancel_running(trace_id, datetime.now())
