"""
@author: caoshuai.cs
@date: 2026-07-15 00:41
@description: LangChain FileManagementToolkit 文件工具适配
"""
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


def _workspace_from_state(state: dict[str, Any]) -> Path:
    """从 Graph State 获取并复核当前工作区。"""
    workspace = workspace_manager.ensure_workspace(int(state["user_id"]), str(state["session_id"]))
    state_workspace = Path(str(state.get("workspace_path", workspace))).resolve()
    if state_workspace != workspace:
        raise WorkspaceError("工作区上下文不匹配")
    return workspace


def _summary(tool_name: str, arguments: dict[str, Any], output: str, success: bool) -> str:
    """生成用于前端与持久化的简短摘要。"""
    if not success:
        return truncate_text(output, 300)
    path = arguments.get("file_path") or arguments.get("source_path") or arguments.get("dir_path") or "."
    labels = {
        "list_directory": f"已列出目录 {path}",
        "file_search": f"已搜索文件 {arguments.get('pattern', '')}",
        "read_file": f"已读取文件 {path}",
        "write_file": f"已写入文件 {path}",
        "copy_file": f"已复制文件 {path}",
        "move_file": f"已移动文件 {path}",
        "file_delete": f"已删除文件 {path}",
    }
    return labels.get(tool_name, f"工具 {tool_name} 执行完成")


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

        if tool_name == "read_file":
            path = workspace_manager.validate_relative_path(
                workspace, str(arguments["file_path"]), allow_missing=False
            )
            workspace_manager.validate_file_size(path, settings.tool_max_read_chars)
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
        output = str(await target_tool.ainvoke(arguments))
        if tool_name == "file_search":
            lines = output.splitlines()
            output = "\n".join(lines[: settings.tool_max_search_results])
        output = truncate_text(output)
        success = not output.lower().startswith("error:")
        duration_ms = int((time.monotonic() - started) * 1000)
        summary = _summary(tool_name, arguments, output, success)
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
        )
    except Exception as exc:  # noqa: BLE001 - 工具异常需转换为可控 ToolMessage
        duration_ms = int((time.monotonic() - started) * 1000)
        message = truncate_text(str(exc), 500)
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
            duration_ms=duration_ms,
        )


@tool
async def list_directory(
    dir_path: str = ".",
    state: Annotated[dict[str, Any], InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str:
    """List files and directories inside the current isolated session workspace."""
    return await _invoke_file_tool("list_directory", {"dir_path": dir_path}, state or {}, tool_call_id)


@tool
async def file_search(
    pattern: str,
    dir_path: str = ".",
    state: Annotated[dict[str, Any], InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str:
    """Search files by glob pattern inside the current isolated session workspace."""
    return await _invoke_file_tool(
        "file_search", {"pattern": pattern, "dir_path": dir_path}, state or {}, tool_call_id
    )


@tool
async def read_file(
    file_path: str,
    state: Annotated[dict[str, Any], InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str:
    """Read a text file inside the current isolated session workspace."""
    return await _invoke_file_tool("read_file", {"file_path": file_path}, state or {}, tool_call_id)


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


@tool
async def copy_file(
    source_path: str,
    destination_path: str,
    state: Annotated[dict[str, Any], InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str:
    """Copy a file inside the current isolated session workspace."""
    return await _invoke_file_tool(
        "copy_file",
        {"source_path": source_path, "destination_path": destination_path},
        state or {},
        tool_call_id,
    )


@tool
async def move_file(
    source_path: str,
    destination_path: str,
    state: Annotated[dict[str, Any], InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str:
    """Move or rename a file inside the current isolated session workspace."""
    return await _invoke_file_tool(
        "move_file",
        {"source_path": source_path, "destination_path": destination_path},
        state or {},
        tool_call_id,
    )


@tool
async def file_delete(
    file_path: str,
    state: Annotated[dict[str, Any], InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str:
    """Delete a file inside the current isolated session workspace."""
    return await _invoke_file_tool("file_delete", {"file_path": file_path}, state or {}, tool_call_id)


FILE_TOOLS = [list_directory, file_search, read_file, write_file, copy_file, move_file, file_delete]
