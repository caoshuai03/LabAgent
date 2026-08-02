"""
@author: caoshuai.cs
@date: 2026-07-25
@description: Ollama Endpoint 选择、精简失败日志、聊天与 Embedding 安全重试测试
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from ollama import ResponseError

from app.services.ollama_load_balancer import (
    LoadBalancedChatOllama,
    LoadBalancedOllamaEmbeddings,
    OllamaEndpointPool,
)
from app.services.model_provider import ModelProvider
from app.core.config import settings


def _chat_result(content: str) -> ChatResult:
    """构造可控的聊天模型结果。"""
    return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])


def test_endpoint_pool_uses_least_in_flight_then_round_robin() -> None:
    """优先选择进行中请求最少的节点，负载相同时按顺序轮询。"""
    pool = OllamaEndpointPool(["http://ollama-a:11434", "http://ollama-b:11434"])

    first = pool.acquire()
    second = pool.acquire()
    first.release()
    third = pool.acquire()

    assert first.endpoint_url == "http://ollama-a:11434"
    assert second.endpoint_url == "http://ollama-b:11434"
    assert third.endpoint_url == "http://ollama-a:11434"

    second.release()
    third.release()
    fourth = pool.acquire()
    assert fourth.endpoint_url == "http://ollama-b:11434"
    fourth.release()


def test_endpoint_pool_rejects_unsafe_url() -> None:
    """Endpoint 配置禁止凭据、路径和非 HTTP 协议。"""
    with pytest.raises(ValueError, match="无效的 Ollama Endpoint"):
        OllamaEndpointPool(["http://user:password@ollama-a:11434/api"])


def test_model_provider_uses_configured_endpoint_list(monkeypatch) -> None:
    """ModelProvider 应优先读取多实例配置，并让聊天与 Embedding 共用 Endpoint 池。"""
    monkeypatch.setattr(
        settings,
        "ollama_base_urls",
        "http://ollama-a:11434,http://ollama-b:11434",
    )
    provider = ModelProvider()

    chat_model = provider.get_chat_model()
    embedding_model = provider.get_embedding_model()

    assert isinstance(chat_model, LoadBalancedChatOllama)
    assert isinstance(embedding_model, LoadBalancedOllamaEmbeddings)
    assert chat_model.endpoint_pool is embedding_model.endpoint_pool
    assert chat_model.endpoint_pool.endpoint_urls == (
        "http://ollama-a:11434",
        "http://ollama-b:11434",
    )


@pytest.mark.asyncio
async def test_auto_model_uses_ollama_when_target_model_exists(monkeypatch) -> None:
    """AUTO 探测到目标模型时应使用 Ollama，并固定使用两秒超时。"""
    monkeypatch.setattr(settings, "ollama_base_urls", "http://ollama-a:11434")
    provider = ModelProvider()
    original_async_client = httpx.AsyncClient
    configured_timeouts: list[float] = []

    async def handle_request(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={"models": [{"name": settings.ollama_chat_model}]},
        )

    def build_client(*, timeout: float) -> httpx.AsyncClient:
        configured_timeouts.append(timeout)
        return original_async_client(
            timeout=timeout,
            transport=httpx.MockTransport(handle_request),
        )

    monkeypatch.setattr(
        "app.services.model_provider.httpx.AsyncClient",
        build_client,
    )

    resolved_model = await provider.resolve_chat_model_name("auto")

    assert resolved_model == settings.ollama_chat_model
    assert configured_timeouts == [2.0]


@pytest.mark.asyncio
async def test_auto_model_uses_azure_when_ollama_model_is_unavailable(monkeypatch) -> None:
    """AUTO 未探测到目标模型时应回退到配置的 Azure 模型。"""
    monkeypatch.setattr(settings, "ollama_base_urls", "http://ollama-a:11434")
    provider = ModelProvider()
    original_async_client = httpx.AsyncClient

    async def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "other-model"}]})

    monkeypatch.setattr(
        "app.services.model_provider.httpx.AsyncClient",
        lambda *, timeout: original_async_client(
            timeout=timeout,
            transport=httpx.MockTransport(handle_request),
        ),
    )

    resolved_model = await provider.resolve_chat_model_name("auto")

    assert resolved_model == settings.azure_chat_model


@pytest.mark.asyncio
async def test_context_window_uses_smallest_loaded_ollama_window(monkeypatch) -> None:
    """多实例实际窗口不一致时必须取最小值，避免负载均衡后请求溢出。"""
    monkeypatch.setattr(
        settings,
        "ollama_base_urls",
        "http://ollama-a:11434,http://ollama-b:11434",
    )
    monkeypatch.setattr(settings, "model_context_windows", {})
    provider = ModelProvider()
    original_async_client = httpx.AsyncClient

    async def handle_request(request: httpx.Request) -> httpx.Response:
        context_length = 65_536 if request.url.host == "ollama-a" else 32_768
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": settings.ollama_chat_model,
                        "context_length": context_length,
                    }
                ]
            },
        )

    monkeypatch.setattr(
        "app.services.model_provider.httpx.AsyncClient",
        lambda *, timeout: original_async_client(
            timeout=timeout,
            transport=httpx.MockTransport(handle_request),
        ),
    )

    context_window = await provider.resolve_context_window(settings.ollama_chat_model)

    assert context_window == 32_768


@pytest.mark.asyncio
async def test_context_window_uses_fallback_for_unloaded_ollama_endpoint(
    monkeypatch,
) -> None:
    """任一负载均衡节点尚未加载模型时，该节点必须按保守窗口参与计算。"""
    monkeypatch.setattr(
        settings,
        "ollama_base_urls",
        "http://ollama-a:11434,http://ollama-b:11434",
    )
    monkeypatch.setattr(settings, "model_context_windows", {})
    monkeypatch.setattr(settings, "model_context_window_fallback", 32_768)
    provider = ModelProvider()
    original_async_client = httpx.AsyncClient

    async def handle_request(request: httpx.Request) -> httpx.Response:
        models = (
            [{"name": settings.ollama_chat_model, "context_length": 65_536}]
            if request.url.host == "ollama-a"
            else []
        )
        return httpx.Response(200, json={"models": models})

    monkeypatch.setattr(
        "app.services.model_provider.httpx.AsyncClient",
        lambda *, timeout: original_async_client(
            timeout=timeout,
            transport=httpx.MockTransport(handle_request),
        ),
    )

    context_window = await provider.resolve_context_window(settings.ollama_chat_model)

    assert context_window == 32_768


@pytest.mark.asyncio
async def test_context_window_prefers_explicit_model_configuration(monkeypatch) -> None:
    """显式模型窗口用于无法查询运行状态的外部模型，且不得访问 Ollama。"""
    monkeypatch.setattr(
        settings,
        "model_context_windows",
        {"gpt-5.5-2026-04-24": 200_000},
    )
    provider = ModelProvider()

    context_window = await provider.resolve_context_window("gpt-5.5-2026-04-24")

    assert context_window == 200_000


@pytest.mark.asyncio
async def test_embedding_model_availability_checks_configured_model(monkeypatch) -> None:
    """Embedding 预检应校验模型列表中存在当前配置的模型。"""
    monkeypatch.setattr(settings, "ollama_base_urls", "http://ollama-a:11434")
    provider = ModelProvider()
    original_async_client = httpx.AsyncClient

    async def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"models": [{"model": settings.ollama_embedding_model}]},
        )

    monkeypatch.setattr(
        "app.services.model_provider.httpx.AsyncClient",
        lambda *, timeout: original_async_client(
            timeout=timeout,
            transport=httpx.MockTransport(handle_request),
        ),
    )

    assert await provider.embedding_model_available() is True


@pytest.mark.asyncio
async def test_chat_does_not_retry_other_endpoint_by_default(monkeypatch) -> None:
    """默认关闭跨节点失败重试，首次失败应直接返回异常。"""
    pool = OllamaEndpointPool(["http://ollama-a:11434", "http://ollama-b:11434"])
    model = LoadBalancedChatOllama(
        model="qwen3.5:35b",
        endpoint_pool=pool,
        operation_name="query_rewrite",
    )
    called_urls: list[str] = []

    class _Delegate:
        def __init__(self, endpoint_url: str) -> None:
            self.endpoint_url = endpoint_url

        async def _agenerate(self, *args: Any, **kwargs: Any) -> ChatResult:
            called_urls.append(self.endpoint_url)
            raise httpx.ConnectTimeout("连接超时")

    monkeypatch.setattr(
        LoadBalancedChatOllama,
        "_build_delegate",
        lambda self, endpoint_url: _Delegate(endpoint_url),
    )

    with pytest.raises(httpx.ConnectTimeout):
        await model.ainvoke([HumanMessage(content="测试")])

    assert called_urls == ["http://ollama-a:11434"]


@pytest.mark.asyncio
async def test_chat_logs_non_retryable_400_response(monkeypatch, caplog) -> None:
    """Ollama 4xx 不重试，但必须记录节点、状态码和精简原因。"""
    pool = OllamaEndpointPool(["http://ollama-a:11434"])
    model = LoadBalancedChatOllama(
        model="qwen3.5:35b",
        endpoint_pool=pool,
        operation_name="memory_extraction",
    )

    class _Delegate:
        async def _agenerate(self, *args: Any, **kwargs: Any) -> ChatResult:
            raise ResponseError("不支持结构化输出参数", 400)

    monkeypatch.setattr(
        LoadBalancedChatOllama,
        "_build_delegate",
        lambda self, endpoint_url: _Delegate(),
    )

    with caplog.at_level(logging.WARNING, logger="labagent"):
        with pytest.raises(ResponseError):
            await model.ainvoke([HumanMessage(content="测试")])

    assert "operation=memory_extraction" in caplog.text
    assert "endpoint=http://ollama-a:11434" in caplog.text
    assert "status_code=400" in caplog.text
    assert "error_type=ResponseError" in caplog.text
    assert "error=不支持结构化输出参数" in caplog.text


@pytest.mark.asyncio
async def test_chat_retries_other_endpoint_on_connect_error(monkeypatch, caplog) -> None:
    """首响应前连接失败时应切换另一个节点重试一次。"""
    pool = OllamaEndpointPool(
        ["http://ollama-a:11434", "http://ollama-b:11434"],
        retry_other_endpoint_on_failure=True,
    )
    model = LoadBalancedChatOllama(
        model="qwen3.5:35b",
        endpoint_pool=pool,
        operation_name="agent",
    )
    called_urls: list[str] = []

    class _Delegate:
        def __init__(self, endpoint_url: str) -> None:
            self.endpoint_url = endpoint_url

        async def _agenerate(self, *args: Any, **kwargs: Any) -> ChatResult:
            called_urls.append(self.endpoint_url)
            if self.endpoint_url == "http://ollama-a:11434":
                raise httpx.ConnectError("连接失败")
            return _chat_result("成功")

    monkeypatch.setattr(
        LoadBalancedChatOllama,
        "_build_delegate",
        lambda self, endpoint_url: _Delegate(endpoint_url),
    )

    bound_model = model.bind_tools(
        [
            {
                "type": "function",
                "function": {
                    "name": "test_tool",
                    "description": "测试工具",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
    )
    with caplog.at_level(logging.WARNING, logger="labagent"):
        result = await bound_model.ainvoke([HumanMessage(content="测试")])

    assert result.content == "成功"
    assert called_urls == ["http://ollama-a:11434", "http://ollama-b:11434"]
    assert "operation=agent" in caplog.text
    assert "endpoint=http://ollama-a:11434" in caplog.text
    assert "model=qwen3.5:35b" in caplog.text
    assert "error_type=ConnectError" in caplog.text
    assert "emitted=unknown" in caplog.text
    assert "进入故障冷却" not in caplog.text


@pytest.mark.asyncio
async def test_stream_does_not_retry_after_first_chunk(monkeypatch) -> None:
    """流式调用已经产生内容后发生故障，不得切换节点造成重复输出。"""
    pool = OllamaEndpointPool(
        ["http://ollama-a:11434", "http://ollama-b:11434"],
        retry_other_endpoint_on_failure=True,
    )
    model = LoadBalancedChatOllama(model="qwen3.5:35b", endpoint_pool=pool)
    called_urls: list[str] = []

    class _Delegate:
        def __init__(self, endpoint_url: str) -> None:
            self.endpoint_url = endpoint_url

        async def _astream(self, *args: Any, **kwargs: Any) -> AsyncIterator[ChatGenerationChunk]:
            called_urls.append(self.endpoint_url)
            yield ChatGenerationChunk(message=AIMessageChunk(content="部分内容"))
            raise httpx.ConnectError("流式连接中断")

    monkeypatch.setattr(
        LoadBalancedChatOllama,
        "_build_delegate",
        lambda self, endpoint_url: _Delegate(endpoint_url),
    )

    chunks: list[str] = []
    with pytest.raises(httpx.ConnectError):
        async for chunk in model._astream([HumanMessage(content="测试")]):
            chunks.append(chunk.text)

    assert chunks == ["部分内容"]
    assert called_urls == ["http://ollama-a:11434"]


@pytest.mark.asyncio
async def test_cancelled_chat_releases_endpoint(monkeypatch) -> None:
    """调用取消时必须释放进行中计数，避免节点永久被视为繁忙。"""
    pool = OllamaEndpointPool(["http://ollama-a:11434", "http://ollama-b:11434"])
    model = LoadBalancedChatOllama(model="qwen3.5:35b", endpoint_pool=pool)
    started = asyncio.Event()

    class _Delegate:
        async def _agenerate(self, *args: Any, **kwargs: Any) -> ChatResult:
            started.set()
            await asyncio.Event().wait()
            return _chat_result("不会返回")

    monkeypatch.setattr(
        LoadBalancedChatOllama,
        "_build_delegate",
        lambda self, endpoint_url: _Delegate(),
    )

    task = asyncio.create_task(model.ainvoke([HumanMessage(content="测试取消")]))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    next_lease = pool.acquire()
    assert next_lease.endpoint_url == "http://ollama-b:11434"
    next_lease.release()
    following_lease = pool.acquire()
    assert following_lease.endpoint_url == "http://ollama-a:11434"
    following_lease.release()


def test_embedding_retries_other_endpoint_on_connect_error(monkeypatch) -> None:
    """Embedding 连接失败时应切换另一个节点重试。"""
    pool = OllamaEndpointPool(
        ["http://ollama-a:11434", "http://ollama-b:11434"],
        retry_other_endpoint_on_failure=True,
    )
    embeddings = LoadBalancedOllamaEmbeddings(
        model="turingdance/gte-large-zh:latest",
        endpoint_pool=pool,
    )
    called_urls: list[str] = []

    class _Delegate:
        def __init__(self, endpoint_url: str) -> None:
            self.endpoint_url = endpoint_url

        def embed_query(self, text: str) -> list[float]:
            called_urls.append(self.endpoint_url)
            if self.endpoint_url == "http://ollama-a:11434":
                raise httpx.ConnectError("连接失败")
            return [1.0, 2.0]

    monkeypatch.setattr(
        LoadBalancedOllamaEmbeddings,
        "_build_delegate",
        lambda self, endpoint_url: _Delegate(endpoint_url),
    )

    result = embeddings.embed_query("测试")

    assert result == [1.0, 2.0]
    assert called_urls == ["http://ollama-a:11434", "http://ollama-b:11434"]
