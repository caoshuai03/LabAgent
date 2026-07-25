"""
@author: caoshuai.cs
@date: 2026-07-25
@description: 知识库文件与异步上传任务状态枚举
"""
from enum import StrEnum


class KbFileStatus(StrEnum):
    """知识库文件处理状态。"""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class KbUploadTaskStatus(StrEnum):
    """知识库异步上传任务状态。"""

    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

    @classmethod
    def active_values(cls) -> tuple[str, str]:
        """返回活动任务状态字符串。"""
        return cls.QUEUED.value, cls.PROCESSING.value


class KbUploadTaskStage(StrEnum):
    """知识库异步上传任务处理阶段。"""

    QUEUED = "queued"
    PARSING = "parsing"
    SPLITTING = "splitting"
    INDEXING = "indexing"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
