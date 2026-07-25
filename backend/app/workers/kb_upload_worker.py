"""
@author: caoshuai.cs
@date: 2026-07-25
@description: ARQ 知识库上传 Worker，执行文档解析、切分和向量化
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from arq.connections import RedisSettings
from langchain_core.documents import Document

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.knowledge_status import KbFileStatus, KbUploadTaskStage, KbUploadTaskStatus
from app.repositories.chat_session_repository import ChatSessionRepository
from app.repositories.kb_file_repository import KbFileRepository
from app.repositories.kb_upload_task_repository import KbUploadTaskRepository
from app.services import document_loader, document_splitter, rag_store
from app.services.conversation_title_service import ConversationTitleService
from app.services.kb_upload_queue import enqueue_kb_upload
from app.services.storage_service import StorageService

logger = logging.getLogger("labagent")
_MAX_ERROR_MESSAGE_LENGTH = 2000


async def process_conversation_title(
    _ctx: dict[str, Any],
    session_id: str,
    user_id: int,
    user_message: str,
    assistant_answer: str,
    model: str | None,
) -> None:
    """在主回答结束后异步生成并安全更新会话标题。"""
    parsed_session_id = uuid.UUID(session_id)
    async with async_session_factory() as session:
        repo = ChatSessionRepository(session)
        chat_session = await repo.get_by_id(parsed_session_id)
        if (
            chat_session is None
            or chat_session.user_id != user_id
            or chat_session.deleted == 1
        ):
            return
        expected_title = chat_session.title

    try:
        title = await ConversationTitleService().generate_title(
            user_message,
            assistant_answer,
            model,
        )
        if not title:
            return
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001 - 标题任务失败只记录日志并保留兜底标题
        logger.warning("新会话标题生成失败: session_id=%s", session_id, exc_info=True)
        return

    async with async_session_factory() as session:
        repo = ChatSessionRepository(session)
        await repo.update_generated_title(
            parsed_session_id,
            user_id,
            expected_title,
            title,
        )
        await session.commit()


async def _update_stage(
    task_id: int,
    stage: KbUploadTaskStage,
    *,
    total_chunks: int | None = None,
) -> None:
    """持久化当前处理阶段，供前端轮询展示。"""
    async with async_session_factory() as session:
        task = await KbUploadTaskRepository(session).get_by_id(task_id, for_update=True)
        if task is None or task.status != KbUploadTaskStatus.PROCESSING.value:
            return
        task.stage = stage.value
        if total_chunks is not None:
            task.total_chunks = total_chunks
        task.updated_at = datetime.now()
        await session.commit()


async def _mark_failed(
    task_id: int,
    error_message: str,
    expected_statuses: tuple[str, ...] = (KbUploadTaskStatus.PROCESSING.value,),
) -> None:
    """将任务及文件标记为失败。"""
    async with async_session_factory() as session:
        task_repo = KbUploadTaskRepository(session)
        file_repo = KbFileRepository(session)
        task = await task_repo.get_by_id(task_id, for_update=True)
        if task is None or task.status not in expected_statuses:
            return
        kb_file = await file_repo.get_by_id(task.kb_file_id)
        message = error_message[:_MAX_ERROR_MESSAGE_LENGTH]
        now = datetime.now()
        task.status = KbUploadTaskStatus.FAILED.value
        task.stage = KbUploadTaskStage.FAILED.value
        task.error_message = message
        task.finished_at = now
        task.updated_at = now
        if kb_file is not None:
            kb_file.status = KbFileStatus.FAILED.value
            kb_file.error_message = message
            kb_file.update_time = now
        await session.commit()


async def _safe_delete_vectors(source_id: str) -> None:
    """清理失败任务可能写入的向量。"""
    try:
        await asyncio.to_thread(rag_store.delete_by_source, source_id)
    except Exception:  # noqa: BLE001 - 补偿失败需保留原始任务错误
        logger.exception("异步上传失败后的向量清理失败: source_id=%s", source_id)


async def _fail_with_vector_cleanup(task_id: int, source_id: str, error_message: str) -> None:
    """清理可能产生的向量并记录任务失败。"""
    await _safe_delete_vectors(source_id)
    await _mark_failed(task_id, error_message)


async def recover_stale_tasks(_ctx: dict[str, Any]) -> None:
    """Worker 启动时清理超时任务，并恢复数据库中尚未成功投递的任务。"""
    started_before = datetime.now() - timedelta(seconds=settings.arq_job_timeout_seconds)
    async with async_session_factory() as session:
        stale_tasks = await KbUploadTaskRepository(session).list_stale_processing(started_before)
        stale_task_refs = [(task.id, str(task.kb_file_id)) for task in stale_tasks]
    for task_id, source_id in stale_task_refs:
        await _fail_with_vector_cleanup(task_id, source_id, "Worker 异常退出或任务执行超时")

    async with async_session_factory() as session:
        queued_tasks = await KbUploadTaskRepository(session).list_queued()
        queued_task_refs = [(task.id, task.attempt_count) for task in queued_tasks]
    for task_id, attempt_count in queued_task_refs:
        try:
            await enqueue_kb_upload(task_id, attempt_count)
        except RuntimeError:
            # 相同 job_id 已在 Redis 中时无需重复投递。
            continue
        except Exception:  # noqa: BLE001 - 启动恢复失败后保留 queued 状态供下次恢复
            logger.exception("知识库待处理任务恢复入队失败: task_id=%s", task_id)


async def process_kb_upload(_ctx: dict[str, Any], task_id: int) -> None:
    """处理单个知识库上传任务。"""
    async with async_session_factory() as session:
        task_repo = KbUploadTaskRepository(session)
        file_repo = KbFileRepository(session)
        task = await task_repo.get_by_id(task_id, for_update=True)
        if task is None or task.status != KbUploadTaskStatus.QUEUED.value:
            return
        kb_file = await file_repo.get_by_id(task.kb_file_id)
        if kb_file is None or not kb_file.url or not kb_file.file_name:
            await session.rollback()
            await _mark_failed(
                task_id,
                "知识库文件或 MinIO 地址不存在",
                (KbUploadTaskStatus.QUEUED.value,),
            )
            return
        now = datetime.now()
        task.status = KbUploadTaskStatus.PROCESSING.value
        task.stage = KbUploadTaskStage.PARSING.value
        task.total_chunks = None
        task.attempt_count += 1
        task.started_at = now
        task.finished_at = None
        task.error_message = None
        task.updated_at = now
        kb_file.status = KbFileStatus.PROCESSING.value
        kb_file.error_message = None
        kb_file.update_time = now
        await session.commit()
        file_name = kb_file.file_name
        file_url = kb_file.url
        source_id = str(kb_file.id)

    try:
        data = await StorageService().get_object(file_url)
        documents: list[Document] = await asyncio.to_thread(
            document_loader.load_documents,
            file_name,
            data,
        )
        await _update_stage(task_id, KbUploadTaskStage.SPLITTING)
        chunks = await asyncio.to_thread(document_splitter.split_documents, documents)
        if not chunks:
            raise ValueError(f"文件切分后无有效内容：{file_name}")
        await _update_stage(task_id, KbUploadTaskStage.INDEXING, total_chunks=len(chunks))
        await asyncio.to_thread(rag_store.index_documents, chunks, source_id)
        await _update_stage(task_id, KbUploadTaskStage.FINALIZING)
    except asyncio.CancelledError:
        await asyncio.shield(
            _fail_with_vector_cleanup(task_id, source_id, "Worker 被终止或任务执行超时")
        )
        raise
    except Exception as exc:  # noqa: BLE001 - Worker 必须落库业务失败状态
        logger.exception("知识库异步上传任务执行失败: task_id=%s", task_id)
        await _fail_with_vector_cleanup(task_id, source_id, str(exc) or exc.__class__.__name__)
        return

    async with async_session_factory() as session:
        task_repo = KbUploadTaskRepository(session)
        file_repo = KbFileRepository(session)
        task = await task_repo.get_by_id(task_id, for_update=True)
        if task is None or task.status != KbUploadTaskStatus.PROCESSING.value:
            return
        kb_file = await file_repo.get_by_id(task.kb_file_id)
        now = datetime.now()
        task.status = KbUploadTaskStatus.SUCCEEDED.value
        task.stage = KbUploadTaskStage.COMPLETED.value
        task.error_message = None
        task.finished_at = now
        task.updated_at = now
        if kb_file is not None:
            kb_file.status = KbFileStatus.READY.value
            kb_file.error_message = None
            kb_file.update_time = now
        await session.commit()


class WorkerSettings:
    """ARQ Worker 配置。"""

    functions = [process_kb_upload, process_conversation_title]
    on_startup = recover_stale_tasks
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    queue_name = settings.arq_queue_name
    job_timeout = settings.arq_job_timeout_seconds
    max_jobs = settings.arq_max_jobs
    max_tries = 1
