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


def test_read_file_is_low_risk(tmp_path: Path) -> None:
    """工作区内读文件不需审批。"""
    workspace = WorkspaceManager(str(tmp_path)).ensure_workspace(1, str(uuid.uuid4()))
    (workspace / "input" / "test.txt").write_text("hello", encoding="utf-8")

    decision = ToolPolicy().evaluate(
        "read_file", {"file_path": "input/test.txt"}, user_role=0, workspace=workspace
    )

    assert decision.allowed is True
    assert decision.requires_approval is False
    assert decision.risk_level == "low"


def test_shell_is_disabled_by_default(tmp_path: Path, monkeypatch) -> None:
    """Shell 默认关闭。"""
    monkeypatch.setattr(settings, "shell_tool_enabled", False)
    workspace = WorkspaceManager(str(tmp_path)).ensure_workspace(1, str(uuid.uuid4()))

    decision = ToolPolicy().evaluate(
        "execute_shell", {"commands": "pwd"}, user_role=1, workspace=workspace
    )

    assert decision.allowed is False


def test_shell_requires_admin_and_only_delete_needs_approval(
    tmp_path: Path, monkeypatch
) -> None:
    """开启Shell后仍校验角色，普通命令直行，删除命令需审批。"""
    monkeypatch.setattr(settings, "shell_tool_enabled", True)
    monkeypatch.setattr(settings, "shell_allowed_roles", "admin")
    monkeypatch.setattr(settings, "shell_delete_require_approval", True)
    workspace = WorkspaceManager(str(tmp_path)).ensure_workspace(1, str(uuid.uuid4()))

    user_decision = ToolPolicy().evaluate(
        "execute_shell", {"commands": "pwd"}, user_role=0, workspace=workspace
    )
    safe_decision = ToolPolicy().evaluate(
        "execute_shell", {"commands": "pwd"}, user_role=1, workspace=workspace
    )
    delete_decision = ToolPolicy().evaluate(
        "execute_shell", {"commands": "rm output/test.txt"}, user_role=1, workspace=workspace
    )

    assert user_decision.allowed is False
    assert safe_decision.allowed is True
    assert safe_decision.requires_approval is False
    assert safe_decision.risk_level == "medium"
    assert delete_decision.allowed is True
    assert delete_decision.requires_approval is True
    assert delete_decision.risk_level == "high"


def test_file_write_and_move_do_not_need_approval_but_delete_does(
    tmp_path: Path, monkeypatch
) -> None:
    """文件读写和移动直接执行，仅删除文件需要审批。"""
    monkeypatch.setattr(settings, "file_write_require_approval", False)
    monkeypatch.setattr(settings, "file_move_require_approval", False)
    monkeypatch.setattr(settings, "file_delete_require_approval", True)
    workspace = WorkspaceManager(str(tmp_path)).ensure_workspace(1, str(uuid.uuid4()))
    (workspace / "output" / "source.txt").write_text("hello", encoding="utf-8")

    write_decision = ToolPolicy().evaluate(
        "write_file", {"file_path": "output/new.txt"}, user_role=0, workspace=workspace
    )
    move_decision = ToolPolicy().evaluate(
        "move_file",
        {"source_path": "output/source.txt", "destination_path": "output/moved.txt"},
        user_role=0,
        workspace=workspace,
    )
    delete_decision = ToolPolicy().evaluate(
        "file_delete", {"file_path": "output/source.txt"}, user_role=0, workspace=workspace
    )

    assert write_decision.requires_approval is False
    assert move_decision.requires_approval is False
    assert delete_decision.requires_approval is True
