"""
@author: caoshuai.cs
@date: 2026-08-02 00:00
@description: 用户明确要求记忆时立即更新 USER_PROFILE.md 的受控工具
"""
import asyncio
import logging
from typing import Annotated, Any

from langchain_core.tools import BaseTool
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState

from app.services.memory_extraction_service import save_explicit_memory
from app.tools.idempotency import tool_idempotency_store
from app.tools.result import result_envelope
from app.tools.workspace import workspace_manager

logger = logging.getLogger("labagent")


@tool
async def save_user_memory(
    memory: str,
    state: Annotated[dict[str, Any], InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str:
    """仅当用户明确要求记住时，保存其稳定信息、偏好或规则。"""
    current_state = state or {}
    arguments = {"memory": memory}
    try:
        user_id = int(current_state["user_id"])
        session_id = str(current_state["session_id"])
        workspace = workspace_manager.ensure_workspace(user_id, session_id)
        idempotency = await asyncio.to_thread(
            tool_idempotency_store.begin,
            workspace,
            "save_user_memory",
            tool_call_id,
            arguments,
        )
        if idempotency.cached_result is not None:
            return idempotency.cached_result
        if idempotency.uncertain:
            return result_envelope(
                success=False,
                summary="个性化记忆未重复保存",
                error="同一工具调用上次执行状态不确定，已阻止重复写入",
                error_type="idempotency_conflict",
            )

        changed = await save_explicit_memory(
            user_id,
            memory,
            model_name=current_state.get("model_name"),
        )
        result = result_envelope(
            success=changed,
            output="USER_PROFILE.md 已更新" if changed else "",
            summary="已保存到个性化记忆" if changed else "个性化记忆未发生变化",
            error=None if changed else "该信息可能已存在或不适合保存为长期记忆",
            error_type=None if changed else "unchanged",
        )
        await asyncio.to_thread(
            tool_idempotency_store.complete,
            workspace,
            "save_user_memory",
            tool_call_id,
            arguments,
            result,
        )
        return result
    except (KeyError, TypeError, ValueError) as exc:
        return result_envelope(
            success=False,
            summary="个性化记忆保存失败",
            error=str(exc),
            error_type="invalid_argument",
        )
    except TimeoutError:
        logger.warning(
            "个性化记忆工具超时: tool_call_id=%s, user_id=%s, model=%s",
            tool_call_id,
            current_state.get("user_id"),
            current_state.get("model_name"),
        )
        return result_envelope(
            success=False,
            summary="个性化记忆保存超时",
            error="模型处理超时，未更新 USER_PROFILE.md",
            error_type="timeout",
        )
    except Exception as exc:
        logger.warning(
            "个性化记忆工具失败: tool_call_id=%s, user_id=%s, model=%s, error_type=%s",
            tool_call_id,
            current_state.get("user_id"),
            current_state.get("model_name"),
            type(exc).__name__,
        )
        raise


MEMORY_TOOLS: list[BaseTool] = [save_user_memory]
