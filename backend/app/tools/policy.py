"""
@author: caoshuai.cs
@date: 2026-07-15 00:41
@description: Agent 工具白名单、风险、权限、路径与 Shell 命令策略
"""
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.tools.workspace import WorkspaceError, workspace_manager

_FILE_PATH_FIELDS: dict[str, tuple[str, ...]] = {
    "list_directory": ("dir_path",),
    "file_search": ("dir_path",),
    "read_file": ("file_path",),
    "write_file": ("file_path",),
    "copy_file": ("source_path", "destination_path"),
    "move_file": ("source_path", "destination_path"),
    "file_delete": ("file_path",),
}
_BLOCKED_EXECUTABLES = {
    "sudo", "su", "mount", "umount", "mkfs", "dd", "shutdown", "reboot",
    "ssh", "scp", "sftp", "telnet", "nc", "ncat", "docker", "podman",
}
_DELETE_EXECUTABLES = {"rm", "rmdir", "unlink", "shred"}
_DANGEROUS_SHELL_PATTERN = re.compile(r"[`\n\r]|\$\(|\b(/dev/|/proc/|/sys/|docker\.sock)\b")


@dataclass(frozen=True)
class ToolPolicyDecision:
    """工具策略决策。"""

    allowed: bool
    requires_approval: bool
    risk_level: str
    message: str = ""


class ToolPolicy:
    """工具执行前策略校验。"""

    def evaluate(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        user_role: int,
        workspace: Path,
    ) -> ToolPolicyDecision:
        """评估工具是否允许以及是否需审批。"""
        if not settings.agent_tools_enabled:
            return ToolPolicyDecision(False, False, "high", "Agent工具未启用")
        if tool_name in _FILE_PATH_FIELDS:
            return self._evaluate_file(tool_name, arguments, workspace)
        if tool_name == "execute_shell":
            return self._evaluate_shell(arguments, user_role)
        return ToolPolicyDecision(False, False, "high", "未注册的工具")

    def _evaluate_file(
        self, tool_name: str, arguments: dict[str, Any], workspace: Path
    ) -> ToolPolicyDecision:
        if not settings.file_tools_enabled:
            return ToolPolicyDecision(False, False, "medium", "文件工具未启用")
        try:
            for field in _FILE_PATH_FIELDS[tool_name]:
                default = "." if field == "dir_path" else ""
                value = str(arguments.get(field, default))
                allow_missing = field == "destination_path" or tool_name == "write_file"
                workspace_manager.validate_relative_path(workspace, value, allow_missing=allow_missing)
        except WorkspaceError as exc:
            return ToolPolicyDecision(False, False, "high", str(exc))

        if tool_name in {"list_directory", "file_search", "read_file"}:
            return ToolPolicyDecision(True, False, "low")
        if tool_name in {"write_file", "copy_file"}:
            return ToolPolicyDecision(True, settings.file_write_require_approval, "medium")
        if tool_name == "move_file":
            return ToolPolicyDecision(True, settings.file_move_require_approval, "high")
        return ToolPolicyDecision(True, settings.file_delete_require_approval, "high")

    def _evaluate_shell(self, arguments: dict[str, Any], user_role: int) -> ToolPolicyDecision:
        if not settings.shell_tool_enabled:
            return ToolPolicyDecision(False, False, "high", "Shell工具未启用")
        if user_role not in settings.shell_allowed_role_set:
            return ToolPolicyDecision(False, False, "high", "当前角色不允许使用Shell")
        commands = arguments.get("commands")
        command_list = commands if isinstance(commands, list) else [commands]
        if not command_list or any(not isinstance(command, str) or not command.strip() for command in command_list):
            return ToolPolicyDecision(False, False, "high", "Shell命令不能为空")
        if sum(len(command) for command in command_list) > settings.tool_max_write_chars:
            return ToolPolicyDecision(False, False, "high", "Shell命令过长")
        requires_approval = False
        for command in command_list:
            if _DANGEROUS_SHELL_PATTERN.search(command):
                return ToolPolicyDecision(False, False, "high", "Shell命令包含禁止的结构或路径")
            try:
                parts = shlex.split(command)
            except ValueError:
                return ToolPolicyDecision(False, False, "high", "Shell命令格式错误")
            if not parts or Path(parts[0]).name.lower() in _BLOCKED_EXECUTABLES:
                return ToolPolicyDecision(False, False, "high", "Shell命令被安全策略拒绝")
            executable = Path(parts[0]).name.lower()
            is_delete_command = executable in _DELETE_EXECUTABLES or (
                executable == "find" and "-delete" in parts
            )
            requires_approval = requires_approval or is_delete_command
        needs_confirmation = requires_approval and settings.shell_delete_require_approval
        return ToolPolicyDecision(
            True,
            needs_confirmation,
            "high" if requires_approval else "medium",
        )


tool_policy = ToolPolicy()
