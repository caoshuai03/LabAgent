"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 会话数据访问层
"""
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.models.chat_session import ChatSession


class ChatSessionRepository:
    """会话表数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, session_id: uuid.UUID) -> ChatSession | None:
        """根据会话 ID 查询。"""
        return await self.session.get(ChatSession, session_id)

    async def add(self, chat_session: ChatSession) -> ChatSession:
        """新增会话。"""
        self.session.add(chat_session)
        await self.session.flush()
        return chat_session

    async def list_by_user(self, user_id: int) -> list[ChatSession]:
        """查询用户未删除的会话，按更新时间倒序。"""
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id, ChatSession.deleted == 0)
            .order_by(ChatSession.updated_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def touch(self, session_id: uuid.UUID) -> None:
        """更新会话的更新时间。"""
        await self.session.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(updated_at=func.current_timestamp())
        )

    async def logical_delete(self, session_ids: list[uuid.UUID], user_id: int) -> int:
        """逻辑删除会话（仅限归属该用户），返回影响行数。"""
        result = await self.session.execute(
            update(ChatSession)
            .where(ChatSession.id.in_(session_ids), ChatSession.user_id == user_id)
            .values(deleted=1)
        )
        return result.rowcount or 0
