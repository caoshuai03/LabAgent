"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 会话业务服务——会话元数据的创建、列表、更新时间与逻辑删除（含归属校验）
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessException, ErrorCode
from app.models.chat_session import ChatSession
from app.repositories.chat_session_repository import ChatSessionRepository
from app.schemas.chat import ChatSessionVO

# 会话标题从首条用户消息截断的最大长度
_TITLE_MAX_LENGTH = 30


def _parse_session_id(session_id: str) -> uuid.UUID:
    """将字符串会话 ID 解析为 UUID，非法则抛参数异常。"""
    try:
        return uuid.UUID(session_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise BusinessException(ErrorCode.PARAMS_ERROR, "会话ID格式错误") from exc


class SessionService:
    """会话业务，负责会话元数据与展示。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ChatSessionRepository(session)

    async def get_or_create_session(
        self, session_id: str | None, user_id: int, first_message: str | None = None
    ) -> ChatSession:
        """获取已有会话（校验归属）或创建新会话；新会话标题取首条用户消息。"""
        if session_id:
            existing = await self.repo.get_by_id(_parse_session_id(session_id))
            if existing is not None and existing.deleted == 0:
                if existing.user_id != user_id:
                    raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权访问该会话")
                return existing
        title = None
        if first_message:
            title = first_message.strip()[:_TITLE_MAX_LENGTH] or None
        new_session = ChatSession(user_id=user_id, title=title)
        return await self.repo.add(new_session)

    async def list_sessions_by_user(self, user_id: int) -> list[ChatSessionVO]:
        """查询用户会话列表（未删除，按更新时间倒序）。"""
        sessions = await self.repo.list_by_user(user_id)
        return [
            ChatSessionVO(
                id=str(s.id),
                title=s.title,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in sessions
        ]

    async def get_owned_session(self, session_id: str, user_id: int) -> ChatSession:
        """获取当前用户所属的未删除会话。"""
        chat_session = await self.repo.get_by_id(_parse_session_id(session_id))
        if chat_session is None or chat_session.deleted == 1:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "会话不存在")
        if chat_session.user_id != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权访问该会话")
        return chat_session

    async def touch(self, session_id: uuid.UUID) -> None:
        """刷新会话更新时间。"""
        await self.repo.touch(session_id)

    async def delete_sessions(self, session_ids: list[str], user_id: int) -> bool:
        """逻辑删除会话（仅限归属该用户），返回是否有删除。"""
        if not session_ids:
            return False
        parsed = [_parse_session_id(sid) for sid in session_ids]
        affected = await self.repo.logical_delete(parsed, user_id)
        return affected > 0
