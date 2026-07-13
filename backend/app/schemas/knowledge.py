"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 知识库文件相关请求/响应模型
"""
from datetime import datetime

from pydantic import BaseModel


class KbFileVO(BaseModel):
    """文件记录返回体。"""

    id: int
    file_name: str | None
    url: str | None
    create_time: datetime | None
    update_time: datetime | None
