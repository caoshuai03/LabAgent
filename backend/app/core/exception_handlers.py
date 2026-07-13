"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 全局异常处理器，将异常转换为统一响应结构
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import BusinessException, ErrorCode
from app.core.response import error

logger = logging.getLogger("labagent")


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。"""

    @app.exception_handler(BusinessException)
    async def handle_business_exception(_: Request, exc: BusinessException) -> JSONResponse:
        """业务异常。"""
        return JSONResponse(content=error(exc.error_code, exc.message).model_dump())

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        """请求参数校验失败。"""
        return JSONResponse(content=error(ErrorCode.PARAMS_ERROR, "请求参数错误").model_dump())

    @app.exception_handler(Exception)
    async def handle_unknown_exception(_: Request, exc: Exception) -> JSONResponse:
        """兜底异常，避免泄漏内部细节。"""
        logger.exception("未处理异常: %s", exc)
        return JSONResponse(content=error(ErrorCode.SYSTEM_ERROR, "系统内部异常").model_dump())
