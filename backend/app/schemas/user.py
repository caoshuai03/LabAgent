"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 用户相关请求/响应模型
"""
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """注册请求。"""

    user_name: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    name: str | None = Field(default=None, description="姓名，为空时用用户名")
    phone: str | None = None
    sex: str | None = None


class PasswordRequest(BaseModel):
    """修改密码请求。"""

    old_password: str
    new_password: str
    confirm_password: str


class UserSaveRequest(BaseModel):
    """管理员新增用户请求。"""

    user_name: str
    name: str | None = None
    phone: str | None = None
    sex: str | None = None
    id_number: str | None = None


class UserUpdateRequest(BaseModel):
    """更新用户信息请求。"""

    id: int | None = None
    user_name: str | None = None
    name: str | None = None
    phone: str | None = None
    sex: str | None = None
    id_number: str | None = None


class UserLoginVO(BaseModel):
    """登录成功返回体。"""

    id: int
    user_name: str
    name: str
    token: str
    role: int


class UserInfoVO(BaseModel):
    """用户信息返回体（脱敏）。"""

    id: int
    name: str
    user_name: str
    role: int
