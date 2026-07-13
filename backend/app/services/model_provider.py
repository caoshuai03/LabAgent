"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 模型统一适配层——按模型名路由到 ChatOllama(本地) 或 ChatOpenAI(OpenAI兼容/千帆)，统一 Runnable 接口
"""
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.core.config import settings

# 外部（OpenAI 兼容）模型清单，对齐参考项目 RagConstant.OPENAI_LLM
_OPENAI_MODELS = {
    "ernie-4.5-turbo-128k-preview",
    "deepseek-v3",
    "deepseek-r1",
    "qwen3-235b-a22b",
    "llama-2-70b",
}

# 外部调用超时（秒），避免阻塞
_REQUEST_TIMEOUT = 60


class ModelProvider:
    """大模型提供器，按模型名选择本地或外部 provider。"""

    def get_chat_model(self, model: str | None = None) -> BaseChatModel:
        """按模型名路由；为空或本地模型走 Ollama，外部模型走 OpenAI 兼容接口。"""
        model_name = model or settings.ollama_chat_model
        if model_name in _OPENAI_MODELS:
            return self._build_openai(model_name)
        return self._build_ollama(model_name)

    def get_fallback_model(self) -> BaseChatModel:
        """本地 Ollama 兜底模型，外部模型失败时回退。"""
        return self._build_ollama(settings.ollama_chat_model)

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


# 全局单例，无状态可复用
model_provider = ModelProvider()
