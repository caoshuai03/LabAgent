"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 认证与用户业务服务
"""
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessException, ErrorCode
from app.core.response import PageResult
from app.core.security import create_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    PasswordRequest,
    RegisterRequest,
    UserInfoVO,
    UserLoginVO,
    UserSaveRequest,
    UserUpdateRequest,
)

# 管理员新增用户时的默认密码
DEFAULT_PASSWORD = "123456"


class UserService:
    """用户与认证业务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def register(self, req: RegisterRequest) -> None:
        """注册新用户。"""
        if await self.repo.get_by_username(req.user_name):
            raise BusinessException(ErrorCode.PARAMS_ERROR, "用户名已存在")
        user = User(
            name=req.name or req.user_name,
            user_name=req.user_name,
            password=hash_password(req.password),
            phone=req.phone,
            sex=req.sex,
            status=1,
            role=0,
            create_time=date.today(),
            update_time=date.today(),
        )
        await self.repo.add(user)

    async def login(self, user_name: str, password: str) -> UserLoginVO:
        """登录校验并签发 JWT。"""
        user = await self.repo.get_by_username(user_name)
        if user is None:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "账号不存在")
        if not verify_password(password, user.password):
            raise BusinessException(ErrorCode.PARAMS_ERROR, "密码错误")
        if user.status == 0:
            raise BusinessException(ErrorCode.FORBIDDEN_ERROR, "账号被锁定")
        token = create_token(user.id)
        return UserLoginVO(
            id=user.id,
            user_name=user.user_name,
            name=user.name,
            token=token,
            role=user.role or 0,
        )

    async def update_password(self, user_id: int, req: PasswordRequest) -> None:
        """修改当前用户密码。"""
        if req.new_password != req.confirm_password:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "两次输入的密码不一致")
        user = await self.repo.get_by_id(user_id)
        if user is None:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "账号不存在")
        if not verify_password(req.old_password, user.password):
            raise BusinessException(ErrorCode.PARAMS_ERROR, "原密码错误")
        user.password = hash_password(req.new_password)
        user.update_time = date.today()

    async def save_user(self, req: UserSaveRequest, operator_id: int) -> None:
        """管理员新增用户，默认密码 123456。"""
        if await self.repo.get_by_username(req.user_name):
            raise BusinessException(ErrorCode.PARAMS_ERROR, "用户名已存在")
        user = User(
            name=req.name or req.user_name,
            user_name=req.user_name,
            password=hash_password(DEFAULT_PASSWORD),
            phone=req.phone,
            sex=req.sex,
            id_number=req.id_number,
            status=1,
            role=0,
            create_time=date.today(),
            update_time=date.today(),
            create_user=operator_id,
            update_user=operator_id,
        )
        await self.repo.add(user)

    async def page_query(self, name: str | None, page: int, page_size: int) -> PageResult[UserInfoVO]:
        """分页查询用户（脱敏）。"""
        total, users = await self.repo.page(name, page, page_size)
        records = [
            UserInfoVO(id=u.id, name=u.name, user_name=u.user_name, role=u.role or 0) for u in users
        ]
        return PageResult(total=total, records=records)

    async def start_or_stop(self, status: int, user_id: int) -> None:
        """启用/禁用账号。"""
        user = await self.repo.get_by_id(user_id)
        if user is None:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "账号不存在")
        user.status = status

    async def get_info(self, user_id: int) -> UserInfoVO:
        """查询用户信息（脱敏）。"""
        user = await self.repo.get_by_id(user_id)
        if user is None:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "账号不存在")
        return UserInfoVO(id=user.id, name=user.name, user_name=user.user_name, role=user.role or 0)

    async def update_user(self, req: UserUpdateRequest, operator_id: int, target_id: int | None = None) -> None:
        """更新用户信息。target_id 指定时更新目标用户，否则更新 req.id。"""
        user_id = target_id if target_id is not None else req.id
        if user_id is None:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "缺少用户ID")
        user = await self.repo.get_by_id(user_id)
        if user is None:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "账号不存在")
        if req.user_name is not None:
            user.user_name = req.user_name
        if req.name is not None:
            user.name = req.name
        if req.phone is not None:
            user.phone = req.phone
        if req.sex is not None:
            user.sex = req.sex
        if req.id_number is not None:
            user.id_number = req.id_number
        user.update_time = date.today()
        user.update_user = operator_id
