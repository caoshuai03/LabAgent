"""
@author: caoshuai.cs
@date: 2026-07-15 00:41
@description: LangChain FileManagementToolkit 文件工具适配（收敛为可靠写入工具 write_file，其余文件操作统一走 execute_shell）
"""
import asyncio
import logging
import time
from pathlib import Path
from typing import Annotated, Any

from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState

from app.core.config import settings
from app.tools.policy import tool_policy
from app.tools.result import result_envelope, safe_stream_writer, truncate_text
from app.tools.workspace import WorkspaceError, workspace_manager

logger = logging.getLogger("labagent")

# 常见文本产物的语法高亮语言，供前端整文件预览（非 diff）渲染
_PREVIEW_LANGUAGES: dict[str, str] = {
    ".py": "python", ".java": "java", ".js": "javascript", ".ts": "typescript",
    ".jsx": "javascript", ".tsx": "typescript", ".vue": "vue", ".json": "json",
    ".md": "markdown", ".markdown": "markdown", ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "scss", ".xml": "xml", ".yaml": "yaml", ".yml": "yaml",
    ".sh": "bash", ".sql": "sql", ".c": "c", ".cpp": "cpp", ".h": "c", ".go": "go",
    ".rs": "rust", ".txt": "text", ".log": "text", ".csv": "text",
}


def preview_language_for(file_path: str) -> str:
    """按扩展名推断整文件预览的语言，未知类型回退为 text。"""
    return _PREVIEW_LANGUAGES.get(Path(file_path).suffix.lower(), "text")


def _build_write_preview(workspace: Path, file_path: str) -> tuple[str | None, str]:
    """读取刚写入的文件正文用于整文件预览；二进制或过大文件返回空正文。"""
    language = preview_language_for(file_path)
    try:
        target = workspace_manager.validate_relative_path(workspace, file_path, allow_missing=False)
        workspace_manager.validate_file_size(target, settings.tool_max_output_chars)
        content = target.read_text(encoding="utf-8")
    except (WorkspaceError, OSError, UnicodeDecodeError):
        return None, language
    return content, language


def _workspace_from_state(state: dict[str, Any]) -> Path:
    """从 Graph State 获取并复核当前工作区。"""
    workspace = workspace_manager.ensure_workspace(int(state["user_id"]), str(state["session_id"]))
    state_workspace = Path(str(state.get("workspace_path", workspace))).resolve()
    if state_workspace != workspace:
        raise WorkspaceError("工作区上下文不匹配")
    return workspace


async def _invoke_file_tool(
    tool_name: str,
    arguments: dict[str, Any],
    state: dict[str, Any],
    tool_call_id: str,
) -> str:
    """安全校验后委托给 FileManagementToolkit。"""
    started = time.monotonic()
    writer = safe_stream_writer()
    try:
        workspace = _workspace_from_state(state)
        decision = tool_policy.evaluate(
            tool_name,
            arguments,
            workspace=workspace,
        )
        if not decision.allowed:
            raise WorkspaceError(decision.message)

        if tool_name == "write_file" and len(str(arguments.get("text", ""))) > settings.tool_max_write_chars:
            raise WorkspaceError("写入内容超出长度限制")

        writer({
            "tool_event": {
                "event_type": "status",
                "payload": {
                    "stage": "tool_running",
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                },
            }
        })
        target_tool = FileManagementToolkit(
            root_dir=str(workspace), selected_tools=[tool_name]
        ).get_tools()[0]
        async with asyncio.timeout(settings.tool_timeout_seconds):
            output = str(await target_tool.ainvoke(arguments))
        output = truncate_text(output)
        success = not output.lower().startswith("error:")
        duration_ms = int((time.monotonic() - started) * 1000)
        path = arguments.get("file_path") or "."
        summary = f"已写入文件 {path}" if success else truncate_text(output, 300)
        preview_path: str | None = None
        preview_language: str | None = None
        preview_content: str | None = None
        if success and tool_name == "write_file":
            preview_path = str(path)
            preview_content, preview_language = _build_write_preview(workspace, str(path))
        writer({
            "tool_event": {
                "event_type": "status",
                "payload": {
                    "stage": "tool_done" if success else "tool_failed",
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "success": success,
                    "duration_ms": duration_ms,
                },
            }
        })
        return result_envelope(
            success=success,
            output=output if success else "",
            summary=summary,
            error=None if success else output,
            duration_ms=duration_ms,
            preview_path=preview_path,
            preview_language=preview_language,
            preview_content=preview_content,
        )
    except TimeoutError:
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.exception(
            "文件工具执行超时: tool_name=%s, tool_call_id=%s",
            tool_name,
            tool_call_id,
        )
        message = f"{tool_name} 执行超时（超过 {settings.tool_timeout_seconds}s）"
        writer({
            "tool_event": {
                "event_type": "status",
                "payload": {
                    "stage": "tool_timeout",
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "success": False,
                    "duration_ms": duration_ms,
                    "message": message,
                },
            }
        })
        return result_envelope(
            success=False,
            summary=f"{tool_name} 执行超时",
            error=message,
            error_type="timeout",
            duration_ms=duration_ms,
        )
    except Exception as exc:  # noqa: BLE001 - 工具异常需转换为可控 ToolMessage
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.exception(
            "文件工具执行失败: tool_name=%s, tool_call_id=%s",
            tool_name,
            tool_call_id,
        )
        message = truncate_text(str(exc), 500)
        error_type = "invalid_argument" if isinstance(exc, WorkspaceError) else "exception"
        writer({
            "tool_event": {
                "event_type": "status",
                "payload": {
                    "stage": "tool_failed",
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "success": False,
                    "duration_ms": duration_ms,
                    "message": message,
                },
            }
        })
        return result_envelope(
            success=False,
            summary=f"{tool_name} 执行失败",
            error=message,
            error_type=error_type,
            duration_ms=duration_ms,
        )


@tool
async def write_file(
    file_path: str,
    text: str,
    append: bool = False,
    state: Annotated[dict[str, Any], InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str:
    """Write or append text to a file inside the current isolated session workspace."""
    return await _invoke_file_tool(
        "write_file", {"file_path": file_path, "text": text, "append": append}, state or {}, tool_call_id
    )


FILE_TOOLS = [write_file]
