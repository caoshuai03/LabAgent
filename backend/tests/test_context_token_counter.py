"""
@author: caoshuai.cs
@date: 2026-07-30 00:00
@description: 固定 o200k_base 上下文 Token 计数器单元测试
"""
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from app.services.context_token_counter import ContextTokenCounter


@tool
def _sample_memory_search(query: str) -> str:
    """Search user memory by keyword."""
    return query


def test_chinese_text_is_not_estimated_by_four_characters_per_token() -> None:
    """中文文本必须交给 tokenizer，不能继续按字符数除以4。"""
    counter = ContextTokenCounter()
    text = "这是一次中文上下文计算测试。" * 100

    assert counter.count_text(text) > len(text) // 4


def test_context_includes_system_messages_and_tool_schema() -> None:
    """完整上下文应包含 System Prompt、历史消息和 Tool Schema。"""
    counter = ContextTokenCounter()
    messages = [
        HumanMessage(content="请搜索我的历史偏好"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "_sample_memory_search",
                    "args": {"query": "回答语言"},
                    "id": "call_1",
                    "type": "tool_call",
                }
            ],
        ),
    ]

    message_tokens = counter.count_context(
        system_prompt="",
        messages=messages,
    )
    complete_tokens = counter.count_context(
        system_prompt="你是 LabAgent。",
        messages=messages,
        tools=[_sample_memory_search],
    )

    assert complete_tokens > message_tokens
    assert counter.count_tools([_sample_memory_search]) > 0


def test_truncate_text_respects_token_limit() -> None:
    """Token 截断结果不得超过指定上限。"""
    counter = ContextTokenCounter()
    result = counter.truncate_text("中文和 English 混合内容。" * 100, 80)

    assert counter.count_text(result) <= 80
