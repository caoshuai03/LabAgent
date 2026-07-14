"""
@author: caoshuai.cs
@date: 2026-07-15 00:41
@description: Agent 工作区隔离与路径安全测试
"""
import uuid
from pathlib import Path

import pytest

from app.tools.workspace import WorkspaceError, WorkspaceManager


def test_workspace_isolated_by_user_and_session(tmp_path: Path) -> None:
    """用户和会话必须使用不同工作区。"""
    manager = WorkspaceManager(str(tmp_path))
    session_a = str(uuid.uuid4())
    session_b = str(uuid.uuid4())

    workspace_a = manager.ensure_workspace(1, session_a)
    workspace_b = manager.ensure_workspace(1, session_b)
    workspace_c = manager.ensure_workspace(2, session_a)

    assert workspace_a != workspace_b
    assert workspace_a != workspace_c
    assert (workspace_a / "input").is_dir()
    assert (workspace_a / "output").is_dir()


@pytest.mark.parametrize("value", ["../secret.txt", "/etc/passwd", "output/../../secret.txt"])
def test_path_traversal_is_rejected(tmp_path: Path, value: str) -> None:
    """路径遍历和绝对路径必须被拒绝。"""
    manager = WorkspaceManager(str(tmp_path))
    workspace = manager.ensure_workspace(1, str(uuid.uuid4()))

    with pytest.raises(WorkspaceError):
        manager.validate_relative_path(workspace, value)


def test_external_symlink_is_rejected(tmp_path: Path) -> None:
    """工作区内指向外部的软链接必须被拒绝。"""
    manager = WorkspaceManager(str(tmp_path / "root"))
    workspace = manager.ensure_workspace(1, str(uuid.uuid4()))
    external = tmp_path / "external"
    external.mkdir()
    (workspace / "link").symlink_to(external, target_is_directory=True)

    with pytest.raises(WorkspaceError):
        manager.validate_relative_path(workspace, "link/secret.txt")
