"""
@author: caoshuai.cs
@date: 2026-07-15 00:41
@description: Shell Tool Runner 工作区、鉴权与命令策略测试
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.tools.shell_tool as shell_tool_module
import tool_runner.app as runner_app
from app.core.config import settings
from app.tools.result import parse_result_envelope
from app.tools.workspace import workspace_manager


def test_runner_executes_command_in_workspace(tmp_path: Path, monkeypatch) -> None:
    """Runner 应在授权工作区执行命令。"""
    workspace = tmp_path / "1" / "session"
    workspace.mkdir(parents=True)
    monkeypatch.setattr(runner_app, "_WORKSPACE_ROOT", tmp_path.resolve())
    monkeypatch.setattr(runner_app, "_RUNNER_TOKEN", "test-token")

    response = TestClient(runner_app.app).post(
        "/execute",
        headers={"Authorization": "Bearer test-token"},
        json={
            "commands": ["python -c 'print(123)'"],
            "workspace_path": str(workspace),
            "timeout_seconds": 5,
            "max_output_chars": 1000,
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "123" in response.json()["output"]


def test_runner_rejects_unauthorized_and_blocked_commands(tmp_path: Path, monkeypatch) -> None:
    """Runner 必须拒绝无鉴权请求和高风险可执行文件。"""
    workspace = tmp_path / "1" / "session"
    workspace.mkdir(parents=True)
    monkeypatch.setattr(runner_app, "_WORKSPACE_ROOT", tmp_path.resolve())
    monkeypatch.setattr(runner_app, "_RUNNER_TOKEN", "test-token")
    client = TestClient(runner_app.app)
    payload = {
        "commands": ["docker ps"],
        "workspace_path": str(workspace),
        "timeout_seconds": 5,
        "max_output_chars": 1000,
    }

    assert client.post("/execute", json=payload).status_code == 401
    assert client.post(
        "/execute", headers={"Authorization": "Bearer test-token"}, json=payload
    ).status_code == 403


@pytest.mark.asyncio
async def test_shell_tool_treats_none_output_as_failure(tmp_path: Path, monkeypatch) -> None:
    """LangChain ShellTool 吞掉执行异常返回 None 时必须标记为失败。"""
    old_root = workspace_manager.root
    workspace_manager.root = tmp_path.resolve()
    monkeypatch.setattr(settings, "agent_tools_enabled", True)
    monkeypatch.setattr(settings, "shell_tool_enabled", True)

    async def return_none(*args, **kwargs):
        return None

    monkeypatch.setattr(shell_tool_module.ShellTool, "ainvoke", return_none)
    session_id = "4fa78a24-8775-4786-b84d-27b86c5b879c"
    try:
        result = await shell_tool_module.execute_shell.coroutine(
            commands="pwd",
            state={
                "user_id": 1,
                "user_role": 1,
                "session_id": session_id,
                "workspace_path": str(tmp_path / "1" / session_id),
            },
            tool_call_id="call-shell-none",
        )
    finally:
        workspace_manager.root = old_root

    payload = parse_result_envelope(result)
    assert payload["success"] is False
    assert payload["summary"] == "Shell执行失败"
    assert payload["error"] == "Shell执行器未返回有效结果"
