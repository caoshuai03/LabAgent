"""
@author: caoshuai.cs
@date: 2026-07-25
@description: 知识库异步上传任务数据访问层
"""
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_upload_task import KbUploadTask
from app.models.knowledge_status import KbUploadTaskStage, KbUploadTaskStatus


class KbUploadTaskRepository:
    """知识库上传任务数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, kb_file_id: int, user_id: int) -> KbUploadTask:
        """新增待入队任务。"""
        now = datetime.now()
        task = KbUploadTask(
            kb_file_id=kb_file_id,
            user_id=user_id,
            status=KbUploadTaskStatus.QUEUED.value,
            stage=KbUploadTaskStage.QUEUED.value,
            attempt_count=0,
            created_at=now,
            updated_at=now,
        )
        self.session.add(task)
        await self.session.flush()
        return task

    async def get_by_id(self, task_id: int, *, for_update: bool = False) -> KbUploadTask | None:
        """按 ID 查询任务，可选行锁。"""
        stmt = select(KbUploadTask).where(KbUploadTask.id == task_id)
        if for_update:
            stmt = stmt.with_for_update()
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_active(self, user_id: int | None = None) -> list[KbUploadTask]:
        """查询活动任务；传入用户 ID 时仅返回该用户任务。"""
        stmt = select(KbUploadTask).where(
            KbUploadTask.status.in_(KbUploadTaskStatus.active_values())
        )
        if user_id is not None:
            stmt = stmt.where(KbUploadTask.user_id == user_id)
        result = await self.session.execute(stmt.order_by(KbUploadTask.id.desc()))
        return list(result.scalars().all())

    async def latest_by_file_ids(self, file_ids: list[int]) -> dict[int, KbUploadTask]:
        """批量查询每个文件的最新任务，供列表恢复任务状态。"""
        if not file_ids:
            return {}
        latest_ids = (
            select(func.max(KbUploadTask.id).label("id"))
            .where(KbUploadTask.kb_file_id.in_(file_ids))
            .group_by(KbUploadTask.kb_file_id)
            .subquery()
        )
        stmt = select(KbUploadTask).join(latest_ids, KbUploadTask.id == latest_ids.c.id)
        tasks = (await self.session.execute(stmt)).scalars().all()
        return {task.kb_file_id: task for task in tasks}

    async def list_stale_processing(self, started_before: datetime) -> list[KbUploadTask]:
        """查询超过 Worker 超时时间仍在处理的任务。"""
        stmt = select(KbUploadTask).where(
            KbUploadTask.status == KbUploadTaskStatus.PROCESSING.value,
            KbUploadTask.started_at < started_before,
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_queued(self) -> list[KbUploadTask]:
        """查询待处理任务，供 Worker 启动时恢复未成功投递的任务。"""
        stmt = select(KbUploadTask).where(
            KbUploadTask.status == KbUploadTaskStatus.QUEUED.value
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def delete_by_id(self, task_id: int) -> None:
        """删除指定任务。"""
        await self.session.execute(delete(KbUploadTask).where(KbUploadTask.id == task_id))
