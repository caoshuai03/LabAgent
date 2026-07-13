"""
@author: caoshuai.cs
@date: 2026-07-12
@description: MinIO 对象存储封装。MinIO SDK 为同步库，异步接口中用线程池隔离，避免阻塞事件循环
"""
import asyncio
import io
from datetime import timedelta
from urllib.parse import urlparse

from minio import Minio

from app.core.config import settings

# 对象统一前缀，替代参考项目的 java-lab-agent-rag/
_OBJECT_PREFIX = "lab-agent-rag/"


class StorageService:
    """MinIO 存储服务，提供上传、删除、流式下载与预签名 URL。"""

    def __init__(self) -> None:
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._bucket = settings.minio_bucket

    def _ensure_bucket(self) -> None:
        """确保 bucket 存在（同步，需在线程池中调用）。"""
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    def _full_object_name(self, object_name: str) -> str:
        """补全对象前缀。"""
        return object_name if object_name.startswith(_OBJECT_PREFIX) else _OBJECT_PREFIX + object_name

    def _extract_object_name(self, url_or_name: str) -> str:
        """从完整 URL 或对象名中提取对象路径（含前缀）。"""
        parsed = urlparse(url_or_name)
        if not parsed.scheme:
            return self._full_object_name(url_or_name)
        path = parsed.path.lstrip("/")
        if path.startswith(f"{self._bucket}/"):
            path = path[len(self._bucket) + 1:]
        return path

    async def ensure_bucket(self) -> None:
        """异步确保 bucket 存在，供启动时调用。"""
        await asyncio.to_thread(self._ensure_bucket)

    async def upload(self, data: bytes, object_name: str) -> str:
        """上传字节数据，返回可访问 URL。"""
        full_name = self._full_object_name(object_name)

        def _do_upload() -> str:
            self._ensure_bucket()
            self._client.put_object(
                self._bucket,
                full_name,
                io.BytesIO(data),
                length=len(data),
            )
            scheme = "https" if settings.minio_secure else "http"
            return f"{scheme}://{settings.minio_endpoint}/{self._bucket}/{full_name}"

        return await asyncio.to_thread(_do_upload)

    async def delete(self, object_name: str) -> None:
        """删除对象。"""
        target = self._extract_object_name(object_name)
        await asyncio.to_thread(self._client.remove_object, self._bucket, target)

    async def get_object(self, object_name: str) -> bytes:
        """获取对象内容字节（一次性读入，适用于中小文件下载）。"""
        target = self._extract_object_name(object_name)

        def _do_get() -> bytes:
            response = self._client.get_object(self._bucket, target)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        return await asyncio.to_thread(_do_get)

    async def get_presigned_url(self, object_name: str, expire_minutes: int = 60) -> str:
        """生成预签名下载 URL。"""
        target = self._extract_object_name(object_name)
        return await asyncio.to_thread(
            self._client.presigned_get_object,
            self._bucket,
            target,
            timedelta(minutes=expire_minutes),
        )
