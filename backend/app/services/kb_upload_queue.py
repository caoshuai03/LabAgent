"""
@author: caoshuai.cs
@date: 2026-07-25
@description: 知识库上传任务 ARQ 入队封装
"""
from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings


async def enqueue_kb_upload(task_id: int, attempt_count: int) -> str:
    """将已提交的知识库上传任务写入 Redis 队列。"""
    redis = await create_pool(
        RedisSettings.from_dsn(settings.redis_url),
        default_queue_name=settings.arq_queue_name,
    )
    job_id = f"kb-upload-{task_id}-{attempt_count + 1}"
    try:
        job = await redis.enqueue_job("process_kb_upload", task_id, _job_id=job_id)
        if job is None:
            raise RuntimeError(f"ARQ 作业已存在且无法重复入队: {job_id}")
        return job.job_id
    finally:
        await redis.aclose()
