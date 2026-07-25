"""
@author: caoshuai.cs
@date: 2026-07-25
@description: 知识库异步上传事务顺序与入队失败补偿测试
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.errors import BusinessException
from app.models.knowledge_status import KbFileStatus, KbUploadTaskStage, KbUploadTaskStatus
from app.services.knowledge_service import KnowledgeService


def _build_service(events: list[str]) -> tuple[KnowledgeService, SimpleNamespace, SimpleNamespace]:
    """构造不依赖外部服务的知识库服务。"""
    now = datetime.now()
    kb_file = SimpleNamespace(
        id=11,
        file_name="course.md",
        url="http://minio/labagent/course.md",
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

    async def _enqueue(_task_id: int, _attempt_count: int) -> str:
        events.append("enqueue")
        return "kb-upload-22-1"

    with patch("app.services.knowledge_service.enqueue_kb_upload", side_effect=_enqueue):
        result = await service.upload_file("course.md", b"# course", 1, "text/markdown")

    assert events == ["upload_object", "add_file", "add_task", "commit", "enqueue", "commit"]
    assert result.task_id == 22
    assert result.status == KbUploadTaskStatus.QUEUED.value


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
