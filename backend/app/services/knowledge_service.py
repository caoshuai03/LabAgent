"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 知识库业务服务——异步上传任务编排、同步更新、删除、下载与分页
"""
import asyncio
import logging
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import BusinessException, ErrorCode
from app.core.response import PageResult
from app.models.kb_file import KbFile
from app.models.kb_upload_task import KbUploadTask
from app.models.knowledge_status import KbFileStatus, KbUploadTaskStage, KbUploadTaskStatus
from app.repositories.kb_file_repository import KbFileRepository
from app.repositories.kb_upload_task_repository import KbUploadTaskRepository
from app.schemas.knowledge import KbFileVO, KbUploadTaskVO
from app.services import document_loader, document_splitter, rag_store
from app.services.kb_upload_queue import enqueue_kb_upload
from app.services.storage_service import StorageService

logger = logging.getLogger("labagent")

_ALLOWED_CONTENT_TYPES: dict[str, set[str]] = {
    "pdf": {"application/pdf", "application/octet-stream"},
    "md": {"text/markdown", "text/plain", "application/octet-stream"},
    "markdown": {"text/markdown", "text/plain", "application/octet-stream"},
    "txt": {"text/plain", "application/octet-stream"},
}


def _validate_upload(file_name: str, size: int, content_type: str | None = None) -> str:
    """校验上传文件：非空、扩展名白名单、大小上限，返回净化后的扩展名。"""
    if not file_name:
        raise BusinessException(ErrorCode.FILE_ERROR, "文件名为空")
    if size <= 0:
        raise BusinessException(ErrorCode.FILE_ERROR, "文件内容为空")
    if "." not in file_name:
        raise BusinessException(ErrorCode.PARAMS_ERROR, "文件缺少扩展名")
    ext = file_name.rsplit(".", 1)[-1].lower()
    if ext not in settings.allowed_extension_set:
        raise BusinessException(ErrorCode.PARAMS_ERROR, f"不支持的文件类型：{ext}")
    max_bytes = settings.upload_max_size_mb * 1024 * 1024
    if size > max_bytes:
        raise BusinessException(ErrorCode.PARAMS_ERROR, f"文件超过大小上限 {settings.upload_max_size_mb}MB")
    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    allowed_content_types = _ALLOWED_CONTENT_TYPES.get(ext)
    if normalized_content_type and allowed_content_types and normalized_content_type not in allowed_content_types:
        raise BusinessException(ErrorCode.PARAMS_ERROR, f"文件类型与扩展名不匹配：{normalized_content_type}")
    return ext


def _sanitize_file_name(file_name: str) -> str:
    """移除路径与响应头控制字符，保留可展示文件名。"""
    return file_name.replace("/", "_").replace("\\", "_").replace("\r", "_").replace("\n", "_")


class KnowledgeService:
    """知识库文件业务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = KbFileRepository(session)
        self.task_repo = KbUploadTaskRepository(session)
        self.storage = StorageService()

    async def upload_file(
        self,
        file_name: str,
        data: bytes,
        user_id: int,
        content_type: str | None = None,
    ) -> KbUploadTaskVO:
        """先上传 MinIO，再提交文件与任务记录，最后写入 ARQ 队列。"""
        ext = _validate_upload(file_name, len(data), content_type)
        safe_name = _sanitize_file_name(file_name)
        object_name = f"{uuid.uuid4().hex}.{ext}"
        url = await self.storage.upload(data, object_name)
        try:
            kb_file = await self.repo.add(
                file_name=safe_name,
                url=url,
                status=KbFileStatus.PENDING.value,
                upload_user_id=user_id,
            )
            task = await self.task_repo.add(kb_file.id, user_id)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            await self._safe_delete_object(url)
            raise

        try:
            job_id = await enqueue_kb_upload(task.id, task.attempt_count)
        except Exception as exc:
            logger.exception("知识库上传任务入队失败: task_id=%s", task.id)
            await self._cleanup_unqueued_upload(task.id, kb_file.id, url)
            raise BusinessException(ErrorCode.OPERATION_ERROR, "上传任务入队失败，请稍后重试") from exc

        task.arq_job_id = job_id
        task.updated_at = datetime.now()
        try:
            await self.session.commit()
        except Exception:  # noqa: BLE001 - 作业已入队，不能反向删除任务
            await self.session.rollback()
            logger.exception("ARQ 作业 ID 回写失败，任务仍可正常执行: task_id=%s", task.id)
        return self._to_task_vo(task, kb_file)

    async def update_file(
        self,
        kb_file_id: int,
        file_name: str,
        data: bytes,
        content_type: str | None = None,
    ) -> KbFileVO:
        """按 kb_file.id 定位文档做增量更新（不全量重建）：解析切分新文件 → index 增量 → 替换 MinIO → 更新元数据。"""
        ext = _validate_upload(file_name, len(data), content_type)
        safe_name = _sanitize_file_name(file_name)
        kb_file = await self.repo.get_by_id(kb_file_id)
        if kb_file is None:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "文件不存在")
        if kb_file.status in (KbFileStatus.PENDING.value, KbFileStatus.PROCESSING.value):
            raise BusinessException(ErrorCode.OPERATION_ERROR, "文件正在处理中，暂不能更新")
        source_id = str(kb_file.id)
        documents = document_loader.load_documents(safe_name, data)
        chunks = document_splitter.split_documents(documents)
        if not chunks:
            raise BusinessException(ErrorCode.FILE_ERROR, f"文件切分后无有效内容：{safe_name}")
        old_url = kb_file.url
        # 增量索引：框架按 source_id 只重写变化切片、清理旧切片
        await asyncio.to_thread(rag_store.index_documents, chunks, source_id)
        # 上传新对象后再删旧对象，避免删旧后上传失败导致文件丢失
        object_name = f"{uuid.uuid4().hex}.{ext}"
        url = await self.storage.upload(data, object_name)
        if old_url and old_url != url:
            await self._safe_delete_object(old_url)
        kb_file.file_name = safe_name
        kb_file.url = url
        kb_file.status = KbFileStatus.READY.value
        kb_file.error_message = None
        kb_file.update_time = datetime.now()
        await self.session.flush()
        return self._to_vo(kb_file)

    async def page_query(self, file_name: str | None, page: int, page_size: int) -> PageResult[KbFileVO]:
        """分页查询文件记录。"""
        total, files = await self.repo.page(file_name, page, page_size)
        latest_tasks = await self.task_repo.latest_by_file_ids([file.id for file in files])
        return PageResult(
            total=total,
            records=[self._to_vo(file, latest_tasks.get(file.id)) for file in files],
        )

    async def list_active_tasks(self, user_id: int, is_admin: bool) -> list[KbUploadTaskVO]:
        """查询活动任务；管理员可见全部，普通用户仅可见本人。"""
        tasks = await self.task_repo.list_active(None if is_admin else user_id)
        return [self._to_task_vo(task, await self.repo.get_by_id(task.kb_file_id)) for task in tasks]

    async def get_task(self, task_id: int, user_id: int, is_admin: bool) -> KbUploadTaskVO:
        """查询单个任务并校验管理员或任务所有权。"""
        task = self._check_task_access(await self.task_repo.get_by_id(task_id), user_id, is_admin)
        kb_file = await self.repo.get_by_id(task.kb_file_id)
        return self._to_task_vo(task, kb_file)

    async def retry_task(self, task_id: int, user_id: int, is_admin: bool) -> KbUploadTaskVO:
        """重新入队失败任务，并通过行锁阻止并发重复重试。"""
        task = self._check_task_access(
            await self.task_repo.get_by_id(task_id, for_update=True),
            user_id,
            is_admin,
        )
        if task.status != KbUploadTaskStatus.FAILED.value:
            raise BusinessException(ErrorCode.OPERATION_ERROR, "仅失败任务可以重试")
        kb_file = await self.repo.get_by_id(task.kb_file_id)
        if kb_file is None or not kb_file.url:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务关联文件不存在")

        previous_error = task.error_message
        now = datetime.now()
        task.status = KbUploadTaskStatus.QUEUED.value
        task.stage = KbUploadTaskStage.QUEUED.value
        task.total_chunks = None
        task.error_message = None
        task.started_at = None
        task.finished_at = None
        task.updated_at = now
        kb_file.status = KbFileStatus.PENDING.value
        kb_file.error_message = None
        kb_file.update_time = now
        await self.session.commit()

        try:
            job_id = await enqueue_kb_upload(task.id, task.attempt_count)
        except Exception as exc:
            logger.exception("知识库上传任务重试入队失败: task_id=%s", task.id)
            await self.session.rollback()
            locked_task = await self.task_repo.get_by_id(task.id, for_update=True)
            if locked_task is not None and locked_task.status == KbUploadTaskStatus.QUEUED.value:
                locked_task.status = KbUploadTaskStatus.FAILED.value
                locked_task.error_message = previous_error or "任务重试入队失败"
                locked_task.finished_at = datetime.now()
                locked_task.updated_at = datetime.now()
                kb_file = await self.repo.get_by_id(locked_task.kb_file_id)
                if kb_file is not None:
                    kb_file.status = KbFileStatus.FAILED.value
                    kb_file.error_message = locked_task.error_message
                    kb_file.update_time = datetime.now()
                await self.session.commit()
            raise BusinessException(ErrorCode.OPERATION_ERROR, "任务重试入队失败，请稍后重试") from exc

        task.arq_job_id = job_id
        task.updated_at = datetime.now()
        try:
            await self.session.commit()
        except Exception:  # noqa: BLE001 - 作业已入队，不能回退为失败
            await self.session.rollback()
            logger.exception("重试 ARQ 作业 ID 回写失败: task_id=%s", task.id)
        return self._to_task_vo(task, kb_file)

    async def delete_files(self, ids: list[int]) -> bool:
        """删除文档：先严格删除向量，再删除 MinIO，全部成功后删除数据库记录。"""
        if not ids:
            return False
        files: list[KbFile] = []
        for file_id in ids:
            kb_file = await self.repo.get_by_id(file_id)
            if kb_file is None:
                continue
            if kb_file.status in (KbFileStatus.PENDING.value, KbFileStatus.PROCESSING.value):
                raise BusinessException(ErrorCode.OPERATION_ERROR, f"文件 {file_id} 正在处理中，暂不能删除")
            files.append(kb_file)

        # 向量删除失败时立即中止，避免文件记录消失后留下仍可被检索的孤立向量。
        for kb_file in files:
            try:
                await asyncio.to_thread(rag_store.delete_by_source, str(kb_file.id))
            except Exception as exc:
                logger.exception("删除知识库文件时向量清理失败: source_id=%s", kb_file.id)
                raise BusinessException(
                    ErrorCode.OPERATION_ERROR,
                    f'文件“{kb_file.file_name or kb_file.id}”的向量清理失败，请稍后重试',
                ) from exc

        for kb_file in files:
            if kb_file.url:
                try:
                    await self.storage.delete(kb_file.url)
                except Exception as exc:
                    logger.exception("删除知识库文件时 MinIO 清理失败: file_id=%s", kb_file.id)
                    raise BusinessException(
                        ErrorCode.OPERATION_ERROR,
                        f'文件“{kb_file.file_name or kb_file.id}”的存储清理失败，请稍后重试',
                    ) from exc

        affected = await self.repo.delete_by_ids([kb_file.id for kb_file in files])
        return affected > 0

    async def get_file_content(self, file_id: int) -> tuple[str, bytes]:
        """获取文件内容用于下载，返回 (文件名, 字节)。"""
        kb_file = await self.repo.get_by_id(file_id)
        if kb_file is None or not kb_file.url:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "文件不存在")
        data = await self.storage.get_object(kb_file.url)
        return kb_file.file_name or f"file_{file_id}", data

    async def _cleanup_unqueued_upload(self, task_id: int, file_id: int, url: str) -> None:
        """补偿清理未成功入队的任务、文件记录与 MinIO 对象。"""
        await self.session.rollback()
        try:
            await self.task_repo.delete_by_id(task_id)
            await self.repo.delete_by_id(file_id)
            await self.session.commit()
        except Exception:  # noqa: BLE001 - 继续尝试清理对象并记录巡检信息
            await self.session.rollback()
            logger.exception("未入队上传的数据库记录清理失败: task_id=%s, file_id=%s", task_id, file_id)
        await self._safe_delete_object(url)

    async def _safe_delete_vectors(self, source_id: str) -> None:
        """清理指定来源的向量切片，失败仅告警便于后台巡检补偿。"""
        try:
            await asyncio.to_thread(rag_store.delete_by_source, source_id)
        except Exception:  # noqa: BLE001 - 补偿清理失败不应阻断主流程
            logger.exception("向量清理失败，需人工巡检: source_id=%s", source_id)

    async def _safe_delete_object(self, url: str) -> None:
        """清理 MinIO 对象，失败仅告警便于后台巡检补偿。"""
        try:
            await self.storage.delete(url)
        except Exception:  # noqa: BLE001 - 补偿清理失败不应阻断主流程
            logger.exception("MinIO 对象清理失败，需人工巡检: url=%s", url)

    @staticmethod
    def _to_vo(kb_file: KbFile, task: KbUploadTask | None = None) -> KbFileVO:
        """ORM 转 VO。"""
        return KbFileVO(
            id=kb_file.id,
            file_name=kb_file.file_name,
            url=kb_file.url,
            status=kb_file.status,
            task_id=task.id if task is not None else None,
            stage=task.stage if task is not None else None,
            total_chunks=task.total_chunks if task is not None else None,
            error_message=kb_file.error_message,
            create_time=kb_file.create_time,
            update_time=kb_file.update_time,
        )

    @staticmethod
    def _to_task_vo(task: KbUploadTask, kb_file: KbFile | None) -> KbUploadTaskVO:
        """任务与文件 ORM 转任务 VO。"""
        return KbUploadTaskVO(
            task_id=task.id,
            kb_file_id=task.kb_file_id,
            file_name=kb_file.file_name if kb_file is not None else None,
            user_id=task.user_id,
            status=task.status,
            stage=task.stage,
            file_status=kb_file.status if kb_file is not None else KbFileStatus.FAILED.value,
            total_chunks=task.total_chunks,
            attempt_count=task.attempt_count,
            error_message=task.error_message,
            created_at=task.created_at,
            started_at=task.started_at,
            finished_at=task.finished_at,
            updated_at=task.updated_at,
        )

    @staticmethod
    def _check_task_access(task: KbUploadTask | None, user_id: int, is_admin: bool) -> KbUploadTask:
        """校验任务存在且当前用户为管理员或任务所有者。"""
        if task is None:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "上传任务不存在")
        if not is_admin and task.user_id != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权访问该上传任务")
        return task
