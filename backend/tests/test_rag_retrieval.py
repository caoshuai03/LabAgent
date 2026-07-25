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


class _FakeVectorRetriever:
    """记录同步向量检索调用的假检索器。"""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def invoke(self, query: str) -> list[Document]:
        self.queries.append(query)
        return [Document(page_content="黄金证据", metadata={"source": "baseline.md"})]


class _FakeHybridRetriever:
    """假混合检索器，用于验证 MultiQuery 构建参数。"""

    pass


class _FakeHybridInvoker:
    """按查询返回固定排序结果的假混合检索器。"""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def invoke(self, query: str) -> list[Document]:
        self.queries.append(query)
        docs = {
            "原问题": [
                Document(page_content="A", metadata={"source": "origin-a.md"}),
                Document(page_content="B", metadata={"source": "origin-b.md"}),
            ],
            "改写一": [
                Document(page_content="B", metadata={"source": "rewrite-b.md"}),
                Document(page_content="C", metadata={"source": "rewrite-c.md"}),
            ],
            "改写二": [
                Document(page_content="B", metadata={"source": "rewrite-b.md"}),
                Document(page_content="D", metadata={"source": "rewrite-d.md"}),
            ],
        }
        return docs[query]


class _FakeLlmChain:
    """返回固定 MultiQuery 改写。"""

    def invoke(self, payload: dict[str, str]) -> list[str]:
        return ["改写一", "改写二"]


class _FakeMultiQueryRetriever:
    """只暴露 RRF 融合测试需要的属性。"""

    def __init__(self) -> None:
        self.retriever = _FakeHybridInvoker()
        self.llm_chain = _FakeLlmChain()


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


def test_multi_query_retriever_includes_original_and_two_rewrites(monkeypatch) -> None:
    """当前检索链路应使用原问题 + 2 个改写进入混合召回。"""
    captured: dict[str, object] = {}

    def _fake_from_llm(**kwargs):
        captured.update(kwargs)
        return _SyncRetriever()

    monkeypatch.setattr(rag_retrieval.settings, "rag_multi_query_count", 2)
    monkeypatch.setattr(rag_retrieval.rag_store, "build_hybrid_retriever", lambda **kwargs: _FakeHybridRetriever())
    monkeypatch.setattr(rag_retrieval.MultiQueryRetriever, "from_llm", _fake_from_llm)
    monkeypatch.setattr(rag_retrieval.model_provider, "get_query_rewrite_model", lambda: object())

    retriever = rag_retrieval._build_retriever()

    prompt = captured["prompt"]
    assert isinstance(retriever, _SyncRetriever)
    assert captured["include_original"] is True
    assert "生成 2 个检索问题" in prompt.format(question="实验三什么时候提交？")


def test_retrieve_with_query_rrf_fuses_original_and_rewrites(monkeypatch) -> None:
    """关闭 rerank 的评测召回应按原问题和改写结果做全局 RRF。"""
    fake_retriever = _FakeMultiQueryRetriever()
    monkeypatch.setattr(rag_retrieval, "_build_retriever", lambda: fake_retriever)

    documents = rag_retrieval._retrieve_with_query_rrf_sync("原问题")

    assert fake_retriever.retriever.queries == ["原问题", "改写一", "改写二"]
    assert [document.page_content for document in documents[:4]] == ["B", "A", "C", "D"]


@pytest.mark.asyncio
async def test_knowledge_tool_vector_only_uses_vector_retriever(monkeypatch) -> None:
    """评测 baseline 模式应只走纯向量检索，不触发混合召回与 rerank。"""
    called: dict[str, int] = {}
    retriever = _FakeVectorRetriever()

    def _build_vector_retriever(vector_top_k: int) -> _FakeVectorRetriever:
        called["top_k"] = vector_top_k
        return retriever

    async def _unexpected_retrieve(query: str) -> list[Document]:
        raise AssertionError("vector_only 不应调用混合召回")

    async def _unexpected_rerank(query: str, documents: list[Document]) -> list[Document]:
        raise AssertionError("vector_only 不应调用 rerank")

    monkeypatch.setattr(knowledge_tool.rag_store, "build_vector_retriever", _build_vector_retriever)
    monkeypatch.setattr(knowledge_tool.rag_retrieval, "retrieve", _unexpected_retrieve)
    monkeypatch.setattr(knowledge_tool.rag_retrieval, "rerank", _unexpected_rerank)

    result = await knowledge_tool.search_knowledge_base.coroutine(
        query="实验三提交要求",
        state={"rag_retrieval_mode": "vector_only", "rag_retrieval_top_k": 5},
        tool_call_id="test-call",
    )

    payload = json.loads(result)
    assert payload["success"] is True
    assert payload["summary"] == "命中 1 条知识库资料"
    assert called["top_k"] == 5
    assert retriever.queries == ["实验三提交要求"]


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
