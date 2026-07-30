"""
@author: caoshuai.cs
@date: 2026-07-30 00:00
@description: 使用固定 o200k_base 统一计算消息、系统提示词与 Tool Schema 的上下文 Token
"""
import json
from collections.abc import Sequence
from typing import Any

import tiktoken
from langchain_core.messages import BaseMessage, SystemMessage, convert_to_openai_messages
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool


class ContextTokenCounter:
    """使用固定 o200k_base 提供与模型无关、可重复的 Token 计算。"""

    def __init__(self) -> None:
        self._encoding = tiktoken.get_encoding("o200k_base")

    def count_text(self, text: str) -> int:
        """计算普通文本 Token。"""
        if not text:
            return 0
        return len(self._encoding.encode(text, disallowed_special=()))

    def count_messages(self, messages: Sequence[BaseMessage]) -> int:
        """按统一 OpenAI 消息结构计算消息及 Tool Call Token。"""
        if not messages:
            return 0
        payload = convert_to_openai_messages(list(messages), include_id=False)
        return self._count_json(payload)

    def count_tools(self, tools: Sequence[BaseTool]) -> int:
        """按统一 OpenAI Tool Schema 结构计算工具定义 Token。"""
        if not tools:
            return 0
        payload = [convert_to_openai_tool(tool_item) for tool_item in tools]
        return self._count_json(payload)

    def count_context(
        self,
        *,
        system_prompt: str,
        messages: Sequence[BaseMessage],
        tools: Sequence[BaseTool] = (),
    ) -> int:
        """计算一次模型调用前的完整输入上下文。"""
        prompt_messages: list[BaseMessage] = list(messages)
        if system_prompt:
            prompt_messages.insert(0, SystemMessage(content=system_prompt))
        return self.count_messages(prompt_messages) + self.count_tools(tools)

    def truncate_text(self, text: str, max_tokens: int) -> str:
        """按 Token 上限安全截断文本。"""
        if max_tokens <= 0 or not text:
            return ""
        token_ids = self._encoding.encode(text, disallowed_special=())
        if len(token_ids) <= max_tokens:
            return text
        return self._encoding.decode(token_ids[:max_tokens])

    def _count_json(self, payload: Any) -> int:
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        return self.count_text(serialized)


context_token_counter = ContextTokenCounter()
