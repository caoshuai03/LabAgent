"""
@author: caoshuai.cs
@date: 2026-07-15 00:41
@description: Agent 用户/会话工作区管理与路径安全校验
"""
import os
import uuid
from pathlib import Path

from app.core.config import settings


class WorkspaceError(ValueError):
    """工作区或路径不合法。"""


class WorkspaceManager:
    """创建并校验用户/会话独立工作区。"""

    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.tool_workspace_root).expanduser().resolve()

    def ensure_workspace(self, user_id: int, session_id: str) -> Path:
        """惰性创建会话工作区。"""
        if user_id <= 0:
            raise WorkspaceError("用户ID不合法")
        try:
            normalized_session_id = str(uuid.UUID(session_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise WorkspaceError("会话ID不合法") from exc
        workspace = (self.root / str(user_id) / normalized_session_id).resolve()
        if not workspace.is_relative_to(self.root):
            raise WorkspaceError("工作区越界")
        for name in ("input", "output", "tmp"):
            (workspace / name).mkdir(parents=True, exist_ok=True)
        return workspace

    def validate_relative_path(
        self,
        workspace: Path,
        value: str,
        *,
        allow_missing: bool = True,
    ) -> Path:
        """校验相对路径、解析后边界与软链接越界。"""
        if not value or "\x00" in value:
            raise WorkspaceError("路径不能为空或包含空字符")
        user_path = Path(value)
        if user_path.is_absolute():
            raise WorkspaceError("只允许使用工作区相对路径")

        workspace = workspace.resolve()
        candidate = workspace / user_path
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(workspace):
            raise WorkspaceError("路径越出当前会话工作区")

        current = workspace
        for part in user_path.parts:
            if part in {"", "."}:
                continue
            if part == "..":
                raise WorkspaceError("路径不允许包含 ..")
            current = current / part
            if current.exists() or current.is_symlink():
                if current.is_symlink():
                    target = current.resolve(strict=False)
                    if not target.is_relative_to(workspace):
                        raise WorkspaceError("软链接指向工作区外部")

        if not allow_missing and not resolved.exists():
            raise WorkspaceError("目标路径不存在")
        return resolved

    def validate_file_size(self, path: Path, max_chars: int) -> None:
        """在读取前以字节数做保守上限检查。"""
        if path.is_file() and path.stat().st_size > max_chars * 4:
            raise WorkspaceError("文件过大，超出单次读取限制")

    def safe_environment(self) -> dict[str, str]:
        """构造 Shell 所需的最小环境变量，不传递密钥。"""
        allowed = {"PATH", "LANG", "LC_ALL", "TZ"}
        return {key: value for key, value in os.environ.items() if key in allowed}


workspace_manager = WorkspaceManager()
