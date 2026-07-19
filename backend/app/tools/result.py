"""
@author: caoshuai.cs
@date: 2026-07-15 00:41
@description: Agent 工具参数脱敏、结果截断与统一返回格式
"""
import json
import re
from typing import Any

from langgraph.config import get_stream_writer

from app.core.config import settings

_SENSITIVE_KEY = re.compile(r"password|passwd|token|secret|api[_-]?key|authorization", re.IGNORECASE)
_SECRET_VALUE = re.compile(
    r"(?i)(bearer\s+[a-z0-9._-]+|sk-[a-z0-9_-]{12,}|api[_-]?key\s*[:=]\s*\S+)"
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?im)(\b[a-z0-9_.-]*(?:password|passwd|token|secret|api[_-]?key|authorization)"
    r"[a-z0-9_.-]*\s*[:=]\s*)(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s\r\n]+)"
)


def redact_value(value: Any) -> Any:
    """递归脱敏工具参数与结果。"""
    if isinstance(value, dict):
        return {
            str(key): "***" if _SENSITIVE_KEY.search(str(key)) else redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        redacted = _SECRET_ASSIGNMENT.sub(r"\1***", value)
        return _SECRET_VALUE.sub("***", redacted)
    return value


def truncate_text(value: str, limit: int | None = None) -> str:
    """截断超长工具输出。"""
    max_length = limit or settings.tool_max_output_chars
    if len(value) <= max_length:
        return value
    return f"{value[:max_length]}\n...[truncated {len(value) - max_length} chars]"


def result_envelope(
    *,
    success: bool,
    output: str = "",
    summary: str = "",
    error: str | None = None,
    error_type: str | None = None,
    status: str | None = None,
    internal: bool = False,
    duration_ms: int | None = None,
    preview_path: str | None = None,
    preview_language: str | None = None,
    preview_content: str | None = None,
) -> str:
    """构造给 ToolMessage/模型的结构化 JSON 结果。

    error_type 为可选的失败分类（如 timeout/permission/invalid_argument/exception），
    供模型判断应重试还是换路；成功时不传。
    status 用于需要保留 rejected/cancelled 等精确状态的受控结果。
    internal 标记仅供后端审计和模型自修正、无需下发前端的内部结果。
    preview_* 为可选的产物预览字段（当前仅 write_file 使用），
    其余工具不传时不会出现在结果里，对既有契约零影响。
    """
    payload = {
        "success": success,
        "output": truncate_text(str(redact_value(output))),
        "summary": truncate_text(str(redact_value(summary)), 500),
        "error": truncate_text(str(redact_value(error)), 500) if error else None,
        "duration_ms": duration_ms,
    }
    if error_type is not None:
        payload["error_type"] = error_type
    if status is not None:
        payload["status"] = status
    if internal:
        payload["internal"] = True
    if preview_path is not None:
        payload["preview_path"] = preview_path
    if preview_language is not None:
        payload["preview_language"] = preview_language
    if preview_content is not None:
        payload["preview_content"] = truncate_text(str(redact_value(preview_content)))
    return json.dumps(payload, ensure_ascii=False)


def parse_result_envelope(content: Any) -> dict[str, Any]:
    """尝试解析工具 JSON 结果，解析失败时按普通文本处理。"""
    if not isinstance(content, str):
        return {"success": True, "output": str(content), "summary": "工具执行完成"}
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {"success": not content.lower().startswith("error"), "output": content, "summary": content[:500]}
    if not isinstance(parsed, dict):
        return {"success": True, "output": content, "summary": content[:500]}
    return parsed


def safe_stream_writer():
    """获取 LangGraph custom writer；脱离图单测时返回空 writer。"""
    try:
        return get_stream_writer()
    except (KeyError, RuntimeError):
        return lambda _: None
