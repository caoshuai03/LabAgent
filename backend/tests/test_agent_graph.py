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
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import app.graph.chat_graph as chat_graph
from app.services import rag_retrieval
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


async def _empty_retrieve(question: str) -> list:
    return []


async def _empty_rerank(question: str, documents: list) -> list:
    return []


def _graph_input(session_id: str) -> dict[str, Any]:
    return {
        "messages": [("user", "执行工具")],
        "user_id": 1,
        "user_role": 0,
        "session_id": session_id,
        "model_name": None,
        "agent_run_id": uuid.uuid4().hex,
        "tool_round": 0,
        "documents": [],
        "sources": [],
    }


@pytest.fixture
def graph_environment(tmp_path: Path, monkeypatch):
    old_root = workspace_manager.root
    workspace_manager.root = tmp_path.resolve()
    monkeypatch.setattr(chat_graph.settings, "file_write_require_approval", False)
    monkeypatch.setattr(chat_graph, "get_checkpointer", lambda: InMemorySaver())
    monkeypatch.setattr(rag_retrieval, "retrieve", _empty_retrieve)
    monkeypatch.setattr(rag_retrieval, "rerank", _empty_rerank)
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
    monkeypatch.setattr(chat_graph.model_provider, "get_chat_model", lambda model_name=None: model)
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
        "prepare_context", "retrieve", "rerank", "agent", "authorize_tools",
        "tools", "agent", "finalize",
    ]


@pytest.mark.asyncio
async def test_rejected_delete_does_not_remove_file(graph_environment, monkeypatch) -> None:
    """用户拒绝删除后文件必须保留。"""
    model = FakeToolModel(
        tool_name="file_delete",
        tool_args={"file_path": "output/delete.txt"},
        tool_call_id="call-delete",
    )
    monkeypatch.setattr(chat_graph.model_provider, "get_chat_model", lambda model_name=None: model)
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
