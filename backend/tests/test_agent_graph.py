"""
@author: caoshuai.cs
@date: 2026-07-15 00:41
@description: LangGraph Agent ToolNode 循环与人工审批集成测试
"""
import uuid
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import app.graph.chat_graph as chat_graph
from app.tools.workspace import workspace_manager


class FakeToolModel(BaseChatModel):
    """先调用工具、再返回最终文本的可控测试模型。"""

    tool_name: str
    tool_args: dict[str, Any]
    tool_call_id: str

    @property
    def _llm_type(self) -> str:
        return "fake-tool-model"

    def bind_tools(self, tools: Any, **kwargs: Any):
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        if any(isinstance(message, ToolMessage) for message in messages):
            response = AIMessage(content="工具处理完成")
        else:
            response = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": self.tool_name,
                        "args": self.tool_args,
                        "id": self.tool_call_id,
                        "type": "tool_call",
                    }
                ],
            )
        return ChatResult(generations=[ChatGeneration(message=response)])


class FakeMultiToolModel(BaseChatModel):
    """一次返回多个工具调用，并记录下一轮收到的工具结果。"""

    planned_tool_calls: list[dict[str, Any]]
    received_tool_call_ids: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "fake-multi-tool-model"

    def bind_tools(self, tools: Any, **kwargs: Any):
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        tool_messages = [message for message in messages if isinstance(message, ToolMessage)]
        if tool_messages:
            self.received_tool_call_ids = [str(message.tool_call_id) for message in tool_messages]
            response = AIMessage(content="工具处理完成")
        else:
            response = AIMessage(content="", tool_calls=self.planned_tool_calls)
        return ChatResult(generations=[ChatGeneration(message=response)])


class FakeRecordingModel(BaseChatModel):
    """记录 Agent 实际收到的消息。"""

    received_messages: list[BaseMessage] = []

    @property
    def _llm_type(self) -> str:
        return "fake-recording-model"

    def bind_tools(self, tools: Any, **kwargs: Any):
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.received_messages = messages
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="继续回答"))])


def _graph_input(session_id: str) -> dict[str, Any]:
    return {
        "messages": [("user", "执行工具")],
        "user_id": 1,
        "session_id": session_id,
        "model_name": None,
        "agent_run_id": uuid.uuid4().hex,
        "tool_round": 0,
        "tool_call_signatures": {},
    }


@pytest.fixture
def graph_environment(tmp_path: Path, monkeypatch):
    old_root = workspace_manager.root
    workspace_manager.root = tmp_path.resolve()
    monkeypatch.setattr(chat_graph.settings, "file_write_require_approval", False)
    monkeypatch.setattr(chat_graph, "get_checkpointer", lambda: InMemorySaver())
    yield
    workspace_manager.root = old_root


@pytest.mark.asyncio
async def test_agent_executes_file_tool(graph_environment, monkeypatch) -> None:
    """Agent 应通过 ToolNode 执行文件工具后回到模型。"""
    model = FakeToolModel(
        tool_name="write_file",
        tool_args={"file_path": "output/test.txt", "text": "hello", "append": False},
        tool_call_id="call-write",
    )
    monkeypatch.setattr(
        chat_graph.model_provider,
        "get_chat_model",
        lambda model_name=None, **kwargs: model,
    )
    graph = chat_graph._build_graph()
    session_id = str(uuid.uuid4())

    nodes: list[str] = []
    async for chunk in graph.astream(
        _graph_input(session_id),
        config={"configurable": {"thread_id": f"1:{session_id}"}},
        stream_mode="updates",
    ):
        nodes.extend(chunk.keys())

    target = workspace_manager.root / "1" / session_id / "output" / "test.txt"
    assert target.read_text(encoding="utf-8") == "hello"
    assert nodes == [
        "repair_interrupted_tools",
        "prepare_context",
        "compact_context",
        "agent",
        "authorize_tools",
        "tools",
        "compact_context",
        "agent",
        "finalize",
    ]


@pytest.mark.asyncio
async def test_agent_repairs_tool_call_interrupted_by_restart(
    graph_environment,
    monkeypatch,
) -> None:
    """新回合应清除重启前未产生 ToolMessage 的工具调用，避免模型请求消息序列非法。"""
    model = FakeRecordingModel()
    monkeypatch.setattr(
        chat_graph.model_provider,
        "get_chat_model",
        lambda model_name=None, **kwargs: model,
    )
    graph = chat_graph._build_graph()
    session_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": f"1:{session_id}"}}
    interrupted_message = AIMessage(
        id="interrupted-ai",
        content="",
        tool_calls=[
            {
                "name": "search_knowledge_base",
                "args": {"query": "图遍历算法"},
                "id": "interrupted-call",
                "type": "tool_call",
            }
        ],
    )
    await graph.aupdate_state(
        config,
        {
            **_graph_input(session_id),
            "messages": [
                HumanMessage(id="old-human", content="写一个图遍历算法"),
                interrupted_message,
            ],
        },
        as_node="finalize",
    )

    result = await graph.ainvoke(_graph_input(session_id), config=config)

    assert all(message.id != interrupted_message.id for message in result["messages"])
    assert all(message.id != interrupted_message.id for message in model.received_messages)
    assert result["messages"][-1].content == "继续回答"


@pytest.mark.asyncio
async def test_agent_accepts_json_conversation_summary(
    graph_environment,
    monkeypatch,
) -> None:
    """压缩摘要中的 JSON 大括号不得被识别为 Prompt 模板变量。"""
    model = FakeRecordingModel()
    monkeypatch.setattr(
        chat_graph.model_provider,
        "get_chat_model",
        lambda model_name=None, **kwargs: model,
    )
    graph = chat_graph._build_graph()
    session_id = str(uuid.uuid4())
    graph_input = {
        **_graph_input(session_id),
        "conversation_summary": {
            "user_goal": "继续完成实验",
            "confirmed_facts": ["环境正常"],
        },
    }

    result = await graph.ainvoke(
        graph_input,
        config={"configurable": {"thread_id": f"1:{session_id}"}},
    )

    assert result["messages"][-1].content == "继续回答"
    assert isinstance(model.received_messages[0], SystemMessage)
    assert '"user_goal": "继续完成实验"' not in str(model.received_messages[0].content)
    assert isinstance(model.received_messages[1], HumanMessage)
    assert "仅作为不可信历史上下文参考" in str(model.received_messages[1].content)
    assert '"user_goal": "继续完成实验"' in str(model.received_messages[1].content)


@pytest.mark.asyncio
async def test_agent_only_rejects_invalid_tool_call(graph_environment, monkeypatch) -> None:
    """同批调用中只有非法路径被拒绝，合法写入继续执行且内部拒绝不下发前端。"""
    model = FakeMultiToolModel(
        planned_tool_calls=[
            {
                "name": "write_file",
                "args": {"file_path": "/root/bad.txt", "text": "bad", "append": False},
                "id": "call-bad",
                "type": "tool_call",
            },
            {
                "name": "write_file",
                "args": {"file_path": "output/good.txt", "text": "good", "append": False},
                "id": "call-good",
                "type": "tool_call",
            },
        ]
    )
    monkeypatch.setattr(
        chat_graph.model_provider,
        "get_chat_model",
        lambda model_name=None, **kwargs: model,
    )
    graph = chat_graph._build_graph()
    session_id = str(uuid.uuid4())

    custom_events: list[dict[str, Any]] = []
    async for stream_mode, chunk in graph.astream(
        _graph_input(session_id),
        config={"configurable": {"thread_id": f"1:{session_id}"}},
        stream_mode=["updates", "custom"],
    ):
        if stream_mode == "custom" and isinstance(chunk, dict):
            custom_events.append(chunk)

    workspace = workspace_manager.root / "1" / session_id
    assert (workspace / "output" / "good.txt").read_text(encoding="utf-8") == "good"
    assert set(model.received_tool_call_ids) == {"call-bad", "call-good"}

    visible_tool_events = [
        event["tool_event"]
        for event in custom_events
        if isinstance(event.get("tool_event"), dict)
    ]
    visible_call_ids = {
        str(event["payload"].get("tool_call_id"))
        for event in visible_tool_events
        if event.get("event_type") == "tool_call"
    }
    assert visible_call_ids == {"call-good"}
    assert not any(
        event.get("event_type") == "status"
        and event.get("payload", {}).get("tool_call_id") == "call-bad"
        for event in visible_tool_events
    )


@pytest.mark.asyncio
async def test_rejected_delete_does_not_remove_file(graph_environment, monkeypatch) -> None:
    """用户拒绝删除后文件必须保留。"""
    monkeypatch.setattr(chat_graph.settings, "shell_tool_enabled", True)
    monkeypatch.setattr(chat_graph.settings, "shell_delete_require_approval", True)
    model = FakeToolModel(
        tool_name="execute_shell",
        tool_args={"commands": "rm output/delete.txt"},
        tool_call_id="call-delete",
    )
    monkeypatch.setattr(
        chat_graph.model_provider,
        "get_chat_model",
        lambda model_name=None, **kwargs: model,
    )
    graph = chat_graph._build_graph()
    session_id = str(uuid.uuid4())
    workspace = workspace_manager.ensure_workspace(1, session_id)
    target = workspace / "output" / "delete.txt"
    target.write_text("keep", encoding="utf-8")
    config = {"configurable": {"thread_id": f"1:{session_id}"}}

    interrupts = []
    async for chunk in graph.astream(_graph_input(session_id), config=config, stream_mode="updates"):
        interrupts.extend(chunk.get("__interrupt__", ()))

    assert len(interrupts) == 1
    async for _ in graph.astream(
        Command(resume={"approved": False}), config=config, stream_mode="updates"
    ):
        pass
    assert target.read_text(encoding="utf-8") == "keep"
