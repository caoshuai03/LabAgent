"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 反馈模块路由——提交反馈，反馈人取自 JWT
"""
from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.response import BaseResponse, success
from app.schemas.feedback import FeedbackRequest
from app.services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/submit")
async def submit(req: FeedbackRequest, current_user: CurrentUser, db: DbSession) -> BaseResponse[int]:
    """提交用户反馈，返回反馈 ID。"""
    feedback = await FeedbackService(db).submit(req, current_user.id)
    return success(feedback.id)
