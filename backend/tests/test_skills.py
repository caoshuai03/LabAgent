"""
@author: caoshuai.cs
@date: 2026-07-30
@description: Markdown Skills 目录、安全资源读取与 LangGraph 激活流程测试
"""
import uuid
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver

import app.graph.chat_graph as chat_graph
from app.services.skill_service import SkillError, skill_catalog, skill_service
from app.tools.workspace import workspace_manager


def _write_skill(root: Path, name: str, body: str = "遵循测试排查流程。") -> Path:
    """在临时目录创建满足规范的最小 Skill。"""
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        (
            "---\n"
            f"name: {name}\n"
            "description: 用于验证 Skill 加载、激活和安全资源读取的测试技能。\n"
            "---\n\n"
            f"# 测试 Skill\n\n{body}"
        ),
        encoding="utf-8",
    )
    return directory


@pytest.fixture
def skill_environment(tmp_path: Path, monkeypatch):
    """隔离全局 Skill 目录并在测试后恢复内置目录。"""
    original_directory = chat_graph.settings.skills_directory
    skill_root = tmp_path / "skills"
    skill_root.mkdir()
    monkeypatch.setattr(chat_graph.settings, "skills_directory", str(skill_root))
    monkeypatch.setattr(chat_graph.settings, "skills_enabled", True)
    yield skill_root
    monkeypatch.setattr(chat_graph.settings, "skills_directory", original_directory)
    skill_catalog.refresh()


def test_catalog_skips_invalid_skill_and_lists_valid_skill(skill_environment: Path) -> None:
    """刷新时应保留有效 Skill，并隔离名称与目录不一致的无效项。"""
    _write_skill(skill_environment, "valid-skill")
    invalid = _write_skill(skill_environment, "invalid-folder")
    invalid_skill_file = invalid / "SKILL.md"
    invalid_skill_file.write_text(
        invalid_skill_file.read_text(encoding="utf-8").replace(
            "name: invalid-folder",
            "name: another-name",
        ),
        encoding="utf-8",
    )

    result = skill_catalog.refresh()

    assert result.loaded_count == 1
    assert result.skipped_count == 1
    assert [item.name for item in skill_catalog.list_summaries()] == ["valid-skill"]


def test_resource_read_rejects_traversal_and_symlink(
    skill_environment: Path,
    tmp_path: Path,
) -> None:
    """资源读取必须拒绝目录穿越与指向 Skill 外部的符号链接。"""
    directory = _write_skill(skill_environment, "secure-skill")
    references = directory / "references"
    references.mkdir()
    (references / "guide.md").write_text("安全参考资料", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("外部敏感内容", encoding="utf-8")
    (references / "outside.md").symlink_to(outside)
    skill_catalog.refresh()

    assert skill_catalog.read_resource("secure-skill", "references/guide.md") == "安全参考资料"
    with pytest.raises(SkillError, match="路径不合法"):
        skill_catalog.read_resource("secure-skill", "../outside.md")
    with pytest.raises(SkillError, match="符号链接"):
        skill_catalog.read_resource("secure-skill", "references/outside.md")


def test_activation_is_idempotent_and_limited(
    skill_environment: Path,
    monkeypatch,
) -> None:
    """重复激活应幂等，超过单次运行上限应拒绝。"""
    _write_skill(skill_environment, "first-skill")
    _write_skill(skill_environment, "second-skill")
    skill_catalog.refresh()
    monkeypatch.setattr(chat_graph.settings, "skills_max_activations_per_run", 1)

    activations, _, already_active = skill_service.activate("first-skill", [])
    same_activations, _, duplicate = skill_service.activate("first-skill", activations)

    assert not already_active
    assert duplicate
    assert same_activations == activations
    with pytest.raises(SkillError, match="数量已达上限"):
        skill_service.activate("second-skill", activations)


class FakeSkillModel(BaseChatModel):
    """先激活 Skill，再记录第二轮系统提示词的测试模型。"""

    skill_name: str
    received_system_prompt: str = ""

    @property
    def _llm_type(self) -> str:
        return "fake-skill-model"

    def bind_tools(self, tools: Any, **kwargs: Any):
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        system_message = next(
            message for message in messages if isinstance(message, SystemMessage)
        )
        if (
            any(isinstance(message, ToolMessage) for message in messages)
            or "<active_skills>" in str(system_message.content)
        ):
            self.received_system_prompt = str(system_message.content)
            response = AIMessage(content="已按 Skill 完成分析")
        else:
            response = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "activate_skill",
                        "args": {"name": self.skill_name},
                        "id": "call-skill",
                        "type": "tool_call",
                    }
                ],
            )
        return ChatResult(generations=[ChatGeneration(message=response)])


@pytest.mark.asyncio
async def test_graph_activates_skill_and_injects_body(
    skill_environment: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """激活成功后，下一轮模型应收到 Skill 正文及 skill_loaded 事件。"""
    body = "先定位最底层异常，再给出最小修复。"
    _write_skill(skill_environment, "debug-skill", body)
    skill_catalog.refresh()
    model = FakeSkillModel(skill_name="debug-skill")
    monkeypatch.setattr(
        chat_graph.model_provider,
        "get_chat_model",
        lambda model_name=None, **kwargs: model,
    )
    monkeypatch.setattr(chat_graph, "get_checkpointer", lambda: InMemorySaver())
    original_workspace_root = workspace_manager.root
    workspace_manager.root = (tmp_path / "workspaces").resolve()
    graph = chat_graph._build_graph()
    session_id = str(uuid.uuid4())
    graph_input = {
        "messages": [("user", "分析 Java 异常")],
        "user_id": 1,
        "session_id": session_id,
        "model_name": None,
        "agent_run_id": uuid.uuid4().hex,
        "tool_round": 0,
        "tool_call_signatures": {},
        "activated_skills": [],
        "active_skill_run_id": "",
    }
    custom_events: list[dict[str, Any]] = []
    try:
        async for stream_mode, chunk in graph.astream(
            graph_input,
            config={"configurable": {"thread_id": f"1:{session_id}"}},
            stream_mode=["updates", "custom"],
        ):
            if stream_mode == "custom" and isinstance(chunk, dict):
                custom_events.append(chunk)
    finally:
        workspace_manager.root = original_workspace_root

    assert body in model.received_system_prompt
    assert any(
        event.get("tool_event", {}).get("event_type") == "skill_loaded"
        for event in custom_events
    )


@pytest.mark.asyncio
async def test_graph_uses_preselected_skill_before_first_model_call(
    skill_environment: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """前端主动选择的 Skill 应在首次模型调用前完成注入。"""
    body = "严格按照实验报告结构输出。"
    _write_skill(skill_environment, "report-skill", body)
    skill_catalog.refresh()
    activations, _, _ = skill_service.activate("report-skill", [])
    model = FakeSkillModel(skill_name="report-skill")
    monkeypatch.setattr(
        chat_graph.model_provider,
        "get_chat_model",
        lambda model_name=None, **kwargs: model,
    )
    monkeypatch.setattr(chat_graph, "get_checkpointer", lambda: InMemorySaver())
    original_workspace_root = workspace_manager.root
    workspace_manager.root = (tmp_path / "workspaces").resolve()
    graph = chat_graph._build_graph()
    session_id = str(uuid.uuid4())
    run_id = uuid.uuid4().hex
    graph_input = {
        "messages": [("user", "生成实验报告")],
        "user_id": 1,
        "session_id": session_id,
        "model_name": None,
        "agent_run_id": run_id,
        "tool_round": 0,
        "tool_call_signatures": {},
        "activated_skills": activations,
        "active_skill_run_id": run_id,
    }
    custom_events: list[dict[str, Any]] = []
    try:
        async for stream_mode, chunk in graph.astream(
            graph_input,
            config={"configurable": {"thread_id": f"1:{session_id}"}},
            stream_mode=["updates", "custom"],
        ):
            if stream_mode == "custom" and isinstance(chunk, dict):
                custom_events.append(chunk)
    finally:
        workspace_manager.root = original_workspace_root

    assert body in model.received_system_prompt
    assert any(
        event.get("tool_event", {}).get("event_type") == "skill_loaded"
        for event in custom_events
    )
