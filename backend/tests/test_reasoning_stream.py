"""
@author: caoshuai.cs
@date: 2026-07-26
@description: 主Agent思考流解析测试
"""
from langchain_core.messages import AIMessageChunk

from app.services.ai_service import _ThinkTagStreamParser, _reasoning_content_from_chunk


def test_think_tag_parser_handles_tags_split_across_chunks() -> None:
    """被网络分片拆开的 think 标签不能泄露到回答正文。"""
    parser = _ThinkTagStreamParser()

    assert parser.feed("<thi") == ([], [], False)
    assert parser.feed("nk>步骤") == ([], [], False)
    assert parser.feed("一</th") == ([], [], False)
    assert parser.feed("ink>答案") == (["步骤一"], [], True)
    assert parser.finish() == ([], ["答案"], False)


def test_structured_reasoning_content_is_preferred() -> None:
    """适配层输出的 reasoning_content 应独立于最终正文读取。"""
    chunk = AIMessageChunk(
        content="最终回答",
        additional_kwargs={"reasoning_content": "先分析题目条件"},
    )

    assert _reasoning_content_from_chunk(chunk) == "先分析题目条件"
