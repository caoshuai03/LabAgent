"""
@author: caoshuai.cs
@date: 2026-07-17 05:17
@description: RAG 检索同步 PGVector 调用与知识库工具异常日志测试
"""
import asyncio
import json
import logging

import pytest
from langchain_core.documents import Document
from langchain_ollama import ChatOllama

from app.services import rag_retrieval
from app.services.model_provider import model_provider
from app.tools import knowledge_tool


class _SyncRetriever:
    """仅支持同步调用的检索器，用于约束同步 PGVector 调用方式。"""

    def invoke(self, query: str) -> list[Document]:
        return [Document(page_content=query, metadata={"source": "test.pdf"})]

    async def ainvoke(self, query: str) -> list[Document]:
        raise AssertionError("不应调用异步检索接口")


class _SlowReranker:
    """持续等待的可控 reranker，用于验证独立超时。"""

    async def acompress_documents(
        self, documents: list[Document], query: str
    ) -> list[Document]:
        await asyncio.Event().wait()
        return documents


@pytest.mark.asyncio
async def test_retrieve_uses_sync_retriever_in_thread(monkeypatch) -> None:
    """同步 PGVector 组合检索器必须通过 invoke 在线程中执行。"""
    monkeypatch.setattr(rag_retrieval, "_build_retriever", lambda: _SyncRetriever())

    documents = await rag_retrieval.retrieve("平摊分析")

    assert [document.page_content for document in documents] == ["平摊分析"]


@pytest.mark.asyncio
async def test_rerank_has_independent_timeout(monkeypatch, caplog) -> None:
    """rerank 长时间不返回时应独立超时并退化为粗召回顺序。"""
    monkeypatch.setattr(rag_retrieval.settings, "rag_rerank_timeout_seconds", 0.01)
    monkeypatch.setattr(
        rag_retrieval.LLMListwiseRerank,
        "from_llm",
        lambda **kwargs: _SlowReranker(),
    )
    documents = [Document(page_content="平摊分析", metadata={"source": "test.pdf"})]

    with caplog.at_level(logging.WARNING, logger="labagent"):
        reranked = await rag_retrieval.rerank("平摊分析", documents)

    assert reranked == documents
    assert "RAG rerank 超时" in caplog.text


def test_local_rerank_model_disables_reasoning_and_limits_output(monkeypatch) -> None:
    """本地 rerank 模型应关闭思考并限制结构化排序输出长度。"""
    monkeypatch.setattr(rag_retrieval.settings, "rag_rerank_model", "")
    monkeypatch.setattr(rag_retrieval.settings, "ollama_chat_model", "qwen3:8b")
    monkeypatch.setattr(rag_retrieval.settings, "rag_rerank_num_predict", 64)

    model = model_provider.get_rerank_model()

    assert isinstance(model, ChatOllama)
    assert model.reasoning is False
    assert model.num_predict == 64
    assert model.temperature == 0


def test_local_query_rewrite_model_is_independent_from_rerank(monkeypatch) -> None:
    """MultiQuery 查询改写应使用独立模型配置，不复用 rerank 模型。"""
    monkeypatch.setattr(rag_retrieval.settings, "rag_query_rewrite_model", "qwen3:4b")
    monkeypatch.setattr(rag_retrieval.settings, "rag_rerank_model", "qwen3:8b")

    model = model_provider.get_query_rewrite_model()

    assert isinstance(model, ChatOllama)
    assert model.model == "qwen3:4b"
    assert model.reasoning is False
    assert model.temperature == 0


@pytest.mark.asyncio
async def test_knowledge_tool_logs_retrieval_exception(monkeypatch, caplog) -> None:
    """知识库检索异常应记录堆栈并返回失败状态，便于定位降级原因。"""
    async def _failed_retrieve(query: str) -> list[Document]:
        raise AssertionError("_async_engine not found")

    monkeypatch.setattr(knowledge_tool.rag_retrieval, "retrieve", _failed_retrieve)

    with caplog.at_level(logging.ERROR, logger="labagent"):
        result = await knowledge_tool.search_knowledge_base.coroutine(
            query="平摊分析",
            tool_call_id="test-call",
        )

    payload = json.loads(result)
    assert payload["success"] is False
    assert payload["error"] == "_async_engine not found"
    assert "知识库检索失败，已降级: query_len=4" in caplog.text
