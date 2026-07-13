"""
@author: caoshuai.cs
@date: 2026-07-12
@description: FastAPI 依赖注入——数据库会话、当前用户、管理员校验
"""
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessException, ErrorCode
from app.core.security import parse_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    session: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """解析 JWT 并返回当前启用的用户；失败抛未登录/无权限异常。"""
    if not authorization:
        raise BusinessException(ErrorCode.NOT_LOGIN_ERROR, "未登录")
    # 兼容 "Bearer xxx" 与直接传 token 两种格式
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else authorization.strip()
    user_id = parse_token(token)
    if user_id is None:
        raise BusinessException(ErrorCode.NOT_LOGIN_ERROR, "登录已过期或无效")
    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise BusinessException(ErrorCode.NOT_LOGIN_ERROR, "用户不存在")
    if user.status == 0:
        raise BusinessException(ErrorCode.FORBIDDEN_ERROR, "账号被锁定")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(current_user: CurrentUser) -> User:
    """要求当前用户为管理员（role=1）。"""
    if (current_user.role or 0) != 1:
        raise BusinessException(ErrorCode.NO_AUTH_ERROR, "需要管理员权限")
    return current_user


AdminUser = Annotated[User, Depends(require_admin)]
