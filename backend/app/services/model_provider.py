"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 模型统一适配层——按模型名路由到 ChatOllama(本地) 或 ChatOpenAI(OpenAI兼容/千帆)，统一 Runnable 接口
"""
import asyncio
import logging
import uuid

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from app.core.config import settings
from app.services.ollama_load_balancer import (
    LoadBalancedChatOllama,
    LoadBalancedOllamaEmbeddings,
    OllamaEndpointPool,
)

logger = logging.getLogger("labagent")

_AUTO_MODEL = "auto"
_OLLAMA_MODEL_PROBE_TIMEOUT_SECONDS = 2.0
_OLLAMA_CONTEXT_WINDOW_TIMEOUT_SECONDS = 2.0

# 外部（OpenAI 兼容）模型清单，对齐参考项目 RagConstant.OPENAI_LLM
_OPENAI_MODELS = {
    "ernie-4.5-turbo-128k-preview",
    "deepseek-v3",
    "deepseek-r1",
    "qwen3-235b-a22b",
    "llama-2-70b",
}

# Azure OpenAI 网关（字节 aidp modelhub）模型清单
_AZURE_MODELS = {
    "gpt-5.5-2026-04-24",
}

class ModelProvider:
    """大模型提供器，按模型名选择本地或外部 provider。"""

    def __init__(self) -> None:
        endpoint_config = settings.ollama_base_urls or settings.ollama_base_url
        self._ollama_endpoint_pool = OllamaEndpointPool(
            endpoint_config.split(","),
            retry_other_endpoint_on_failure=settings.ollama_retry_other_endpoint_on_failure,
        )

    def get_chat_model(
        self,
        model: str | None = None,
        *,
        operation_name: str = "chat",
    ) -> BaseChatModel:
        """按模型名路由；为空或本地模型走 Ollama，外部模型走 OpenAI 兼容接口。"""
        model_name = model or settings.ollama_chat_model
        if model_name in _AZURE_MODELS:
            return self._build_azure(model_name)
        if model_name in _OPENAI_MODELS:
            return self._build_openai(model_name)
        return self._build_ollama(model_name, operation_name=operation_name)

    async def resolve_chat_model_name(self, model: str | None) -> str:
        """解析 AUTO 模型：Ollama 目标模型可用时使用本地模型，否则使用 Azure 模型。"""
        model_name = model or settings.ollama_chat_model
        if model_name != _AUTO_MODEL:
            return model_name

        local_model = settings.ollama_chat_model
        if await self._ollama_model_available(local_model):
            logger.info("AUTO模型路由: provider=ollama, model=%s", local_model)
            return local_model

        fallback_model = settings.azure_chat_model
        logger.info("AUTO模型路由: provider=azure, model=%s", fallback_model)
        return fallback_model

    async def resolve_context_window(self, model_name: str) -> int:
        """解析模型实际上下文窗口，Ollama 多节点取最小值以保证负载均衡安全。"""
        configured_window = settings.model_context_windows.get(model_name)
        if configured_window is not None and configured_window > 0:
            return configured_window
        if model_name in _AZURE_MODELS or model_name in _OPENAI_MODELS:
            return settings.model_context_window_fallback

        context_windows = await asyncio.gather(
            *(
                self._ollama_loaded_context_window(endpoint_url, model_name)
                for endpoint_url in self._ollama_endpoint_pool.endpoint_urls
            )
        )
        safe_windows = [
            window or settings.model_context_window_fallback
            for window in context_windows
        ]
        return min(safe_windows)

    @staticmethod
    async def _ollama_loaded_context_window(
        endpoint_url: str,
        model_name: str,
    ) -> int | None:
        """从 Ollama 运行状态读取已加载模型的实际 context_length。"""
        try:
            async with httpx.AsyncClient(
                timeout=_OLLAMA_CONTEXT_WINDOW_TIMEOUT_SECONDS
            ) as client:
                response = await client.get(f"{endpoint_url}/api/ps")
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError):
            return None

        models = payload.get("models", []) if isinstance(payload, dict) else []
        if not isinstance(models, list):
            return None
        for item in models:
            if not isinstance(item, dict):
                continue
            loaded_name = item.get("name") or item.get("model")
            context_length = item.get("context_length")
            if loaded_name == model_name and isinstance(context_length, int) and context_length > 0:
                return context_length
        return None

    async def embedding_model_available(self) -> bool:
        """在两秒内确认至少一个 Ollama Endpoint 已加载 Embedding 模型。"""
        return await self._ollama_model_available(settings.ollama_embedding_model)

    async def _ollama_model_available(self, model_name: str) -> bool:
        """在固定两秒内并发探测所有 Ollama Endpoint 的模型列表。"""
        async def probe(endpoint_url: str) -> bool:
            try:
                async with httpx.AsyncClient(timeout=_OLLAMA_MODEL_PROBE_TIMEOUT_SECONDS) as client:
                    response = await client.get(f"{endpoint_url}/api/tags")
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict):
                        return False
                    models = payload.get("models", [])
                    if not isinstance(models, list):
                        return False
                    return any(
                        isinstance(item, dict)
                        and (item.get("name") == model_name or item.get("model") == model_name)
                        for item in models
                    )
            except (httpx.HTTPError, ValueError, TypeError):
                return False

        tasks = [
            asyncio.create_task(probe(url))
            for url in self._ollama_endpoint_pool.endpoint_urls
        ]
        try:
            for completed in asyncio.as_completed(
                tasks,
                timeout=_OLLAMA_MODEL_PROBE_TIMEOUT_SECONDS,
            ):
                if await completed:
                    return True
        except TimeoutError:
            return False
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        return False

    def get_fallback_model(self) -> BaseChatModel:
        """本地 Ollama 兜底模型，外部模型失败时回退。"""
        return self._build_ollama(settings.ollama_chat_model, operation_name="fallback")

    def get_embedding_model(self) -> OllamaEmbeddings:
        """构建嵌入模型，供 RAG 向量化使用；与 chat 模型共用 Endpoint 池。

        显式设置超时：Ollama 不可达时快速失败，让检索层及时降级，
        避免默认长超时（约 75s）拖死整个对话流。
        """
        return LoadBalancedOllamaEmbeddings(
            model=settings.ollama_embedding_model,
            endpoint_pool=self._ollama_endpoint_pool,
            client_kwargs={"timeout": settings.ollama_embedding_timeout},
        )

    def get_query_rewrite_model(self) -> BaseChatModel:
        """构建用于 MultiQuery 查询改写的模型，与 rerank 模型职责分离。"""
        model_name = settings.rag_query_rewrite_model or settings.ollama_chat_model
        if model_name in _AZURE_MODELS or model_name in _OPENAI_MODELS:
            return self.get_chat_model(model_name)
        return LoadBalancedChatOllama(
            model=model_name,
            endpoint_pool=self._ollama_endpoint_pool,
            operation_name="query_rewrite",
            reasoning=False,
            temperature=0,
            client_kwargs={"timeout": settings.model_request_timeout_seconds},
        )

    def get_rerank_model(self) -> BaseChatModel:
        """构建用于 LLM rerank 精排的模型；本地模型关闭思考并限制短 JSON 输出。"""
        model_name = settings.rag_rerank_model or settings.ollama_chat_model
        if model_name in _AZURE_MODELS or model_name in _OPENAI_MODELS:
            return self.get_chat_model(model_name)
        return LoadBalancedChatOllama(
            model=model_name,
            endpoint_pool=self._ollama_endpoint_pool,
            operation_name="rerank",
            reasoning=False,
            num_predict=settings.rag_rerank_num_predict,
            temperature=0,
            client_kwargs={"timeout": settings.model_request_timeout_seconds},
        )

    def get_memory_extraction_model(self, model: str | None = None) -> BaseChatModel:
        """构建记忆提取模型；本地模型关闭思考并限制结构化 Profile 输出。"""
        model_name = model or settings.ollama_chat_model
        if model_name in _AZURE_MODELS or model_name in _OPENAI_MODELS:
            return self.get_chat_model(model_name, operation_name="memory_extraction")
        return LoadBalancedChatOllama(
            model=model_name,
            endpoint_pool=self._ollama_endpoint_pool,
            operation_name="memory_extraction",
            reasoning=False,
            num_predict=settings.memory_extraction_num_predict,
            temperature=0,
            client_kwargs={"timeout": settings.model_request_timeout_seconds},
        )

    def get_conversation_title_model(self, model: str | None = None) -> BaseChatModel:
        """构建会话标题模型；本地模型关闭思考并限制短文本输出。"""
        model_name = settings.conversation_title_model or model or settings.ollama_chat_model
        if model_name in _AZURE_MODELS or model_name in _OPENAI_MODELS:
            return self.get_chat_model(model_name, operation_name="title")
        return LoadBalancedChatOllama(
            model=model_name,
            endpoint_pool=self._ollama_endpoint_pool,
            operation_name="title",
            reasoning=False,
            num_predict=settings.conversation_title_num_predict,
            temperature=0,
            client_kwargs={"timeout": settings.model_request_timeout_seconds},
        )

    def _build_ollama(
        self,
        model_name: str,
        *,
        operation_name: str,
    ) -> ChatOllama:
        """构建 Ollama 聊天模型。"""
        return LoadBalancedChatOllama(
            model=model_name,
            endpoint_pool=self._ollama_endpoint_pool,
            operation_name=operation_name,
            reasoning=True if operation_name == "agent" else None,
            client_kwargs={"timeout": settings.model_request_timeout_seconds},
        )

    def _build_openai(self, model_name: str) -> ChatOpenAI:
        """构建 OpenAI 兼容聊天模型（千帆等）。"""
        return ChatOpenAI(
            model=model_name,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=settings.model_request_timeout_seconds,
        )

    def _build_azure(self, model_name: str) -> AzureChatOpenAI:
        """构建 Azure OpenAI 网关聊天模型（字节 aidp modelhub）。

        网关按 Azure 部署路径 openai/deployments/{deployment}/chat/completions 暴露，
        须用 deployment_name + openai_api_version + openai_api_type=azure 参数组合，
        否则拼出的路径与网关不匹配导致请求挂起超时。
        """
        logid = settings.azure_logid or f"labagent-{uuid.uuid4().hex}"
        return AzureChatOpenAI(
            openai_api_type="azure",
            openai_api_version=settings.azure_api_version,
            azure_endpoint=settings.azure_endpoint,
            openai_api_key=settings.azure_api_key,
            deployment_name=model_name,
            default_headers={"X-TT-LOGID": logid},
            timeout=settings.model_request_timeout_seconds,
            max_retries=0,
        )


# 全局单例，无状态可复用
model_provider = ModelProvider()
