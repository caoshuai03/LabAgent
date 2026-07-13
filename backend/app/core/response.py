"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 统一响应结构，对齐参考项目 BaseResponse/ResultUtils
"""
from typing import Generic, TypeVar

from pydantic import BaseModel

from app.core.errors import ErrorCode

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """统一响应体：{code, data, message}，成功时 code=0。"""

    code: int = 0
    data: T | None = None
    message: str = "ok"


def success(data: T | None = None) -> BaseResponse[T]:
    """成功响应。"""
    return BaseResponse(code=ErrorCode.SUCCESS, data=data, message="ok")


def error(error_code: ErrorCode, message: str | None = None) -> BaseResponse[None]:
    """失败响应。"""
    return BaseResponse(code=int(error_code), data=None, message=message or error_code.default_message)


class PageResult(BaseModel, Generic[T]):
    """分页结果，对齐参考项目 PageResult。"""

    total: int
    records: list[T]
