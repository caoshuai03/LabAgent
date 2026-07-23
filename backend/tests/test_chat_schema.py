"""
@author: caoshuai.cs
@date: 2026-07-24 00:00
@description: 对话接口响应模型兼容性测试
"""
from datetime import datetime

from app.schemas.chat import ChatMessageVO


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
