"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 知识库模块路由——异步上传任务、同步更新、查询、删除与下载
"""
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.core.deps import AdminUser, CurrentUser, DbSession
from app.core.response import BaseResponse, PageResult, success
from app.schemas.knowledge import KbFileVO, KbUploadTaskVO
from app.services.knowledge_cache import invalidate_knowledge_cache
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/file/upload")
async def upload(
    admin: AdminUser,
    db: DbSession,
    file: Annotated[list[UploadFile], File()],
) -> BaseResponse[list[KbUploadTaskVO]]:
    """上传文件到 MinIO 并创建异步处理任务（管理员）。"""
    service = KnowledgeService(db)
    results: list[KbUploadTaskVO] = []
    for upload_item in file:
        data = await upload_item.read()
        vo = await service.upload_file(
            upload_item.filename or "",
            data,
            admin.id,
            upload_item.content_type,
        )
        results.append(vo)
    return success(results)


@router.get("/upload-tasks")
async def active_upload_tasks(
    current_user: CurrentUser,
    db: DbSession,
    active_only: Annotated[bool, Query()] = True,
) -> BaseResponse[list[KbUploadTaskVO]]:
    """查询活动上传任务；管理员可见全部，普通用户仅可见本人。"""
    # 当前只开放活动任务查询；保留参数以稳定前端契约并便于后续扩展历史任务。
    _ = active_only
    result = await KnowledgeService(db).list_active_tasks(
        current_user.id,
        (current_user.role or 0) == 1,
    )
    return success(result)


@router.get("/upload-tasks/{task_id}")
async def get_upload_task(
    task_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> BaseResponse[KbUploadTaskVO]:
    """查询单个上传任务，校验管理员或任务所有权。"""
    result = await KnowledgeService(db).get_task(
        task_id,
        current_user.id,
        (current_user.role or 0) == 1,
    )
    return success(result)


@router.post("/upload-tasks/{task_id}/retry")
async def retry_upload_task(
    task_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> BaseResponse[KbUploadTaskVO]:
    """重新提交失败上传任务，校验管理员或任务所有权。"""
    result = await KnowledgeService(db).retry_task(
        task_id,
        current_user.id,
        (current_user.role or 0) == 1,
    )
    return success(result)


@router.post("/file/update")
async def update(
    admin: AdminUser,
    db: DbSession,
    kb_file_id: Annotated[int, Form()],
    file: UploadFile,
) -> BaseResponse[KbFileVO]:
    """按 kb_file_id 定位已有文档做增量更新（管理员）：解析切分新文件、增量索引、替换 MinIO 对象。"""
    data = await file.read()
    vo = await KnowledgeService(db).update_file(
        kb_file_id,
        file.filename or "",
        data,
        file.content_type,
    )
    await db.commit()
    await invalidate_knowledge_cache()
    return success(vo)


@router.get("/contents")
async def query_files(
    current_user: CurrentUser,
    db: DbSession,
    file_name: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query()] = 1,
    page_size: Annotated[int, Query()] = 10,
) -> BaseResponse[PageResult[KbFileVO]]:
    """分页查询文件记录。"""
    result = await KnowledgeService(db).page_query(file_name, page, page_size)
    return success(result)


@router.delete("/delete")
async def delete_files(admin: AdminUser, db: DbSession, ids: Annotated[list[int], Query()]) -> BaseResponse[bool]:
    """删除文件记录与 MinIO 对象（管理员）。"""
    result = await KnowledgeService(db).delete_files(ids)
    await db.commit()
    if result:
        await invalidate_knowledge_cache()
    return success(result)


@router.get("/downloadFile/{id}")
async def download_file(id: int, current_user: CurrentUser, db: DbSession) -> StreamingResponse:
    """单个文件流式下载。"""
    import io

    file_name, data = await KnowledgeService(db).get_file_content(id)
    headers = {"Content-Disposition": f'attachment; filename="{file_name}"'}
    return StreamingResponse(io.BytesIO(data), media_type="application/octet-stream", headers=headers)
