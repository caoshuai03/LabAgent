"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 模型统一适配层——按模型名路由到 ChatOllama(本地) 或 ChatOpenAI(OpenAI兼容/千帆)，统一 Runnable 接口
"""
import uuid

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from app.core.config import settings

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

# 外部调用超时（秒），避免阻塞
_REQUEST_TIMEOUT = 60


class ModelProvider:
    """大模型提供器，按模型名选择本地或外部 provider。"""

    def get_chat_model(self, model: str | None = None) -> BaseChatModel:
        """按模型名路由；为空或本地模型走 Ollama，外部模型走 OpenAI 兼容接口。"""
        model_name = model or settings.ollama_chat_model
        if model_name in _AZURE_MODELS:
            return self._build_azure(model_name)
        if model_name in _OPENAI_MODELS:
            return self._build_openai(model_name)
        return self._build_ollama(model_name)

    def get_fallback_model(self) -> BaseChatModel:
        """本地 Ollama 兜底模型，外部模型失败时回退。"""
        return self._build_ollama(settings.ollama_chat_model)

    def get_embedding_model(self) -> OllamaEmbeddings:
        """构建嵌入模型，供 RAG 向量化使用；与 chat 模型共用 base_url。

        显式设置超时：Ollama 不可达时快速失败，让检索层及时降级，
        避免默认长超时（约 75s）拖死整个对话流。
        """
        return OllamaEmbeddings(
            model=settings.ollama_embedding_model,
            base_url=settings.ollama_base_url,
            client_kwargs={"timeout": settings.ollama_embedding_timeout},
        )

    def get_query_rewrite_model(self) -> BaseChatModel:
        """构建用于 MultiQuery 查询改写的模型，与 rerank 模型职责分离。"""
        model_name = settings.rag_query_rewrite_model or settings.ollama_chat_model
        if model_name in _AZURE_MODELS or model_name in _OPENAI_MODELS:
            return self.get_chat_model(model_name)
        return ChatOllama(
            model=model_name,
            base_url=settings.ollama_base_url,
            reasoning=False,
            temperature=0,
            client_kwargs={"timeout": _REQUEST_TIMEOUT},
        )

    def get_rerank_model(self) -> BaseChatModel:
        """构建用于 LLM rerank 精排的模型；本地模型关闭思考并限制短 JSON 输出。"""
        model_name = settings.rag_rerank_model or settings.ollama_chat_model
        if model_name in _AZURE_MODELS or model_name in _OPENAI_MODELS:
            return self.get_chat_model(model_name)
        return ChatOllama(
            model=model_name,
            base_url=settings.ollama_base_url,
            reasoning=False,
            num_predict=settings.rag_rerank_num_predict,
            temperature=0,
            client_kwargs={"timeout": _REQUEST_TIMEOUT},
        )

    def _build_ollama(self, model_name: str) -> ChatOllama:
        """构建 Ollama 聊天模型。"""
        return ChatOllama(
            model=model_name,
            base_url=settings.ollama_base_url,
            client_kwargs={"timeout": _REQUEST_TIMEOUT},
        )

    def _build_openai(self, model_name: str) -> ChatOpenAI:
        """构建 OpenAI 兼容聊天模型（千帆等）。"""
        return ChatOpenAI(
            model=model_name,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=_REQUEST_TIMEOUT,
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
            timeout=_REQUEST_TIMEOUT,
            max_retries=0,
        )


# 全局单例，无状态可复用
model_provider = ModelProvider()
