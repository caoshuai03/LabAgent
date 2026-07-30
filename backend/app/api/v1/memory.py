"""
@author: caoshuai.cs
@date: 2026-07-30 00:00
@description: 当前用户 AGENTS.md 与长期记忆查询、编辑和删除接口
"""
import asyncio
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser
from app.core.errors import BusinessException, ErrorCode
from app.core.response import BaseResponse, PageResult, success
from app.schemas.memory import (
    AgentsMemoryVO,
    MemoryItemVO,
    MemoryType,
    UpdateAgentsMemoryRequest,
    UpdateMemoryItemRequest,
)
from app.services.memory_service import MemoryError, memory_service

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/agents")
async def get_agents_memory(current_user: CurrentUser) -> BaseResponse[AgentsMemoryVO]:
    """读取当前用户可编辑 AGENTS.md。"""
    content, updated_at = await asyncio.to_thread(memory_service.get_agents, current_user.id)
    return success(AgentsMemoryVO(content=content, updated_at=updated_at))


@router.put("/agents")
async def update_agents_memory(
    req: UpdateAgentsMemoryRequest,
    current_user: CurrentUser,
) -> BaseResponse[AgentsMemoryVO]:
    """更新当前用户 AGENTS.md，自动记忆流程不会调用此接口。"""
    try:
        content, updated_at = await asyncio.to_thread(
            memory_service.update_agents,
            current_user.id,
            req.content,
        )
    except MemoryError as exc:
        raise BusinessException(ErrorCode.PARAMS_ERROR, str(exc)) from exc
    return success(AgentsMemoryVO(content=content, updated_at=updated_at))


@router.get("/items")
async def list_memory_items(
    current_user: CurrentUser,
    memory_type: Annotated[MemoryType | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> BaseResponse[PageResult[MemoryItemVO]]:
    """分页查询当前用户事实、偏好和历史经验。"""
    items = await asyncio.to_thread(
        memory_service.list_items,
        current_user.id,
        memory_type=memory_type,
    )
    start = (page - 1) * page_size
    return success(PageResult(total=len(items), records=items[start : start + page_size]))


@router.put("/items/{memory_id}")
async def update_memory_item(
    memory_id: str,
    req: UpdateMemoryItemRequest,
    current_user: CurrentUser,
) -> BaseResponse[MemoryItemVO]:
    """编辑或停用当前用户一条长期记忆。"""
    try:
        item = await asyncio.to_thread(
            memory_service.update_item,
            current_user.id,
            memory_id,
            title=req.title,
            content=req.content,
            status=req.status,
        )
    except MemoryError as exc:
        raise BusinessException(ErrorCode.PARAMS_ERROR, str(exc)) from exc
    return success(item)


@router.delete("/items/{memory_id}")
async def delete_memory_item(
    memory_id: str,
    current_user: CurrentUser,
) -> BaseResponse[bool]:
    """删除当前用户一条长期记忆。"""
    deleted = await asyncio.to_thread(memory_service.delete_item, current_user.id, memory_id)
    if not deleted:
        raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "长期记忆不存在")
    return success(True)
