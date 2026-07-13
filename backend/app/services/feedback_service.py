"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 用户反馈业务服务——提交反馈（用户ID取自 JWT）
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessException, ErrorCode
from app.models.user_feedback import UserFeedback
from app.repositories.feedback_repository import FeedbackRepository
from app.schemas.feedback import FeedbackRequest


class FeedbackService:
    """反馈业务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = FeedbackRepository(session)

    async def submit(self, req: FeedbackRequest, user_id: int) -> UserFeedback:
        """提交反馈，反馈人取自当前登录用户。"""
        if not req.content or not req.content.strip():
            raise BusinessException(ErrorCode.PARAMS_ERROR, "反馈内容不能为空")
        feedback = UserFeedback(
            user_id=user_id,
            type=req.type if req.type is not None else 0,
            title=req.title,
            content=req.content,
            priority=req.priority if req.priority is not None else 1,
        )
        return await self.repo.add(feedback)
