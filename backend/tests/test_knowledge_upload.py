"""
@author: caoshuai.cs
@date: 2026-07-25
@description: 知识库异步上传事务顺序与入队失败补偿测试
"""
import hashlib
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1.knowledge import (
    _build_content_disposition,
    _read_upload_file,
    download_file,
)
from app.core.config import settings
from app.core.errors import BusinessException
from app.models.knowledge_status import KbFileStatus, KbUploadTaskStage, KbUploadTaskStatus
from app.services.knowledge_service import KnowledgeService


def test_content_disposition_encodes_chinese_file_name() -> None:
    """中文文件名必须使用 RFC 5987 编码，避免响应头 Latin-1 编码失败。"""
    header = _build_content_disposition("自然语言处理应用.md")

    header.encode("ascii")
    assert 'filename="download.md"' in header
    assert "filename*=UTF-8''%E8%87%AA%E7%84%B6" in header


@pytest.mark.asyncio
async def test_download_file_returns_chinese_named_content() -> None:
    """中文文件名下载接口应正常返回文件内容与可编码响应头。"""
    service = SimpleNamespace(
        get_file_content=AsyncMock(
            return_value=("自然语言处理应用.md", b"# content"),
        )
    )
    with patch("app.api.v1.knowledge.KnowledgeService", return_value=service):
        response = await download_file(
            id=18,
            current_user=SimpleNamespace(id=1),
            db=SimpleNamespace(),
        )

    body = b"".join([chunk async for chunk in response.body_iterator])
    assert body == b"# content"
    assert response.headers["content-disposition"].encode("latin-1")
    assert "filename*=UTF-8''" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_read_upload_file_rejects_known_oversize_before_read() -> None:
    """已知文件大小超限时，不应再把文件内容读入应用内存。"""
    max_bytes = settings.upload_max_size_mb * 1024 * 1024
    upload = SimpleNamespace(size=max_bytes + 1, read=AsyncMock())

    with pytest.raises(BusinessException, match="文件超过大小上限"):
        await _read_upload_file(upload)

    upload.read.assert_not_awaited()


@pytest.mark.asyncio
async def test_read_upload_file_uses_configured_limit() -> None:
    """正常文件读取也应携带上限，防止未知大小的文件被无界读取。"""
    max_bytes = settings.upload_max_size_mb * 1024 * 1024
    upload = SimpleNamespace(size=3, read=AsyncMock(return_value=b"abc"))

    assert await _read_upload_file(upload) == b"abc"
    upload.read.assert_awaited_once_with(max_bytes + 1)


def _build_service(events: list[str]) -> tuple[KnowledgeService, SimpleNamespace, SimpleNamespace]:
    """构造不依赖外部服务的知识库服务。"""
    now = datetime.now()
    kb_file = SimpleNamespace(
        id=11,
        file_name="course.md",
        url="http://minio/labagent/course.md",
        content_hash=None,
        source_url=None,
        license=None,
        status=KbFileStatus.PENDING.value,
        error_message=None,
        upload_user_id=1,
        create_time=now,
        update_time=now,
    )
    task = SimpleNamespace(
        id=22,
        kb_file_id=11,
        user_id=1,
        status=KbUploadTaskStatus.QUEUED.value,
        stage=KbUploadTaskStage.QUEUED.value,
        total_chunks=None,
        attempt_count=0,
        arq_job_id=None,
        error_message=None,
        created_at=now,
        started_at=None,
        finished_at=None,
        updated_at=now,
    )

    service = KnowledgeService.__new__(KnowledgeService)
    service.session = SimpleNamespace(
        commit=AsyncMock(side_effect=lambda: events.append("commit")),
        rollback=AsyncMock(side_effect=lambda: events.append("rollback")),
    )
    service.repo = SimpleNamespace(
        get_by_content_hash=AsyncMock(return_value=None),
        add=AsyncMock(side_effect=lambda **_kwargs: (events.append("add_file"), kb_file)[1]),
        delete_by_id=AsyncMock(side_effect=lambda _file_id: events.append("delete_file")),
    )
    service.task_repo = SimpleNamespace(
        add=AsyncMock(side_effect=lambda _file_id, _user_id: (events.append("add_task"), task)[1]),
        delete_by_id=AsyncMock(side_effect=lambda _task_id: events.append("delete_task")),
    )
    service.storage = SimpleNamespace(
        upload=AsyncMock(
            side_effect=lambda _data, _object_name: (
                events.append("upload_object"),
                kb_file.url,
            )[1]
        ),
        delete=AsyncMock(side_effect=lambda _url: events.append("delete_object")),
    )
    return service, kb_file, task


@pytest.mark.asyncio
async def test_upload_commits_before_enqueue() -> None:
    """数据库提交完成后才允许写入 ARQ 队列。"""
    events: list[str] = []
    service, _, _ = _build_service(events)
    data = b"""---
course_name: "Course"
source_url: "https://example.com/course"
license: "MIT"
---
# course
"""

    async def _enqueue(_task_id: int, _attempt_count: int) -> str:
        events.append("enqueue")
        return "kb-upload-22-1"

    with patch("app.services.knowledge_service.enqueue_kb_upload", side_effect=_enqueue):
        result = await service.upload_file("course.md", data, 1, "text/markdown")

    assert events == ["upload_object", "add_file", "add_task", "commit", "enqueue", "commit"]
    assert result.task_id == 22
    assert result.status == KbUploadTaskStatus.QUEUED.value
    add_kwargs = service.repo.add.await_args.kwargs
    assert add_kwargs["content_hash"] == hashlib.sha256(data).hexdigest()
    assert add_kwargs["source_url"] == "https://example.com/course"
    assert add_kwargs["license"] == "MIT"


@pytest.mark.asyncio
async def test_upload_rejects_duplicate_content_before_storage() -> None:
    """相同内容即使文件名不同，也应在写入 MinIO 前拒绝。"""
    events: list[str] = []
    service, existing_file, _ = _build_service(events)
    existing_file.file_name = "existing.md"
    service.repo.get_by_content_hash = AsyncMock(return_value=existing_file)

    with pytest.raises(BusinessException, match="existing.md.*重复"):
        await service.upload_file("renamed.md", b"# course", 1, "text/markdown")

    service.storage.upload.assert_not_awaited()
    service.repo.add.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_enqueue_failure_cleans_database_and_object() -> None:
    """入队失败时删除已提交的任务、文件记录和 MinIO 对象。"""
    events: list[str] = []
    service, _, _ = _build_service(events)

    with (
        patch(
            "app.services.knowledge_service.enqueue_kb_upload",
            AsyncMock(side_effect=ConnectionError("redis unavailable")),
        ),
        pytest.raises(BusinessException, match="上传任务入队失败"),
    ):
        await service.upload_file("course.md", b"# course", 1, "text/markdown")

    assert events == [
        "upload_object",
        "add_file",
        "add_task",
        "commit",
        "rollback",
        "delete_task",
        "delete_file",
        "commit",
        "delete_object",
    ]


@pytest.mark.asyncio
async def test_active_tasks_batch_loads_related_files() -> None:
    """活动任务应批量查询关联文件，避免按任务逐条访问数据库。"""
    now = datetime.now()
    tasks = [
        SimpleNamespace(
            id=22,
            kb_file_id=11,
            user_id=1,
            status=KbUploadTaskStatus.QUEUED.value,
            stage=KbUploadTaskStage.QUEUED.value,
            total_chunks=None,
            attempt_count=0,
            error_message=None,
            created_at=now,
            started_at=None,
            finished_at=None,
            updated_at=now,
        )
    ]
    kb_file = SimpleNamespace(
        id=11,
        file_name="course.md",
        status=KbFileStatus.PENDING.value,
    )
    service = KnowledgeService.__new__(KnowledgeService)
    service.task_repo = SimpleNamespace(list_active=AsyncMock(return_value=tasks))
    service.repo = SimpleNamespace(get_by_ids=AsyncMock(return_value={11: kb_file}))

    result = await service.list_active_tasks(user_id=1, is_admin=False)

    service.repo.get_by_ids.assert_awaited_once_with([11])
    assert result[0].file_name == "course.md"
