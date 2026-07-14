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

from langchain_core.messages import AIMessageChunk, HumanMessage

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

        # 2. 通过 LangGraph 检索增强图流式生成（上下文由 checkpointer 按 thread_id 恢复）
        # thread_id 绑定 user_id：复用 checkpointer 原生 thread 隔离能力，按「用户+会话」双键隔离记忆，
        # 即使拿到他人 session_id 也凑不出正确 thread_id，与业务归属校验形成双保险
        graph = get_chat_graph()
        thread_id = f"{user_id}:{session_id_str}"
        config = {"configurable": {"thread_id": thread_id, "model": model}}
        full_response: list[str] = []
        response_sources: list[dict[str, str | float | None]] = []
        try:
            # 双模式：messages 捕获生成 token，custom 捕获检索图回传的引用来源
            async for stream_mode, chunk in graph.astream(
                {"messages": [HumanMessage(content=message)]},
                config=config,
                stream_mode=["messages", "custom"],
            ):
                if stream_mode == "custom":
                    sources = chunk.get("sources") if isinstance(chunk, dict) else None
                    if isinstance(sources, list):
                        response_sources = sources
                    if response_sources:
                        yield _sse_event("sources", session_id_str, trace_id, {"sources": response_sources})
                    continue
                # messages 模式：(消息块, 元数据)，仅取 generate 节点 token，避免 rerank 的 LLM 输出混入
                token, meta = chunk
                if (meta or {}).get("langgraph_node") != "generate":
                    continue
                # 只取流式增量块 AIMessageChunk；generate 节点结束时返回的完整 AIMessage
                # 也会作为 messages 事件发出，若不过滤会导致整段回答被重复输出一次
                if not isinstance(token, AIMessageChunk):
                    continue
                content = getattr(token, "content", "")
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
                await MessageService(db).save_message(
                    sid, user_id, "assistant", answer, sources=response_sources
                )
                await SessionService(db).touch(sid)
                await db.commit()

        logger.info(
            "对话完成: session_id=%s, trace_id=%s, answer_length=%d, cost=%dms",
            session_id_str, trace_id, len(answer), int((time.time() - start) * 1000),
        )
        yield _sse_event("final", session_id_str, trace_id, {"done": True})
