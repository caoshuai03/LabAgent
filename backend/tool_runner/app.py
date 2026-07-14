"""
@author: caoshuai.cs
@date: 2026-07-15 00:41
@description: Agent Shell 内部 Tool Runner，仅在会话工作区执行受控命令
"""
import asyncio
import os
import shlex
import signal
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="LabAgent Tool Runner")

_WORKSPACE_ROOT = Path(os.getenv("TOOL_WORKSPACE_ROOT", "/data/tool-workspaces")).resolve()
_RUNNER_TOKEN = os.getenv("TOOL_RUNNER_TOKEN", "")
_BLOCKED_EXECUTABLES = {
    "sudo", "su", "mount", "umount", "mkfs", "dd", "shutdown", "reboot",
    "ssh", "scp", "sftp", "telnet", "nc", "ncat", "docker", "podman",
}


class ExecuteRequest(BaseModel):
    """Shell 执行请求。"""

    commands: list[str] = Field(min_length=1, max_length=10)
    workspace_path: str
    timeout_seconds: int = Field(default=20, ge=1, le=120)
    max_output_chars: int = Field(default=12000, ge=100, le=100000)


def _authorize(authorization: str | None) -> None:
    """验证 backend 与 runner 之间的内部 Token。"""
    if not _RUNNER_TOKEN:
        raise HTTPException(status_code=503, detail="Tool Runner Token 未配置")
    expected = f"Bearer {_RUNNER_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="未授权的 Tool Runner 请求")


def _workspace(value: str) -> Path:
    """校验 runner 工作目录。"""
    path = Path(value).resolve()
    if not path.is_relative_to(_WORKSPACE_ROOT) or not path.is_dir():
        raise HTTPException(status_code=400, detail="工作区不合法")
    return path


def _command_parts(command: str) -> list[str]:
    """将单条命令解析为参数列表，不经过 shell 解释器。"""
    try:
        parts = shlex.split(command)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Shell命令格式错误") from exc
    if not parts:
        raise HTTPException(status_code=400, detail="Shell命令不能为空")
    if Path(parts[0]).name.lower() in _BLOCKED_EXECUTABLES:
        raise HTTPException(status_code=403, detail="Shell命令被安全策略拒绝")
    return parts


async def _terminate(process: asyncio.subprocess.Process) -> None:
    """终止整个子进程组。"""
    if process.returncode is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=2)
    except TimeoutError:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        await process.wait()


async def _run_command(parts: list[str], workspace: Path, timeout_seconds: int) -> tuple[int, str]:
    """执行单条命令并合并 stdout/stderr。"""
    env = {key: value for key, value in os.environ.items() if key in {"PATH", "LANG", "LC_ALL", "TZ"}}
    process = await asyncio.create_subprocess_exec(
        *parts,
        cwd=workspace,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except TimeoutError:
        await _terminate(process)
        raise HTTPException(status_code=408, detail="Shell命令执行超时")
    return process.returncode or 0, output.decode("utf-8", errors="replace")


@app.post("/execute")
async def execute(
    request: ExecuteRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    """在受控工作区顺序执行命令。"""
    _authorize(authorization)
    workspace = _workspace(request.workspace_path)
    outputs: list[str] = []
    for command in request.commands:
        return_code, output = await _run_command(
            _command_parts(command), workspace, request.timeout_seconds
        )
        outputs.append(f"$ {command}\n{output}")
        if return_code != 0:
            combined = "\n".join(outputs)
            return {
                "success": False,
                "output": combined[: request.max_output_chars],
                "error": f"命令退出码: {return_code}",
            }
    combined = "\n".join(outputs)
    return {"success": True, "output": combined[: request.max_output_chars], "error": None}


@app.get("/health")
async def health() -> dict[str, str]:
    """健康检查。"""
    return {"status": "ok"}
