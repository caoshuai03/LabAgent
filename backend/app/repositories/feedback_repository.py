"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 反馈数据访问层
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_feedback import UserFeedback


class FeedbackRepository:
    """反馈表数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, feedback: UserFeedback) -> UserFeedback:
        """新增反馈。"""
        self.session.add(feedback)
        await self.session.flush()
        return feedback
