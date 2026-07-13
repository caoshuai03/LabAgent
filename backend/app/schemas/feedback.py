"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 反馈相关请求模型
"""
from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    """提交反馈请求。"""

    type: int | None = Field(default=0, description="类型 0-其它 1-BUG 2-建议 3-投诉")
    title: str | None = Field(default=None, description="标题")
    content: str = Field(..., description="反馈内容")
    priority: int | None = Field(default=1, description="优先级 0-低 1-中 2-高")
