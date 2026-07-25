"""
@author: caoshuai.cs
@date: 2026-07-25
@description: 知识库异步上传任务 ORM 模型
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.knowledge_status import KbUploadTaskStage, KbUploadTaskStatus


class KbUploadTask(Base):
    """记录知识库文件异步解析、切分和向量化任务。"""

    __tablename__ = "kb_upload_task"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="任务ID")
    kb_file_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ali_oss_file.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="知识库文件ID",
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tb_user.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="任务创建用户ID",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=KbUploadTaskStatus.QUEUED.value,
        index=True,
        comment="任务状态",
    )
    stage: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=KbUploadTaskStage.QUEUED.value,
        comment="当前处理阶段",
    )
    total_chunks: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="文档切片总数")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="已执行次数")
    arq_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="ARQ 作业ID")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="失败原因")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="开始时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="完成时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )
