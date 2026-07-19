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
    "write_file": ("file_path",),
}
_BLOCKED_EXECUTABLES = {
    "sudo", "su", "mount", "umount", "mkfs", "dd", "shutdown", "reboot",
    "ssh", "scp", "sftp", "telnet", "nc", "ncat", "docker", "podman",
}
_DELETE_EXECUTABLES = {"rm", "rmdir", "unlink", "shred"}
# 只读命令白名单：查看目录、读文件、搜索等，风险最低，直接执行
_READ_ONLY_EXECUTABLES = {
    "ls", "cat", "head", "tail", "pwd", "grep", "egrep", "fgrep", "rg",
    "find", "wc", "stat", "file", "tree", "echo", "which", "diff", "sort", "uniq",
}
# 命令分隔符：其后是新的命令段首词
_SHELL_SEPARATORS = {";", "&&", "||", "|", "&", "|&"}
# 输出重定向：写文件语义
_WRITE_REDIRECTS = {">", ">>", "&>", "2>", "2>>"}
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
        workspace: Path,
    ) -> ToolPolicyDecision:
        """评估工具是否允许以及是否需审批。"""
        if not settings.agent_tools_enabled:
            return ToolPolicyDecision(False, False, "high", "Agent工具未启用")
        if tool_name == "search_knowledge_base":
            # 只读知识库检索，无路径/命令参数，低风险直接放行
            return ToolPolicyDecision(True, False, "low")
        if tool_name in _FILE_PATH_FIELDS:
            return self._evaluate_file(tool_name, arguments, workspace)
        if tool_name == "execute_shell":
            return self._evaluate_shell(arguments)
        return ToolPolicyDecision(False, False, "high", "未注册的工具")

    def _evaluate_file(
        self, tool_name: str, arguments: dict[str, Any], workspace: Path
    ) -> ToolPolicyDecision:
        if not settings.file_tools_enabled:
            return ToolPolicyDecision(False, False, "medium", "文件工具未启用")
        try:
            for field in _FILE_PATH_FIELDS[tool_name]:
                value = str(arguments.get(field, ""))
                workspace_manager.validate_relative_path(workspace, value, allow_missing=True)
        except WorkspaceError as exc:
            return ToolPolicyDecision(False, False, "high", str(exc))

        return ToolPolicyDecision(True, settings.file_write_require_approval, "medium")

    def _tokenize_shell(self, command: str) -> list[str]:
        """按 shell 词法拆分命令，将操作符拆成独立 token。"""
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)

    def _evaluate_shell(self, arguments: dict[str, Any]) -> ToolPolicyDecision:
        if not settings.shell_tool_enabled:
            return ToolPolicyDecision(False, False, "high", "Shell工具未启用")
        commands = arguments.get("commands")
        command_list = commands if isinstance(commands, list) else [commands]
        if not command_list or any(not isinstance(command, str) or not command.strip() for command in command_list):
            return ToolPolicyDecision(False, False, "high", "Shell命令不能为空")
        if sum(len(command) for command in command_list) > settings.tool_max_write_chars:
            return ToolPolicyDecision(False, False, "high", "Shell命令过长")
        has_delete = False
        has_write = False
        for command in command_list:
            if _DANGEROUS_SHELL_PATTERN.search(command):
                return ToolPolicyDecision(False, False, "high", "Shell命令包含禁止的结构或路径")
            try:
                tokens = self._tokenize_shell(command)
            except ValueError:
                return ToolPolicyDecision(False, False, "high", "Shell命令格式错误")
            if not tokens:
                return ToolPolicyDecision(False, False, "high", "Shell命令不能为空")
            expect_command = True
            for token in tokens:
                if token in _WRITE_REDIRECTS:
                    # 输出重定向属于写操作
                    has_write = True
                    expect_command = False
                    continue
                if token in _SHELL_SEPARATORS:
                    expect_command = True
                    continue
                if not expect_command:
                    continue
                # 命令段首词：判定风险等级
                executable = Path(token).name.lower()
                if executable in _BLOCKED_EXECUTABLES:
                    return ToolPolicyDecision(False, False, "high", "Shell命令被安全策略拒绝")
                if executable in _DELETE_EXECUTABLES:
                    has_delete = True
                elif executable not in _READ_ONLY_EXECUTABLES:
                    # 不在只读白名单内的命令（如 cp/mv/mkdir/touch/python 等）视为写操作
                    has_write = True
                expect_command = False
            # find -delete 语义为删除
            if "find" in {Path(token).name.lower() for token in tokens} and "-delete" in tokens:
                has_delete = True
        if has_delete:
            return ToolPolicyDecision(True, settings.shell_delete_require_approval, "high")
        if has_write:
            return ToolPolicyDecision(True, False, "medium")
        return ToolPolicyDecision(True, False, "low")


tool_policy = ToolPolicy()
