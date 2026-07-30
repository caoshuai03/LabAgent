"""
@author: caoshuai.cs
@date: 2026-07-30 00:00
@description: 用户级长期记忆的安全查找、搜索、读取、记住与忘记工具
"""
import asyncio
from typing import Annotated, Any, Literal

from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState

from app.services.memory_service import MemoryError, memory_service
from app.tools.result import result_envelope


def _user_id_from_state(state: dict[str, Any]) -> int:
    """从可信 Graph State 获取当前用户 ID。"""
    user_id = int(state.get("user_id") or 0)
    if user_id <= 0:
        raise MemoryError("长期记忆缺少当前用户上下文")
    return user_id


@tool
async def memory_find(
    pattern: str = "*.md",
    state: Annotated[dict[str, Any], InjectedState] = None,
) -> str:
    """Find memory files belonging to the current user by file-name pattern. Use before reading when the file is unknown."""
    try:
        output = await asyncio.to_thread(
            memory_service.find,
            _user_id_from_state(state or {}),
            pattern,
        )
        return result_envelope(success=True, output=output, summary="已查找用户长期记忆文件")
    except MemoryError as exc:
        return result_envelope(
            success=False,
            summary="长期记忆文件查找失败",
            error=str(exc),
            error_type="invalid_argument",
        )


@tool
async def memory_grep(
    query: str,
    path: str = ".",
    state: Annotated[dict[str, Any], InjectedState] = None,
) -> str:
    """Search text in the current user's memory Markdown files. Use for facts, preferences, or similar past experiences."""
    try:
        output = await asyncio.to_thread(
            memory_service.grep,
            _user_id_from_state(state or {}),
            query,
            path,
        )
        return result_envelope(success=True, output=output, summary=f"已搜索用户长期记忆：{query}")
    except MemoryError as exc:
        return result_envelope(
            success=False,
            summary="长期记忆搜索失败",
            error=str(exc),
            error_type="invalid_argument",
        )


@tool
async def memory_read(
    path: str,
    start_line: int = 1,
    end_line: int = 200,
    state: Annotated[dict[str, Any], InjectedState] = None,
) -> str:
    """Read a line range from one Markdown memory file belonging to the current user."""
    try:
        output = await asyncio.to_thread(
            memory_service.read,
            _user_id_from_state(state or {}),
            path,
            start_line,
            end_line,
        )
        return result_envelope(success=True, output=output, summary=f"已读取用户长期记忆 {path}")
    except MemoryError as exc:
        return result_envelope(
            success=False,
            summary="长期记忆读取失败",
            error=str(exc),
            error_type="invalid_argument",
        )


@tool
async def remember_memory(
    memory_type: Literal["fact", "preference", "experience"],
    title: str,
    content: str,
    normalized_key: str = "",
    state: Annotated[dict[str, Any], InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str:
    """Save a durable user fact, preference, or reusable experience only when the user explicitly asks to remember it."""
    try:
        state_value = state or {}
        item = await asyncio.to_thread(
            memory_service.add_item,
            _user_id_from_state(state_value),
            memory_type,
            title,
            content,
            source_session_id=str(state_value.get("session_id") or "") or None,
            updated_by="user",
            normalized_key=normalized_key.strip() or None,
        )
        return result_envelope(
            success=True,
            output={"memory_id": item.memory_id, "memory_type": item.memory_type},
            summary=f"已记住：{item.title}",
        )
    except MemoryError as exc:
        return result_envelope(
            success=False,
            summary="保存长期记忆失败",
            error=str(exc),
            error_type="invalid_argument",
        )


@tool
async def forget_memory(
    memory_id: str,
    state: Annotated[dict[str, Any], InjectedState] = None,
) -> str:
    """Delete one durable memory belonging to the current user when the user explicitly asks to forget it."""
    try:
        deleted = await asyncio.to_thread(
            memory_service.delete_item,
            _user_id_from_state(state or {}),
            memory_id,
        )
        return result_envelope(
            success=deleted,
            output={"memory_id": memory_id, "deleted": deleted},
            summary="已删除长期记忆" if deleted else "未找到要删除的长期记忆",
            error=None if deleted else "长期记忆不存在",
            error_type=None if deleted else "not_found",
        )
    except MemoryError as exc:
        return result_envelope(
            success=False,
            summary="删除长期记忆失败",
            error=str(exc),
            error_type="invalid_argument",
        )


MEMORY_TOOLS = [memory_find, memory_grep, memory_read, remember_memory, forget_memory]
