"""
@author: caoshuai.cs
@date: 2026-07-30
@description: Skills 管理路由——查询已校验 Skill、查看详情及管理员刷新目录
"""
import asyncio

from fastapi import APIRouter

from app.core.deps import AdminUser, CurrentUser
from app.core.errors import BusinessException, ErrorCode
from app.core.response import BaseResponse, success
from app.schemas.skill import SkillDetailVO, SkillRefreshVO, SkillSummaryVO
from app.services.skill_service import SkillError, skill_catalog

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("")
async def list_skills(current_user: CurrentUser) -> BaseResponse[list[SkillSummaryVO]]:
    """获取已通过校验的 Skills 列表。"""
    return success(skill_catalog.list_summaries())


@router.post("/refresh")
async def refresh_skills(admin: AdminUser) -> BaseResponse[SkillRefreshVO]:
    """管理员重新扫描应用内置 Skills 目录。"""
    return success(await asyncio.to_thread(skill_catalog.refresh))


@router.get("/{name}")
async def get_skill_detail(name: str, current_user: CurrentUser) -> BaseResponse[SkillDetailVO]:
    """获取指定 Skill 的完整说明与资源清单。"""
    try:
        return success(skill_catalog.detail(name))
    except SkillError as exc:
        raise BusinessException(ErrorCode.NOT_FOUND_ERROR, str(exc)) from exc
