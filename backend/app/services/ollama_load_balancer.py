"""
@author: caoshuai.cs
@date: 2026-07-25
@description: Ollama 双实例请求级负载均衡——最少进行中请求优先、平局轮询与安全重试
"""

import logging
import threading
import time
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import Any
from urllib.parse import urlsplit

import httpx
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_ollama import ChatOllama, OllamaEmbeddings
from ollama import ResponseError
from pydantic import ConfigDict, Field

logger = logging.getLogger("labagent")


class OllamaEndpointUnavailableError(RuntimeError):
    """没有可用 Ollama Endpoint。"""


class _EndpointState:
    """单个 Endpoint 的进程内运行状态。"""

    def __init__(self, url: str) -> None:
        self.url = url
        self.in_flight = 0


class OllamaEndpointLease:
    """一次模型调用占用的 Endpoint 租约，确保计数只释放一次。"""

    def __init__(self, pool: "OllamaEndpointPool", endpoint_url: str) -> None:
        self._pool = pool
        self.endpoint_url = endpoint_url
        self._released = False

    def release(self) -> None:
        """释放租约。"""
        if self._released:
            return
        self._released = True
        self._pool.release(self.endpoint_url)


class OllamaEndpointPool:
    """线程安全的进程内 Endpoint 池。"""

    def __init__(
        self,
        endpoint_urls: Sequence[str],
        *,
        retry_other_endpoint_on_failure: bool = False,
    ) -> None:
        normalized_urls = [self._normalize_url(url) for url in endpoint_urls if url.strip()]
        unique_urls = list(dict.fromkeys(normalized_urls))
        if not unique_urls:
            raise ValueError("至少需要配置一个 Ollama Endpoint")
        self._states = [_EndpointState(url) for url in unique_urls]
        self._retry_other_endpoint_on_failure = retry_other_endpoint_on_failure
        self._cursor = 0
        self._lock = threading.Lock()

    @staticmethod
    def _normalize_url(raw_url: str) -> str:
        """规范化并校验服务端配置的 Endpoint，拒绝路径、凭据和非 HTTP 协议。"""
        url = raw_url.strip().rstrip("/")
        parsed = urlsplit(url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(f"无效的 Ollama Endpoint: {raw_url}")
        return url

    @property
    def endpoint_urls(self) -> tuple[str, ...]:
        """返回已配置的 Endpoint。"""
        return tuple(state.url for state in self._states)

    @property
    def request_attempts(self) -> int:
        """返回单次模型调用允许尝试的 Endpoint 数量。"""
        return 2 if self._retry_other_endpoint_on_failure and len(self._states) > 1 else 1

    def can_retry(self, attempt: int) -> bool:
        """当前失败后是否还能改投另一 Endpoint。"""
        return attempt + 1 < self.request_attempts

    def acquire(self, *, excluded_urls: set[str] | None = None) -> OllamaEndpointLease:
        """选择最少进行中请求的可选节点，平局时按游标轮询。"""
        excluded = excluded_urls or set()
        with self._lock:
            candidates = [(index, state) for index, state in enumerate(self._states) if state.url not in excluded]
            if not candidates:
                raise OllamaEndpointUnavailableError("当前没有可用的 Ollama Endpoint")
            min_in_flight = min(state.in_flight for _, state in candidates)
            candidate_indexes = {index for index, state in candidates if state.in_flight == min_in_flight}
            selected_index = next(
                index
                for offset in range(len(self._states))
                if (index := (self._cursor + offset) % len(self._states)) in candidate_indexes
            )
            selected = self._states[selected_index]
            selected.in_flight += 1
            self._cursor = (selected_index + 1) % len(self._states)
            return OllamaEndpointLease(self, selected.url)

    def release(self, endpoint_url: str) -> None:
        """释放进行中计数。"""
        with self._lock:
            state = next(state for state in self._states if state.url == endpoint_url)
            state.in_flight = max(0, state.in_flight - 1)


def _is_endpoint_failure(exc: Exception) -> bool:
    """识别连接、传输和服务端故障，用于日志与可选故障重试。"""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, ResponseError) and (
        exc.status_code is None or exc.status_code >= 500 or exc.status_code == 404
    )


def _is_safe_non_stream_retry(exc: Exception) -> bool:
    """非流式聚合无法判断是否已产生 Token，只重试明确的建连前错误。"""
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, ResponseError) and (
        exc.status_code is None or exc.status_code >= 500 or exc.status_code == 404
    )


def _log_endpoint_failure(
    *,
    operation: str,
    endpoint_url: str,
    model_name: str,
    exc: Exception,
    emitted: bool | None,
    started: float,
) -> None:
    """每次失败只输出一条不含请求内容的精简诊断日志。"""
    error_message = str(exc).replace("\r", " ").replace("\n", " ")[:200]
    logger.warning(
        "Ollama调用失败: operation=%s, endpoint=%s, model=%s, error_type=%s, emitted=%s, cost=%dms, error=%s",
        operation,
        endpoint_url,
        model_name,
        type(exc).__name__,
        "unknown" if emitted is None else str(emitted).lower(),
        int((time.monotonic() - started) * 1000),
        error_message,
    )


class LoadBalancedChatOllama(ChatOllama):
    """每次实际调用动态选择 Endpoint 的 ChatOllama。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    endpoint_pool: OllamaEndpointPool = Field(exclude=True)
    operation_name: str = Field(default="chat", exclude=True)

    def _build_delegate(self, endpoint_url: str) -> ChatOllama:
        """用当前模型参数构造绑定单一 Endpoint 的原生 ChatOllama。"""
        model_options = self.model_dump(exclude={"endpoint_pool", "operation_name", "base_url"})
        return ChatOllama(**model_options, base_url=endpoint_url)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        last_error: Exception | None = None
        excluded_urls: set[str] = set()
        for attempt in range(self.endpoint_pool.request_attempts):
            try:
                lease = self.endpoint_pool.acquire(excluded_urls=excluded_urls)
            except OllamaEndpointUnavailableError:
                if last_error is not None:
                    raise last_error
                raise
            started = time.monotonic()
            try:
                result = self._build_delegate(lease.endpoint_url)._generate(
                    messages,
                    stop=stop,
                    run_manager=run_manager,
                    **kwargs,
                )
            except BaseException as exc:
                endpoint_failure = isinstance(exc, Exception) and _is_endpoint_failure(exc)
                retryable = isinstance(exc, Exception) and _is_safe_non_stream_retry(exc)
                if isinstance(exc, Exception) and endpoint_failure:
                    _log_endpoint_failure(
                        operation=self.operation_name,
                        endpoint_url=lease.endpoint_url,
                        model_name=self.model,
                        exc=exc,
                        emitted=None,
                        started=started,
                    )
                lease.release()
                if not isinstance(exc, Exception) or not retryable or not self.endpoint_pool.can_retry(attempt):
                    raise
                last_error = exc
                excluded_urls.add(lease.endpoint_url)
                continue
            lease.release()
            return result
        raise last_error or OllamaEndpointUnavailableError("Ollama 模型调用失败")

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        last_error: Exception | None = None
        excluded_urls: set[str] = set()
        for attempt in range(self.endpoint_pool.request_attempts):
            try:
                lease = self.endpoint_pool.acquire(excluded_urls=excluded_urls)
            except OllamaEndpointUnavailableError:
                if last_error is not None:
                    raise last_error
                raise
            started = time.monotonic()
            try:
                result = await self._build_delegate(lease.endpoint_url)._agenerate(
                    messages,
                    stop=stop,
                    run_manager=run_manager,
                    **kwargs,
                )
            except BaseException as exc:
                endpoint_failure = isinstance(exc, Exception) and _is_endpoint_failure(exc)
                retryable = isinstance(exc, Exception) and _is_safe_non_stream_retry(exc)
                if isinstance(exc, Exception) and endpoint_failure:
                    _log_endpoint_failure(
                        operation=self.operation_name,
                        endpoint_url=lease.endpoint_url,
                        model_name=self.model,
                        exc=exc,
                        emitted=None,
                        started=started,
                    )
                lease.release()
                if not isinstance(exc, Exception) or not retryable or not self.endpoint_pool.can_retry(attempt):
                    raise
                last_error = exc
                excluded_urls.add(lease.endpoint_url)
                continue
            lease.release()
            return result
        raise last_error or OllamaEndpointUnavailableError("Ollama 模型调用失败")

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        excluded_urls: set[str] = set()
        last_error: Exception | None = None
        for attempt in range(self.endpoint_pool.request_attempts):
            try:
                lease = self.endpoint_pool.acquire(excluded_urls=excluded_urls)
            except OllamaEndpointUnavailableError:
                if last_error is not None:
                    raise last_error
                raise
            started = time.monotonic()
            emitted = False
            try:
                for chunk in self._build_delegate(lease.endpoint_url)._stream(
                    messages,
                    stop=stop,
                    run_manager=run_manager,
                    **kwargs,
                ):
                    emitted = True
                    yield chunk
            except BaseException as exc:
                endpoint_failure = isinstance(exc, Exception) and _is_endpoint_failure(exc)
                if isinstance(exc, Exception) and endpoint_failure:
                    _log_endpoint_failure(
                        operation=self.operation_name,
                        endpoint_url=lease.endpoint_url,
                        model_name=self.model,
                        exc=exc,
                        emitted=emitted,
                        started=started,
                    )
                lease.release()
                if (
                    not isinstance(exc, Exception)
                    or emitted
                    or not endpoint_failure
                    or not self.endpoint_pool.can_retry(attempt)
                ):
                    raise
                last_error = exc
                excluded_urls.add(lease.endpoint_url)
                continue
            lease.release()
            return
        raise last_error or OllamaEndpointUnavailableError("Ollama 流式调用失败")

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        excluded_urls: set[str] = set()
        last_error: Exception | None = None
        for attempt in range(self.endpoint_pool.request_attempts):
            try:
                lease = self.endpoint_pool.acquire(excluded_urls=excluded_urls)
            except OllamaEndpointUnavailableError:
                if last_error is not None:
                    raise last_error
                raise
            started = time.monotonic()
            emitted = False
            try:
                async for chunk in self._build_delegate(lease.endpoint_url)._astream(
                    messages,
                    stop=stop,
                    run_manager=run_manager,
                    **kwargs,
                ):
                    emitted = True
                    yield chunk
            except BaseException as exc:
                endpoint_failure = isinstance(exc, Exception) and _is_endpoint_failure(exc)
                if isinstance(exc, Exception) and endpoint_failure:
                    _log_endpoint_failure(
                        operation=self.operation_name,
                        endpoint_url=lease.endpoint_url,
                        model_name=self.model,
                        exc=exc,
                        emitted=emitted,
                        started=started,
                    )
                lease.release()
                if (
                    not isinstance(exc, Exception)
                    or emitted
                    or not endpoint_failure
                    or not self.endpoint_pool.can_retry(attempt)
                ):
                    raise
                last_error = exc
                excluded_urls.add(lease.endpoint_url)
                continue
            lease.release()
            return
        raise last_error or OllamaEndpointUnavailableError("Ollama 流式调用失败")


class LoadBalancedOllamaEmbeddings(OllamaEmbeddings):
    """每次向量化调用动态选择 Endpoint 的 OllamaEmbeddings。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    endpoint_pool: OllamaEndpointPool = Field(exclude=True)

    def _build_delegate(self, endpoint_url: str) -> OllamaEmbeddings:
        """用当前参数构造绑定单一 Endpoint 的原生 Embedding 客户端。"""
        model_options = self.model_dump(exclude={"endpoint_pool", "base_url"})
        return OllamaEmbeddings(**model_options, base_url=endpoint_url)

    def _invoke_with_retry(self, method_name: str, payload: Any) -> Any:
        last_error: Exception | None = None
        excluded_urls: set[str] = set()
        for attempt in range(self.endpoint_pool.request_attempts):
            try:
                lease = self.endpoint_pool.acquire(excluded_urls=excluded_urls)
            except OllamaEndpointUnavailableError:
                if last_error is not None:
                    raise last_error
                raise
            started = time.monotonic()
            try:
                result = getattr(self._build_delegate(lease.endpoint_url), method_name)(payload)
            except BaseException as exc:
                retryable = isinstance(exc, Exception) and _is_endpoint_failure(exc)
                if isinstance(exc, Exception) and retryable:
                    _log_endpoint_failure(
                        operation=method_name,
                        endpoint_url=lease.endpoint_url,
                        model_name=self.model,
                        exc=exc,
                        emitted=False,
                        started=started,
                    )
                lease.release()
                if not isinstance(exc, Exception) or not retryable or not self.endpoint_pool.can_retry(attempt):
                    raise
                last_error = exc
                excluded_urls.add(lease.endpoint_url)
                continue
            lease.release()
            return result
        raise last_error or OllamaEndpointUnavailableError("Ollama Embedding 调用失败")

    async def _ainvoke_with_retry(self, method_name: str, payload: Any) -> Any:
        last_error: Exception | None = None
        excluded_urls: set[str] = set()
        for attempt in range(self.endpoint_pool.request_attempts):
            try:
                lease = self.endpoint_pool.acquire(excluded_urls=excluded_urls)
            except OllamaEndpointUnavailableError:
                if last_error is not None:
                    raise last_error
                raise
            started = time.monotonic()
            try:
                result = await getattr(self._build_delegate(lease.endpoint_url), method_name)(payload)
            except BaseException as exc:
                retryable = isinstance(exc, Exception) and _is_endpoint_failure(exc)
                if isinstance(exc, Exception) and retryable:
                    _log_endpoint_failure(
                        operation=method_name,
                        endpoint_url=lease.endpoint_url,
                        model_name=self.model,
                        exc=exc,
                        emitted=False,
                        started=started,
                    )
                lease.release()
                if not isinstance(exc, Exception) or not retryable or not self.endpoint_pool.can_retry(attempt):
                    raise
                last_error = exc
                excluded_urls.add(lease.endpoint_url)
                continue
            lease.release()
            return result
        raise last_error or OllamaEndpointUnavailableError("Ollama Embedding 调用失败")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量向量化并执行请求级分发。"""
        return self._invoke_with_retry("embed_documents", texts)

    def embed_query(self, text: str) -> list[float]:
        """查询向量化并执行请求级分发。"""
        return self._invoke_with_retry("embed_query", text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """异步批量向量化并执行请求级分发。"""
        return await self._ainvoke_with_retry("aembed_documents", texts)

    async def aembed_query(self, text: str) -> list[float]:
        """异步查询向量化并执行请求级分发。"""
        return await self._ainvoke_with_retry("aembed_query", text)
