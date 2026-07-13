"""
@author: caoshuai.cs
@date: 2026-07-12
@description: AI 对话编排服务——串联会话/消息业务与 LangGraph 图；SSE 流式输出，上下文由 checkpointer 管理
"""
import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator

from langchain_core.messages import HumanMessage

from app.db.session import async_session_factory
from app.graph.chat_graph import get_chat_graph
from app.services.message_service import MessageService
from app.services.session_service import SessionService

logger = logging.getLogger("labagent")


def _sse_event(event_type: str, session_id: str, trace_id: str, payload: dict) -> str:
    """组装一条 SSE data 行（JSON）。"""
    data = {
        "event_type": event_type,
        "session_id": session_id,
        "trace_id": trace_id,
        "ts": int(time.time() * 1000),
        "payload": payload,
    }
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


class AiService:
    """AI 对话编排。自管理数据库会话，以适配流式响应生命周期。"""

    async def stream_chat(
        self, message: str, session_id: str | None, user_id: int, model: str | None
    ) -> AsyncGenerator[str, None]:
        """执行一次对话：准备会话→存用户消息→图流式生成→存助手消息，产出 SSE。"""
        trace_id = uuid.uuid4().hex
        start = time.time()

        # 1. 准备会话并持久化用户消息（业务表）
        async with async_session_factory() as db:
            session_service = SessionService(db)
            message_service = MessageService(db)
            chat_session = await session_service.get_or_create_session(session_id, user_id, message)
            sid = chat_session.id
            await message_service.save_message(sid, user_id, "user", message)
            await db.commit()

        session_id_str = str(sid)
        yield _sse_event("session", session_id_str, trace_id, {"session_id": session_id_str})

        # 2. 通过 LangGraph 图流式生成（上下文由 checkpointer 按 thread_id 恢复）
        graph = get_chat_graph()
        config = {"configurable": {"thread_id": session_id_str, "model": model}}
        full_response: list[str] = []
        try:
            async for chunk, _meta in graph.astream(
                {"messages": [HumanMessage(content=message)]},
                config=config,
                stream_mode="messages",
            ):
                content = getattr(chunk, "content", "")
                if content:
                    full_response.append(content)
                    yield _sse_event("token", session_id_str, trace_id, {"content": content})
        except Exception as exc:  # noqa: BLE001 - 流式失败需返回错误事件而非中断连接
            logger.exception("对话流式生成失败: session_id=%s, trace_id=%s", session_id_str, trace_id)
            yield _sse_event("error", session_id_str, trace_id, {"message": "模型服务异常，请稍后重试"})
            return

        # 3. 持久化助手消息并刷新会话时间（业务表）
        answer = "".join(full_response)
        if answer:
            async with async_session_factory() as db:
                await MessageService(db).save_message(sid, user_id, "assistant", answer)
                await SessionService(db).touch(sid)
                await db.commit()

        logger.info(
            "对话完成: session_id=%s, trace_id=%s, answer_length=%d, cost=%dms",
            session_id_str, trace_id, len(answer), int((time.time() - start) * 1000),
        )
        yield _sse_event("final", session_id_str, trace_id, {"done": True})
