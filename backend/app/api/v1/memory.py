"""
@author: caoshuai.cs
@date: 2026-07-30 00:00
@description: 当前用户 AGENTS.md 与个性化记忆接口
"""
import asyncio

from fastapi import APIRouter

from app.core.deps import CurrentUser
from app.core.errors import BusinessException, ErrorCode
from app.core.response import BaseResponse, success
from app.schemas.memory import (
    AgentsMemoryVO,
    MemorySettingsVO,
    UpdateAgentsMemoryRequest,
    UpdateMemorySettingsRequest,
    UserProfileMemoryVO,
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


@router.get("/profile")
async def get_user_profile_memory(current_user: CurrentUser) -> BaseResponse[UserProfileMemoryVO]:
    """读取当前用户的个性化信息。"""
    content, updated_at = await asyncio.to_thread(memory_service.get_profile, current_user.id)
    return success(UserProfileMemoryVO(content=content, updated_at=updated_at))


@router.get("/settings")
async def get_memory_settings(current_user: CurrentUser) -> BaseResponse[MemorySettingsVO]:
    """读取当前用户个性化记忆设置。"""
    settings = await asyncio.to_thread(memory_service.get_settings, current_user.id)
    return success(MemorySettingsVO.model_validate(settings))


@router.put("/settings")
async def update_memory_settings(
    req: UpdateMemorySettingsRequest,
    current_user: CurrentUser,
) -> BaseResponse[MemorySettingsVO]:
    """更新当前用户个性化记忆设置。"""
    settings = await asyncio.to_thread(
        memory_service.update_settings,
        current_user.id,
        long_term_memory_enabled=req.long_term_memory_enabled,
    )
    return success(MemorySettingsVO.model_validate(settings))
