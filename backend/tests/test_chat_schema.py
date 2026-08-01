"""
@author: caoshuai.cs
@date: 2026-07-24 00:00
@description: 对话接口响应模型兼容性测试
"""
from datetime import datetime

import pytest

from app.schemas.chat import ChatMessageVO, ChatRequest


def test_chat_message_sources_allow_missing_score() -> None:
    """历史引用来源可能没有相关度分数，接口返回模型应兼容旧数据。"""
    message = ChatMessageVO(
        id=1,
        session_id="00000000-0000-0000-0000-000000000001",
        role="assistant",
        content="回答内容",
        sources=[
            {
                "file_name": "实验课程知识库样例.md",
                "snippet": "Java 空指针异常通常是引用对象为空后继续访问成员。",
            }
        ],
        tool_calls=[],
        created_at=datetime(2026, 7, 24, 0, 0, 0),
    )

    assert message.sources[0].score is None


def test_chat_message_supports_selected_skills() -> None:
    """历史用户消息应返回主动选择的Skill名称。"""
    message = ChatMessageVO(
        id=1,
        session_id="00000000-0000-0000-0000-000000000001",
        role="user",
        content="分析异常",
        skill_names=["java-debug-helper"],
        created_at=datetime(2026, 8, 1, 0, 0, 0),
    )

    assert message.skill_names == ["java-debug-helper"]


def test_chat_request_requires_text_or_image() -> None:
    """聊天请求必须包含文本或图片。"""
    with pytest.raises(ValueError):
        ChatRequest(message="")


def test_chat_request_accepts_image_only() -> None:
    """允许只发送图片，由后端补充模型提示文本。"""
    request = ChatRequest(
        message="",
        images=[
            {
                "image_id": "a" * 32,
                "file_name": "实验图.png",
                "content_type": "image/png",
                "size": 100,
            }
        ],
    )
    assert request.message == ""


def test_chat_request_allows_up_to_ten_images() -> None:
    """单轮允许十张图片，第十一张由请求模型直接拒绝。"""
    image = {
        "image_id": "a" * 32,
        "file_name": "实验图.png",
        "content_type": "image/png",
        "size": 100,
    }
    assert len(ChatRequest(message="", images=[image] * 10).images) == 10
    with pytest.raises(ValueError):
        ChatRequest(message="", images=[image] * 11)


def test_chat_request_allows_up_to_three_skills() -> None:
    """单轮最多允许主动选择三个 Skill。"""
    request = ChatRequest(
        message="分析异常",
        skill_names=["java-debug-helper", "lab-report-writer"],
    )

    assert request.skill_names == ["java-debug-helper", "lab-report-writer"]
    with pytest.raises(ValueError):
        ChatRequest(message="分析异常", skill_names=["a", "b", "c", "d"])
