"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 消息数据访问层
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage


class ChatMessageRepository:
    """消息表数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, message: ChatMessage) -> ChatMessage:
        """新增消息。"""
        self.session.add(message)
        await self.session.flush()
        return message

    async def list_by_session(self, session_id: uuid.UUID) -> list[ChatMessage]:
        """按会话查询消息，按创建时间正序。"""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())
