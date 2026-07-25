"""
@author: caoshuai.cs
@date: 2026-07-26 01:24
@description: 会话标题异步生成任务 ARQ 入队封装
"""

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings


async def enqueue_conversation_title(
    session_id: str,
    user_id: int,
    user_message: str,
    assistant_answer: str,
    model: str | None,
) -> str:
    """提交会话标题生成任务，同一会话仅允许一个 ARQ 作业。"""
    redis = await create_pool(
        RedisSettings.from_dsn(settings.redis_url),
        default_queue_name=settings.arq_queue_name,
    )
    job_id = f"conversation-title-{session_id}"
    try:
        job = await redis.enqueue_job(
            "process_conversation_title",
            session_id,
            user_id,
            user_message,
            assistant_answer,
            model,
            _job_id=job_id,
        )
        if job is None:
            raise RuntimeError(f"ARQ 作业已存在且无法重复入队: {job_id}")
        return job.job_id
    finally:
        await redis.aclose()
