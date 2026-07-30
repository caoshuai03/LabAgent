"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 消息业务服务——持久化用户/助手消息并按会话查询历史（含归属校验）
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessException, ErrorCode
from app.models.chat_message import ChatMessage
from app.repositories.chat_message_repository import ChatMessageRepository
from app.repositories.chat_session_repository import ChatSessionRepository
from app.repositories.tool_call_repository import ToolCallRepository
from app.schemas.chat import ChatImageVO, ChatMessageVO
from app.schemas.tool import ChatToolCallVO


class MessageService:
    """消息业务，负责消息落库与历史展示。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ChatMessageRepository(session)
        self.session_repo = ChatSessionRepository(session)

    async def save_message(
        self,
        session_id: uuid.UUID,
        user_id: int,
        role: str,
        content: str,
        sources: list[dict[str, str | float | None]] | None = None,
        reasoning: list[dict[str, str | int]] | None = None,
        images: list[dict[str, str | int]] | None = None,
    ) -> ChatMessage:
        """持久化一条消息。"""
        message = ChatMessage(
            session_id=session_id,
            user_id=user_id,
            role=role,
            content=content,
            sources=sources,
            reasoning=reasoning,
            images=images,
        )
        return await self.repo.add(message)

    async def get_messages_by_session(self, session_id: str, user_id: int) -> list[ChatMessageVO]:
        """按会话查询历史消息，先校验会话归属。"""
        try:
            sid = uuid.UUID(session_id)
        except (ValueError, AttributeError, TypeError) as exc:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "会话ID格式错误") from exc
        chat_session = await self.session_repo.get_by_id(sid)
        if chat_session is None or chat_session.deleted == 1:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "会话不存在")
        if chat_session.user_id != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权访问该会话")
        messages = await self.repo.list_by_session(sid)
        tool_call_records = await ToolCallRepository(self.session).list_by_session(sid)
        calls_by_message: dict[int, list[ChatToolCallVO]] = {}
        for record in tool_call_records:
            if record.message_id is not None and record.visible:
                calls_by_message.setdefault(record.message_id, []).append(
                    ChatToolCallVO.model_validate(record, from_attributes=True)
                )
        return [
            ChatMessageVO(
                id=m.id,
                session_id=str(m.session_id),
                role=m.role,
                content=m.content,
                images=[ChatImageVO.model_validate(image) for image in (m.images or [])],
                sources=m.sources or [],
                reasoning=m.reasoning or [],
                tool_calls=calls_by_message.get(m.id, []),
                created_at=m.created_at,
            )
            for m in messages
        ]
