"""
@author: caoshuai.cs
@date: 2026-08-02 00:00
@description: 副作用工具基于会话工作区的持久化幂等执行记录
"""
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class IdempotencyDecision:
    """工具执行前的幂等判定。"""

    should_execute: bool
    cached_result: str | None = None
    uncertain: bool = False


class ToolIdempotencyStore:
    """使用原子标记避免同一工具调用重复产生副作用。"""

    _DIRECTORY_NAME = ".tool_idempotency"

    def begin(
        self,
        workspace: Path,
        tool_name: str,
        tool_call_id: str,
        arguments: dict[str, Any],
    ) -> IdempotencyDecision:
        """原子取得执行权；已完成则重放结果，执行状态未知则禁止重试。"""
        if not tool_call_id:
            return IdempotencyDecision(should_execute=True)
        directory = self._directory(workspace)
        key = self._key(tool_name, tool_call_id)
        result_path = directory / f"{key}.result.json"
        marker_path = directory / f"{key}.running.json"
        arguments_hash = self._arguments_hash(arguments)

        if result_path.exists():
            cached_result = self._read_result(result_path, arguments_hash)
            if cached_result is not None:
                return IdempotencyDecision(should_execute=False, cached_result=cached_result)
            return IdempotencyDecision(should_execute=False, uncertain=True)

        marker_payload = json.dumps(
            {
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "arguments_hash": arguments_hash,
                "started_at": datetime.now(UTC).isoformat(),
            },
            ensure_ascii=False,
        )
        try:
            descriptor = os.open(marker_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return IdempotencyDecision(should_execute=False, uncertain=True)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(marker_payload)
            file.flush()
            os.fsync(file.fileno())
        return IdempotencyDecision(should_execute=True)

    def complete(
        self,
        workspace: Path,
        tool_name: str,
        tool_call_id: str,
        arguments: dict[str, Any],
        result: str,
    ) -> None:
        """原子保存完整工具结果，供恢复执行时直接重放。"""
        if not tool_call_id:
            return
        directory = self._directory(workspace)
        key = self._key(tool_name, tool_call_id)
        payload = json.dumps(
            {
                "arguments_hash": self._arguments_hash(arguments),
                "result": result,
                "finished_at": datetime.now(UTC).isoformat(),
            },
            ensure_ascii=False,
        )
        descriptor, temporary_path = tempfile.mkstemp(
            dir=directory,
            prefix=f".{key}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, directory / f"{key}.result.json")
            (directory / f"{key}.running.json").unlink(missing_ok=True)
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)

    def _directory(self, workspace: Path) -> Path:
        directory = workspace / self._DIRECTORY_NAME
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        return directory

    @staticmethod
    def _key(tool_name: str, tool_call_id: str) -> str:
        return hashlib.sha256(f"{tool_name}:{tool_call_id}".encode("utf-8")).hexdigest()

    @staticmethod
    def _arguments_hash(arguments: dict[str, Any]) -> str:
        serialized = json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _read_result(path: Path, arguments_hash: str) -> str | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or payload.get("arguments_hash") != arguments_hash:
            return None
        result = payload.get("result")
        return result if isinstance(result, str) else None


tool_idempotency_store = ToolIdempotencyStore()
