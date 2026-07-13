"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 错误码与业务异常，对齐参考项目 ErrorCode/BusinessException
"""
from enum import IntEnum


class ErrorCode(IntEnum):
    """业务错误码，数值与参考项目保持一致。"""

    SUCCESS = 0
    PARAMS_ERROR = 40000
    NOT_LOGIN_ERROR = 40100
    NO_AUTH_ERROR = 40101
    FORBIDDEN_ERROR = 40300
    NOT_FOUND_ERROR = 40400
    SYSTEM_ERROR = 50000
    OPERATION_ERROR = 50001
    UPDATE_ERROR = 50002
    DELETE_ERROR = 50004
    FILE_ERROR = 50008

    @property
    def default_message(self) -> str:
        """错误码默认提示信息。"""
        return _DEFAULT_MESSAGES.get(self, "系统内部异常")


_DEFAULT_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.SUCCESS: "ok",
    ErrorCode.PARAMS_ERROR: "请求参数错误",
    ErrorCode.NOT_LOGIN_ERROR: "未登录",
    ErrorCode.NO_AUTH_ERROR: "无权限",
    ErrorCode.FORBIDDEN_ERROR: "禁止访问",
    ErrorCode.NOT_FOUND_ERROR: "请求数据不存在",
    ErrorCode.SYSTEM_ERROR: "系统内部异常",
    ErrorCode.OPERATION_ERROR: "操作失败",
    ErrorCode.UPDATE_ERROR: "更新失败",
    ErrorCode.DELETE_ERROR: "删除失败",
    ErrorCode.FILE_ERROR: "请求文件为空",
}


class BusinessException(Exception):
    """业务异常，携带错误码与自定义信息。"""

    def __init__(self, error_code: ErrorCode, message: str | None = None) -> None:
        self.error_code = error_code
        self.message = message or error_code.default_message
        super().__init__(self.message)
