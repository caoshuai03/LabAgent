"""
@author: caoshuai.cs
@date: 2026-07-15 00:41
@description: Agent 文件与 Shell 工具策略测试
"""
import uuid
from pathlib import Path

from app.core.config import settings
from app.tools.policy import ToolPolicy
from app.tools.workspace import WorkspaceManager


def test_write_file_is_medium_risk(tmp_path: Path) -> None:
    """工作区内写文件默认无需审批。"""
    workspace = WorkspaceManager(str(tmp_path)).ensure_workspace(1, str(uuid.uuid4()))

    decision = ToolPolicy().evaluate(
        "write_file", {"file_path": "output/test.txt"}, workspace=workspace
    )

    assert decision.allowed is True
    assert decision.requires_approval is False
    assert decision.risk_level == "medium"


def test_shell_is_disabled_by_default(tmp_path: Path, monkeypatch) -> None:
    """Shell 默认关闭。"""
    monkeypatch.setattr(settings, "shell_tool_enabled", False)
    workspace = WorkspaceManager(str(tmp_path)).ensure_workspace(1, str(uuid.uuid4()))

    decision = ToolPolicy().evaluate(
        "execute_shell", {"commands": "pwd"}, workspace=workspace
    )

    assert decision.allowed is False


def test_shell_read_write_delete_tiering(tmp_path: Path, monkeypatch) -> None:
    """开启Shell后按读写分级：只读命令 low、写命令 medium、删除命令 high 且需审批。"""
    monkeypatch.setattr(settings, "shell_tool_enabled", True)
    monkeypatch.setattr(settings, "shell_delete_require_approval", True)
    workspace = WorkspaceManager(str(tmp_path)).ensure_workspace(1, str(uuid.uuid4()))

    read_decision = ToolPolicy().evaluate(
        "execute_shell", {"commands": "pwd"}, workspace=workspace
    )
    write_decision = ToolPolicy().evaluate(
        "execute_shell", {"commands": "cp a.txt b.txt"}, workspace=workspace
    )
    delete_decision = ToolPolicy().evaluate(
        "execute_shell", {"commands": "rm output/test.txt"}, workspace=workspace
    )

    assert read_decision.allowed is True
    assert read_decision.requires_approval is False
    assert read_decision.risk_level == "low"
    assert write_decision.allowed is True
    assert write_decision.requires_approval is False
    assert write_decision.risk_level == "medium"
    assert delete_decision.allowed is True
    assert delete_decision.requires_approval is True
    assert delete_decision.risk_level == "high"


def test_shell_rejects_blocked_and_dangerous_commands(tmp_path: Path, monkeypatch) -> None:
    """危险结构与高风险可执行文件必须被拒绝。"""
    monkeypatch.setattr(settings, "shell_tool_enabled", True)
    workspace = WorkspaceManager(str(tmp_path)).ensure_workspace(1, str(uuid.uuid4()))

    blocked_decision = ToolPolicy().evaluate(
        "execute_shell", {"commands": "docker ps"}, workspace=workspace
    )
    dangerous_decision = ToolPolicy().evaluate(
        "execute_shell", {"commands": "cat $(whoami)"}, workspace=workspace
    )

    assert blocked_decision.allowed is False
    assert dangerous_decision.allowed is False


def test_shell_scans_all_command_segments(tmp_path: Path, monkeypatch) -> None:
    """操作符后隐藏的命令段也要参与安全扫描与读写分级。"""
    monkeypatch.setattr(settings, "shell_tool_enabled", True)
    monkeypatch.setattr(settings, "shell_delete_require_approval", True)
    workspace = WorkspaceManager(str(tmp_path)).ensure_workspace(1, str(uuid.uuid4()))

    hidden_blocked = ToolPolicy().evaluate(
        "execute_shell", {"commands": "echo hi && docker ps"}, workspace=workspace
    )
    redirect_write = ToolPolicy().evaluate(
        "execute_shell", {"commands": "echo hi > out.txt"}, workspace=workspace
    )
    hidden_delete = ToolPolicy().evaluate(
        "execute_shell", {"commands": "pwd && rm out.txt"}, workspace=workspace
    )
    read_pipe = ToolPolicy().evaluate(
        "execute_shell", {"commands": "cat a.txt | grep x"}, workspace=workspace
    )

    assert hidden_blocked.allowed is False
    assert redirect_write.risk_level == "medium"
    assert hidden_delete.risk_level == "high"
    assert hidden_delete.requires_approval is True
    assert read_pipe.risk_level == "low"
