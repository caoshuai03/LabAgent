"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 知识库模块路由——文件上传/更新/查询/删除/下载（上传/更新/删除需管理员）
"""
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.core.deps import AdminUser, CurrentUser, DbSession
from app.core.response import BaseResponse, PageResult, success
from app.schemas.knowledge import KbFileVO
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/file/upload")
async def upload(
    admin: AdminUser,
    db: DbSession,
    file: Annotated[list[UploadFile], File()],
) -> BaseResponse[list[KbFileVO]]:
    """上传文件到 MinIO 并记录（管理员）。表单字段名为 file，可携带多个。"""
    service = KnowledgeService(db)
    results: list[KbFileVO] = []
    for upload_item in file:
        data = await upload_item.read()
        vo = await service.upload_file(upload_item.filename or "", data)
        results.append(vo)
    return success(results)


@router.post("/file/update")
async def update(
    admin: AdminUser,
    db: DbSession,
    kb_file_id: Annotated[int, Form()],
    file: UploadFile,
) -> BaseResponse[KbFileVO]:
    """按 kb_file_id 定位已有文档做增量更新（管理员）：解析切分新文件、增量索引、替换 MinIO 对象。"""
    data = await file.read()
    vo = await KnowledgeService(db).update_file(kb_file_id, file.filename or "", data)
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
    return success(result)


@router.get("/downloadFile/{id}")
async def download_file(id: int, current_user: CurrentUser, db: DbSession) -> StreamingResponse:
    """单个文件流式下载。"""
    import io

    file_name, data = await KnowledgeService(db).get_file_content(id)
    headers = {"Content-Disposition": f'attachment; filename="{file_name}"'}
    return StreamingResponse(io.BytesIO(data), media_type="application/octet-stream", headers=headers)
