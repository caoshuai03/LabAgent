"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 用户模块路由——注册/登录/登出/改密/用户管理，管理接口叠加管理员校验
"""
from typing import Annotated

from fastapi import APIRouter, Form, Query

from app.core.deps import AdminUser, CurrentUser, DbSession
from app.core.response import BaseResponse, PageResult, success
from app.schemas.user import (
    PasswordRequest,
    RegisterRequest,
    UserInfoVO,
    UserLoginVO,
    UserSaveRequest,
    UserUpdateRequest,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/user", tags=["user"])


@router.post("/register")
async def register(req: RegisterRequest, db: DbSession) -> BaseResponse[str]:
    """用户注册。"""
    await UserService(db).register(req)
    return success("注册成功")


@router.post("/login")
async def login(
    db: DbSession,
    user_name: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> BaseResponse[UserLoginVO]:
    """登录，表单参数 user_name/password，签发 JWT。"""
    vo = await UserService(db).login(user_name, password)
    return success(vo)


@router.post("/logout")
async def logout(current_user: CurrentUser) -> BaseResponse[str]:
    """登出（JWT 无状态，前端清除 token 即可）。"""
    return success("退出成功")


@router.post("/updatePassword")
async def update_password(req: PasswordRequest, current_user: CurrentUser, db: DbSession) -> BaseResponse[str]:
    """修改当前用户密码，用户 ID 取自 JWT。"""
    await UserService(db).update_password(current_user.id, req)
    return success("密码修改成功")


@router.post("/addUser")
async def add_user(req: UserSaveRequest, admin: AdminUser, db: DbSession) -> BaseResponse[str]:
    """管理员新增用户，默认密码 123456。"""
    await UserService(db).save_user(req, admin.id)
    return success("新增成功")


@router.get("/page")
async def page(
    admin: AdminUser,
    db: DbSession,
    name: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query()] = 1,
    page_size: Annotated[int, Query()] = 10,
) -> BaseResponse[PageResult[UserInfoVO]]:
    """管理员分页查询用户。"""
    result = await UserService(db).page_query(name, page, page_size)
    return success(result)


@router.post("/status/{status}")
async def start_or_stop(
    status: int,
    admin: AdminUser,
    db: DbSession,
    id: Annotated[int, Query()],
) -> BaseResponse[str]:
    """管理员启用/禁用账号。"""
    await UserService(db).start_or_stop(status, id)
    return success("操作成功")


@router.get("/validate")
async def validate(current_user: CurrentUser, db: DbSession) -> BaseResponse[UserInfoVO]:
    """校验 token 有效性并返回当前用户信息。"""
    info = await UserService(db).get_info(current_user.id)
    return success(info)


@router.get("/{id}")
async def get_by_id(id: int, current_user: CurrentUser, db: DbSession) -> BaseResponse[UserInfoVO]:
    """根据 ID 查询用户信息（脱敏）。"""
    info = await UserService(db).get_info(id)
    return success(info)


@router.put("/update")
async def update(req: UserUpdateRequest, admin: AdminUser, db: DbSession) -> BaseResponse[str]:
    """管理员编辑用户信息。"""
    await UserService(db).update_user(req, admin.id)
    return success("编辑成功")


@router.put("/update/info")
async def update_info(req: UserUpdateRequest, current_user: CurrentUser, db: DbSession) -> BaseResponse[str]:
    """更新当前用户信息，目标用户固定为当前登录用户。"""
    await UserService(db).update_user(req, current_user.id, target_id=current_user.id)
    return success("更新成功")
