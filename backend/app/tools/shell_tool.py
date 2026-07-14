"""
@author: caoshuai.cs
@date: 2026-07-15 00:41
@description: LangChain ShellTool 受控 Tool Runner 适配
"""
import time
from pathlib import Path
from typing import Annotated, Any

import httpx
from langchain_community.tools import ShellTool
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState

from app.core.config import settings
from app.tools.policy import tool_policy
from app.tools.result import result_envelope, safe_stream_writer, truncate_text
from app.tools.workspace import WorkspaceError, workspace_manager


class SandboxShellProcess:
    """ShellTool process 协议实现，把命令发送给内部 Tool Runner。"""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def run(self, commands: str | list[str]) -> str:
        """调用内部 runner 并返回执行输出。"""
        headers: dict[str, str] = {}
        if settings.tool_runner_token:
            headers["Authorization"] = f"Bearer {settings.tool_runner_token}"
        payload = {
            "commands": commands if isinstance(commands, list) else [commands],
            "workspace_path": str(self.workspace),
            "timeout_seconds": settings.shell_timeout_seconds,
            "max_output_chars": settings.tool_max_output_chars,
        }
        with httpx.Client(timeout=settings.shell_timeout_seconds + 5) as client:
            response = client.post(
                f"{settings.tool_runner_base_url.rstrip('/')}/execute",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        if not data.get("success"):
            raise RuntimeError(str(data.get("error") or "Shell执行失败"))
        return str(data.get("output") or "")


@tool("execute_shell")
async def execute_shell(
    commands: str | list[str],
    state: Annotated[dict[str, Any], InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str:
    """Execute commands inside the current isolated session workspace sandbox."""
    started = time.monotonic()
    writer = safe_stream_writer()
    current_state = state or {}
    try:
        workspace = workspace_manager.ensure_workspace(
            int(current_state["user_id"]), str(current_state["session_id"])
        )
        if Path(str(current_state.get("workspace_path", workspace))).resolve() != workspace:
            raise WorkspaceError("工作区上下文不匹配")
        arguments = {"commands": commands}
        decision = tool_policy.evaluate(
            "execute_shell",
            arguments,
            user_role=int(current_state.get("user_role", 0)),
            workspace=workspace,
        )
        if not decision.allowed:
            raise WorkspaceError(decision.message)

        writer({
            "tool_event": {
                "event_type": "status",
                "payload": {
                    "stage": "tool_running",
                    "tool_call_id": tool_call_id,
                    "tool_name": "execute_shell",
                },
            }
        })
        shell_tool = ShellTool(
            name="execute_shell",
            description="Execute commands inside the current isolated session workspace sandbox.",
            process=SandboxShellProcess(workspace),
            ask_human_input=False,
        )
        output = await shell_tool.ainvoke({"commands": commands})
        if output is None:
            raise RuntimeError("Shell执行器未返回有效结果")
        duration_ms = int((time.monotonic() - started) * 1000)
        output_text = truncate_text(str(output))
        summary = f"Shell执行完成，耗时 {duration_ms}ms"
        writer({
            "tool_event": {
                "event_type": "status",
                "payload": {
                    "stage": "tool_done",
                    "tool_call_id": tool_call_id,
                    "tool_name": "execute_shell",
                    "success": True,
                    "duration_ms": duration_ms,
                },
            }
        })
        return result_envelope(
            success=True,
            output=output_text,
            summary=summary,
            duration_ms=duration_ms,
        )
    except Exception as exc:  # noqa: BLE001 - 工具异常转为可控 ToolMessage
        duration_ms = int((time.monotonic() - started) * 1000)
        message = truncate_text(str(exc), 500)
        writer({
            "tool_event": {
                "event_type": "status",
                "payload": {
                    "stage": "tool_failed",
                    "tool_call_id": tool_call_id,
                    "tool_name": "execute_shell",
                    "success": False,
                    "duration_ms": duration_ms,
                    "message": message,
                },
            }
        })
        return result_envelope(
            success=False,
            summary="Shell执行失败",
            error=message,
            duration_ms=duration_ms,
        )
