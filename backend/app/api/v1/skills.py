"""
@author: caoshuai.cs
@date: 2026-07-12
@description: Skills 模块路由——本阶段返回骨架，Skills 加载留第四阶段
"""
from fastapi import APIRouter

from app.core.deps import CurrentUser
from app.core.response import BaseResponse, success

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("")
async def list_skills(current_user: CurrentUser) -> BaseResponse[list[dict]]:
    """获取 Skills 列表（本阶段为空骨架）。"""
    return success([])
