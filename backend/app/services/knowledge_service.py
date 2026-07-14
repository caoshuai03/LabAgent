"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 知识库业务服务——上传编排（解析→切分→向量化→MinIO→落库，失败反向补偿）、更新、删除、下载、分页
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
from app.repositories.kb_file_repository import KbFileRepository
from app.schemas.knowledge import KbFileVO
from app.services import document_loader, document_splitter, rag_store
from app.services.storage_service import StorageService

logger = logging.getLogger("labagent")


def _validate_upload(file_name: str, size: int) -> str:
    """校验上传文件：非空、扩展名白名单、大小上限，返回净化后的扩展名。"""
    if not file_name:
        raise BusinessException(ErrorCode.FILE_ERROR, "文件名为空")
    if "." not in file_name:
        raise BusinessException(ErrorCode.PARAMS_ERROR, "文件缺少扩展名")
    ext = file_name.rsplit(".", 1)[-1].lower()
    if ext not in settings.allowed_extension_set:
        raise BusinessException(ErrorCode.PARAMS_ERROR, f"不支持的文件类型：{ext}")
    max_bytes = settings.upload_max_size_mb * 1024 * 1024
    if size > max_bytes:
        raise BusinessException(ErrorCode.PARAMS_ERROR, f"文件超过大小上限 {settings.upload_max_size_mb}MB")
    return ext


class KnowledgeService:
    """知识库文件业务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = KbFileRepository(session)
        self.storage = StorageService()

    async def upload_file(self, file_name: str, data: bytes) -> KbFileVO:
        """上传编排：先写记录拿 id → 解析切分 → 向量化(source_id=id) → 上传 MinIO → 回填 url，失败反向补偿。"""
        ext = _validate_upload(file_name, len(data))
        safe_name = file_name.replace("/", "_").replace("\\", "_")
        # 先写 kb_file 拿到自增 id，url 暂空——source_id 依赖该 id
        kb_file = await self.repo.add(file_name=safe_name, url="")
        source_id = str(kb_file.id)
        # 解析 + 切分失败：抛异常触发请求级回滚，此时无向量、无 MinIO 对象，天然一致
        documents = document_loader.load_documents(safe_name, data)
        chunks = document_splitter.split_documents(documents)
        if not chunks:
            raise BusinessException(ErrorCode.FILE_ERROR, f"文件切分后无有效内容：{safe_name}")
        # 向量化：同步组件用线程池隔离，失败先清理可能写入的向量再抛异常
        try:
            await asyncio.to_thread(rag_store.index_documents, chunks, source_id)
        except Exception:
            await self._safe_delete_vectors(source_id)
            raise
        # 上传 MinIO：失败清理向量后抛异常（kb_file 由请求级回滚删除）
        object_name = f"{uuid.uuid4().hex}.{ext}"
        try:
            url = await self.storage.upload(data, object_name)
        except Exception:
            await self._safe_delete_vectors(source_id)
            raise
        kb_file.url = url
        kb_file.update_time = datetime.now()
        await self.session.flush()
        return self._to_vo(kb_file)

    async def update_file(self, kb_file_id: int, file_name: str, data: bytes) -> KbFileVO:
        """按 kb_file.id 定位文档做增量更新（不全量重建）：解析切分新文件 → index 增量 → 替换 MinIO → 更新元数据。"""
        ext = _validate_upload(file_name, len(data))
        safe_name = file_name.replace("/", "_").replace("\\", "_")
        kb_file = await self.repo.get_by_id(kb_file_id)
        if kb_file is None:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "文件不存在")
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
        kb_file.update_time = datetime.now()
        await self.session.flush()
        return self._to_vo(kb_file)

    async def page_query(self, file_name: str | None, page: int, page_size: int) -> PageResult[KbFileVO]:
        """分页查询文件记录。"""
        total, files = await self.repo.page(file_name, page, page_size)
        return PageResult(total=total, records=[self._to_vo(f) for f in files])

    async def delete_files(self, ids: list[int]) -> bool:
        """删除文档：先删外部资源（向量 + MinIO 对象）再删 DB 记录，外部删除失败仅告警不阻断。"""
        if not ids:
            return False
        for file_id in ids:
            kb_file = await self.repo.get_by_id(file_id)
            if kb_file is None:
                continue
            await self._safe_delete_vectors(str(kb_file.id))
            if kb_file.url:
                await self._safe_delete_object(kb_file.url)
        affected = await self.repo.delete_by_ids(ids)
        return affected > 0

    async def get_file_content(self, file_id: int) -> tuple[str, bytes]:
        """获取文件内容用于下载，返回 (文件名, 字节)。"""
        kb_file = await self.repo.get_by_id(file_id)
        if kb_file is None or not kb_file.url:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "文件不存在")
        data = await self.storage.get_object(kb_file.url)
        return kb_file.file_name or f"file_{file_id}", data

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
    def _to_vo(kb_file: KbFile) -> KbFileVO:
        """ORM 转 VO。"""
        return KbFileVO(
            id=kb_file.id,
            file_name=kb_file.file_name,
            url=kb_file.url,
            create_time=kb_file.create_time,
            update_time=kb_file.update_time,
        )
