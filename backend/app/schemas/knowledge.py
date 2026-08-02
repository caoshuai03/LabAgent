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
    status: str
    source_url: str | None = None
    license: str | None = None
    task_id: int | None = None
    stage: str | None = None
    total_chunks: int | None = None
    error_message: str | None = None
    create_time: datetime | None
    update_time: datetime | None


class KbUploadTaskVO(BaseModel):
    """知识库异步上传任务返回体。"""

    task_id: int
    kb_file_id: int
    file_name: str | None
    user_id: int
    status: str
    stage: str
    file_status: str
    total_chunks: int | None
    attempt_count: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime


class KbSourceVO(BaseModel):
    """RAG 引用来源返回体——供对话结果展示引用出处，全字段蛇形。"""

    citation_id: str | None = None
    file_name: str | None
    snippet: str
    course_name: str | None = None
    chapter_name: str | None = None
    section_name: str | None = None
    score: float | None = None
