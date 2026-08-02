"""
@author: caoshuai.cs
@date: 2026-07-30
@description: Agent Skill 激活与按需资源读取工具
"""
import asyncio
import time
from typing import Annotated, Any

from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState

from app.services.skill_service import SkillError, skill_catalog, skill_service
from app.tools.result import result_envelope, safe_stream_writer


@tool("activate_skill")
async def activate_skill(
    name: str,
    state: Annotated[dict[str, Any], InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str:
    """Activate a listed Skill before following its specialized workflow.

    Pass the exact Skill name from the available_skills catalog. Activation loads
    the reviewed SKILL.md instructions into the current Agent run.
    """
    started = time.monotonic()
    try:
        current_state = state or {}
        activations = list(current_state.get("activated_skills") or [])
        _, definition, already_active = skill_service.activate(name, activations)
        return result_envelope(
            success=True,
            output=f"Skill {definition.name} 已就绪",
            summary=(
                f"Skill {definition.name} 已激活"
                if not already_active
                else f"Skill {definition.name} 已处于激活状态"
            ),
            internal=already_active,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    except SkillError as exc:
        return result_envelope(
            success=False,
            summary="Skill 激活失败",
            error=str(exc),
            error_type="invalid_argument",
            duration_ms=int((time.monotonic() - started) * 1000),
        )


@tool("read_skill_resource")
async def read_skill_resource(
    name: str,
    resource_path: str,
    state: Annotated[dict[str, Any], InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str:
    """Read a text resource referenced by an already activated Skill.

    Use an exact relative path listed by that Skill, such as
    references/common-exceptions.md. Never guess or use absolute paths.
    """
    started = time.monotonic()
    writer = safe_stream_writer()
    try:
        current_state = state or {}
        active_names = {
            str(item.get("name"))
            for item in current_state.get("activated_skills") or []
            if isinstance(item, dict)
        }
        if name not in active_names:
            raise SkillError("请先激活对应 Skill")
        content = await asyncio.to_thread(skill_catalog.read_resource, name, resource_path)
        writer(
            {
                "tool_event": {
                    "event_type": "skill_resource_loaded",
                    "payload": {
                        "tool_call_id": tool_call_id,
                        "skill_name": name,
                        "resource_path": resource_path,
                    },
                }
            }
        )
        return result_envelope(
            success=True,
            output=content,
            summary=f"已读取 Skill 资源 {resource_path}",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    except SkillError as exc:
        return result_envelope(
            success=False,
            summary="Skill 资源读取失败",
            error=str(exc),
            error_type="invalid_argument",
            duration_ms=int((time.monotonic() - started) * 1000),
        )


SKILL_TOOLS = [activate_skill, read_skill_resource]
