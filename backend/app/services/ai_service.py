"""
@author: caoshuai.cs
@date: 2026-07-15 00:41
@description: AI 对话编排服务——RAG + Agent ToolNode 流式调用、人工审批恢复、工具事件持久化
"""
import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langgraph.types import Command

from app.core.config import settings
from app.db.session import async_session_factory
from app.graph.chat_graph import get_chat_graph
from app.services.conversation_title_queue import enqueue_conversation_title
from app.services.message_service import MessageService
from app.services.session_service import SessionService
from app.services.tool_call_service import ToolCallService
from app.tools.registry import tool_registry
from app.tools.result import parse_result_envelope, redact_value, truncate_text

logger = logging.getLogger("labagent")

_MAX_REASONING_SEGMENT_LENGTH = 4_000
_MAX_REASONING_TOTAL_LENGTH = 12_000


class _ThinkTagStreamParser:
    """按流式分片拆分 <think> 标签内的思考内容与最终回答。"""

    _open_tag = "<think>"
    _close_tag = "</think>"

    def __init__(self) -> None:
        self._buffer = ""
        self._in_reasoning = False

    def feed(self, content: str) -> tuple[list[str], list[str], bool]:
        """解析一个文本分片，保留可能被切开的标签尾部。"""
        reasoning_parts: list[str] = []
        answer_parts: list[str] = []
        reasoning_finished = False
        pending = self._buffer + content
        self._buffer = ""

        while pending:
            tag = self._close_tag if self._in_reasoning else self._open_tag
            tag_index = pending.lower().find(tag)
            if tag_index >= 0:
                before_tag = pending[:tag_index]
                if before_tag:
                    (reasoning_parts if self._in_reasoning else answer_parts).append(before_tag)
                pending = pending[tag_index + len(tag) :]
                if self._in_reasoning:
                    reasoning_finished = True
                self._in_reasoning = not self._in_reasoning
                continue

            tail_length = len(tag) - 1
            if len(pending) <= tail_length:
                self._buffer = pending
                break
            visible, self._buffer = pending[:-tail_length], pending[-tail_length:]
            (reasoning_parts if self._in_reasoning else answer_parts).append(visible)
            break

        return reasoning_parts, answer_parts, reasoning_finished

    def finish(self) -> tuple[list[str], list[str], bool]:
        """结束当前模型分片，输出延迟缓冲的内容。"""
        reasoning_parts: list[str] = []
        answer_parts: list[str] = []
        if self._buffer:
            (reasoning_parts if self._in_reasoning else answer_parts).append(self._buffer)
        reasoning_finished = self._in_reasoning
        self._buffer = ""
        self._in_reasoning = False
        return reasoning_parts, answer_parts, reasoning_finished


class _ReasoningCollector:
    """限制并汇集可向用户展示、可持久化的主 Agent 思考片段。"""

    def __init__(self) -> None:
        self.records: list[dict[str, str | int]] = []
        self._total_length = 0

    def start(self) -> dict[str, str | int]:
        """创建新一轮思考记录。"""
        round_number = len(self.records) + 1
        record: dict[str, str | int] = {
            "reasoning_id": f"agent-{round_number}",
            "phase": "agent",
            "round_number": round_number,
            "content": "",
        }
        self.records.append(record)
        return record

    def append(self, record: dict[str, str | int], content: str) -> str:
        """追加思考内容，并限制单轮与整条消息的持久化长度。"""
        current_length = len(str(record["content"]))
        allowed = min(
            _MAX_REASONING_SEGMENT_LENGTH - current_length,
            _MAX_REASONING_TOTAL_LENGTH - self._total_length,
        )
        if allowed <= 0:
            return ""
        safe_content = content[:allowed]
        record["content"] = f"{record['content']}{safe_content}"
        self._total_length += len(safe_content)
        return safe_content


def _reasoning_content_from_chunk(chunk: AIMessageChunk) -> str:
    """提取模型适配层规范化后的结构化思考字段。"""
    additional_kwargs = chunk.additional_kwargs
    if not isinstance(additional_kwargs, dict):
        return ""
    for field_name in ("reasoning_content", "reasoning", "thinking"):
        value = additional_kwargs.get(field_name)
        if isinstance(value, str) and value:
            return value
    return ""


def _sse_event(event_type: str, session_id: str, trace_id: str, payload: dict[str, Any]) -> str:
    """组装一条 SSE data 行。"""
    data = {
        "event_type": event_type,
        "session_id": session_id,
        "trace_id": trace_id,
        "ts": int(time.time() * 1000),
        "payload": payload,
    }
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _messages_from_update(chunk: Any, node_name: str) -> list[Any]:
    """从 updates 流的指定节点提取消息。"""
    if not isinstance(chunk, dict):
        return []
    node_update = chunk.get(node_name)
    if not isinstance(node_update, dict):
        return []
    messages = node_update.get("messages")
    return list(messages) if isinstance(messages, list) else []


def _merge_sources(
    existing: list[dict[str, Any]], incoming: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """累积多次检索的引用来源并按 file_name + snippet 去重（供持久化保存全部来源）。"""
    merged = list(existing)
    seen = {(item.get("file_name"), item.get("snippet")) for item in existing}
    for item in incoming:
        key = (item.get("file_name"), item.get("snippet"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


class AiService:
    """RAG + Agent 对话编排。"""

    def __init__(self) -> None:
        self._running_tasks: dict[str, tuple[int, str, asyncio.Task[Any]]] = {}
        self._cleanup_tasks: set[asyncio.Task[None]] = set()

    def _schedule_cancel_cleanup(self, trace_id: str) -> None:
        """在独立任务中清理已取消的工具记录，避免请求取消作用域中断数据库操作。"""
        task = asyncio.create_task(self._cancel_running_tools(trace_id))
        self._cleanup_tasks.add(task)
        task.add_done_callback(self._handle_cleanup_done)

    def _handle_cleanup_done(self, task: asyncio.Task[None]) -> None:
        """回收取消清理任务并记录异常。"""
        self._cleanup_tasks.discard(task)
        try:
            task.result()
        except asyncio.CancelledError:
            logger.warning("Agent取消清理任务被中断")
        except Exception:  # noqa: BLE001 - 后台清理异常只记录日志
            logger.exception("Agent取消清理失败")

    async def _cancel_running_tools(self, trace_id: str) -> None:
        """将指定运行中尚未结束的工具调用标记为已取消。"""
        async with async_session_factory() as db:
            await ToolCallService(db).cancel_running(trace_id)
            await db.commit()

    async def _safe_cancel_running_tools(self, trace_id: str) -> None:
        """安全清理运行中的工具记录，清理失败不吞掉主错误响应。"""
        try:
            await self._cancel_running_tools(trace_id)
        except Exception:  # noqa: BLE001 - 异常路径只记录清理失败，继续返回原始错误
            logger.exception("Agent异常清理工具状态失败: trace_id=%s", trace_id)

    async def _save_assistant_error_message(
        self,
        session_id: uuid.UUID,
        user_id: int,
        record_trace_id: str,
        content: str,
    ) -> None:
        """把 Agent 异常结果落库，避免历史会话只有标题或缺少失败原因。"""
        try:
            async with async_session_factory() as db:
                message = await MessageService(db).save_message(
                    session_id,
                    user_id,
                    "assistant",
                    content,
                )
                await ToolCallService(db).link_message(record_trace_id, message.id)
                await SessionService(db).touch(session_id)
                await db.commit()
        except Exception:  # noqa: BLE001 - 异常兜底落库失败只能记录日志，避免覆盖原始错误
            logger.exception("Agent异常消息落库失败: session_id=%s, trace_id=%s", session_id, record_trace_id)

    async def _enqueue_session_title(
        self,
        session_id: uuid.UUID,
        user_id: int,
        user_message: str,
        assistant_answer: str,
        model: str | None,
    ) -> None:
        """提交标题后台任务；入队失败只更新状态，不影响主对话。"""
        if not settings.conversation_title_enabled:
            return
        try:
            await enqueue_conversation_title(
                str(session_id),
                user_id,
                user_message,
                assistant_answer,
                model,
            )
        except Exception:  # noqa: BLE001 - 标题是辅助能力，入队失败不影响主对话
            logger.warning("新会话标题任务入队失败: session_id=%s", session_id, exc_info=True)

    async def stream_chat(
        self,
        message: str,
        session_id: str | None,
        user_id: int,
        model: str | None,
        rag_retrieval_mode: str | None = None,
        rag_retrieval_top_k: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """开始新的 Agent 运行。"""
        trace_id = uuid.uuid4().hex
        is_new_session = not session_id
        try:
            async with async_session_factory() as db:
                try:
                    session_service = SessionService(db)
                    chat_session = await session_service.get_or_create_session(session_id, user_id, message)
                    sid = chat_session.id
                    await MessageService(db).save_message(sid, user_id, "user", message)
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise
        except Exception:  # noqa: BLE001 - SSE 中返回受控错误
            logger.exception("Agent会话初始化失败: user_id=%s, session_id=%s", user_id, session_id)
            yield _sse_event("error", session_id or "", trace_id, {"message": "会话初始化失败，请稍后重试"})
            return

        session_id_str = str(sid)
        yield _sse_event("session", session_id_str, trace_id, {"session_id": session_id_str})
        graph_input = {
            "messages": [HumanMessage(content=message)],
            "user_id": user_id,
            "session_id": session_id_str,
            "model_name": model,
            "agent_run_id": trace_id,
            "tool_round": 0,
            "tool_call_signatures": {},
            "rag_retrieval_mode": rag_retrieval_mode or "current",
            "rag_retrieval_top_k": rag_retrieval_top_k or settings.rag_rerank_top_n,
        }
        async for event in self._stream_graph(
            graph_input,
            session_id=session_id_str,
            user_id=user_id,
            model=model,
            trace_id=trace_id,
            record_trace_id=trace_id,
            title_source_message=message if is_new_session else None,
        ):
            yield event

    async def stream_resume(
        self,
        session_id: str,
        interrupt_id: str,
        approved: bool,
        user_id: int,
    ) -> AsyncGenerator[str, None]:
        """在用户批准或拒绝后恢复暂停的 Agent 图。"""
        trace_id = uuid.uuid4().hex
        async with async_session_factory() as db:
            await SessionService(db).get_owned_session(session_id, user_id)

        graph = get_chat_graph()
        config = {"configurable": {"thread_id": f"{user_id}:{session_id}"}}
        snapshot = await graph.aget_state(config)
        values = snapshot.values if snapshot is not None else {}
        if not values or str(values.get("session_id", "")) != session_id:
            yield _sse_event("error", session_id, trace_id, {"message": "未找到可恢复的Agent状态"})
            return
        pending_interrupts = getattr(snapshot, "interrupts", ()) or ()
        if interrupt_id not in {str(getattr(item, "id", "")) for item in pending_interrupts}:
            yield _sse_event("error", session_id, trace_id, {"message": "工具审批已失效或不属于当前会话"})
            return

        model = values.get("model_name")
        record_trace_id = str(values.get("agent_run_id") or trace_id)
        title_source_message = next(
            (
                message.content
                for message in values.get("messages", [])
                if isinstance(message, HumanMessage) and isinstance(message.content, str)
            ),
            None,
        )
        async for event in self._stream_graph(
            Command(resume={"approved": approved}),
            session_id=session_id,
            user_id=user_id,
            model=model if isinstance(model, str) else None,
            trace_id=trace_id,
            record_trace_id=record_trace_id,
            title_source_message=title_source_message,
        ):
            yield event

    async def cancel_run(self, session_id: str, trace_id: str, user_id: int) -> bool:
        """取消当前用户指定会话中的 Agent 运行。"""
        async with async_session_factory() as db:
            await SessionService(db).get_owned_session(session_id, user_id)

        running = self._running_tasks.get(trace_id)
        if running is None:
            return False

        running_user_id, running_session_id, task = running
        if running_user_id != user_id or running_session_id != session_id or task.done():
            return False

        task.cancel()
        return True

    async def _stream_graph(
        self,
        graph_input: dict[str, Any] | Command,
        *,
        session_id: str,
        user_id: int,
        model: str | None,
        trace_id: str,
        record_trace_id: str,
        title_source_message: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """执行或恢复图，把框架流转换为前端 SSE。"""
        started = time.monotonic()
        graph = get_chat_graph()
        config = {
            "configurable": {"thread_id": f"{user_id}:{session_id}", "model": model},
            "recursion_limit": max(settings.agent_max_tool_rounds * 4 + 10, 30),
        }
        full_response: list[str] = []
        final_content = ""
        response_sources: list[dict[str, str | float | None]] = []
        reasoning_parser = _ThinkTagStreamParser()
        reasoning_collector = _ReasoningCollector()
        active_reasoning: dict[str, str | int] | None = None
        active_reasoning_is_tagged = False
        seen_tool_calls: set[str] = set()
        seen_tool_results: set[str] = set()
        paused = False
        sid = uuid.UUID(session_id)
        current_task = asyncio.current_task()
        if current_task is not None:
            self._running_tasks[trace_id] = (user_id, session_id, current_task)

        try:
            async with asyncio.timeout(settings.agent_timeout_seconds):
                async for stream_mode, chunk in graph.astream(
                    graph_input,
                    config=config,
                    stream_mode=["messages", "updates", "custom"],
                ):
                    if stream_mode == "custom":
                        if isinstance(chunk, dict) and isinstance(chunk.get("sources"), list):
                            new_sources = chunk["sources"]
                            if new_sources:
                                response_sources = _merge_sources(response_sources, new_sources)
                                yield _sse_event("sources", session_id, trace_id, {"sources": new_sources})
                        tool_event = chunk.get("tool_event") if isinstance(chunk, dict) else None
                        if isinstance(tool_event, dict):
                            event_type = str(tool_event.get("event_type") or "status")
                            payload = tool_event.get("payload") if isinstance(tool_event.get("payload"), dict) else {}
                            if event_type == "tool_call" and payload.get("tool_call_id"):
                                seen_tool_calls.add(str(payload["tool_call_id"]))
                            await self._persist_status_event(sid, payload)
                            yield _sse_event(event_type, session_id, trace_id, payload)
                        continue

                    if stream_mode == "messages":
                        token, meta = chunk
                        if (meta or {}).get("langgraph_node") != "agent":
                            continue
                        if not isinstance(token, AIMessageChunk):
                            continue
                        structured_reasoning = _reasoning_content_from_chunk(token)
                        if structured_reasoning:
                            if active_reasoning is None:
                                active_reasoning = reasoning_collector.start()
                                active_reasoning_is_tagged = False
                            reasoning_content = reasoning_collector.append(
                                active_reasoning, structured_reasoning
                            )
                            if reasoning_content:
                                yield _sse_event(
                                    "reasoning_token",
                                    session_id,
                                    trace_id,
                                    {
                                        "content": reasoning_content,
                                        "reasoning_id": active_reasoning["reasoning_id"],
                                        "phase": active_reasoning["phase"],
                                        "round_number": active_reasoning["round_number"],
                                    },
                                )
                        content = token.content
                        if isinstance(content, str) and content:
                            if active_reasoning is not None and not active_reasoning_is_tagged:
                                yield _sse_event(
                                    "reasoning_done",
                                    session_id,
                                    trace_id,
                                    {
                                        "reasoning_id": active_reasoning["reasoning_id"],
                                        "round_number": active_reasoning["round_number"],
                                    },
                                )
                                active_reasoning = None
                                full_response.append(content)
                                yield _sse_event("token", session_id, trace_id, {"content": content})
                                continue

                            reasoning_parts, answer_parts, reasoning_finished = reasoning_parser.feed(content)
                            for reasoning_part in reasoning_parts:
                                if active_reasoning is None:
                                    active_reasoning = reasoning_collector.start()
                                    active_reasoning_is_tagged = True
                                reasoning_content = reasoning_collector.append(active_reasoning, reasoning_part)
                                if reasoning_content:
                                    yield _sse_event(
                                        "reasoning_token",
                                        session_id,
                                        trace_id,
                                        {
                                            "content": reasoning_content,
                                            "reasoning_id": active_reasoning["reasoning_id"],
                                            "phase": active_reasoning["phase"],
                                            "round_number": active_reasoning["round_number"],
                                        },
                                    )
                            if reasoning_finished and active_reasoning is not None:
                                yield _sse_event(
                                    "reasoning_done",
                                    session_id,
                                    trace_id,
                                    {
                                        "reasoning_id": active_reasoning["reasoning_id"],
                                        "round_number": active_reasoning["round_number"],
                                    },
                                )
                                active_reasoning = None
                                active_reasoning_is_tagged = False
                            for answer_part in answer_parts:
                                if active_reasoning is not None:
                                    yield _sse_event(
                                        "reasoning_done",
                                        session_id,
                                        trace_id,
                                        {
                                            "reasoning_id": active_reasoning["reasoning_id"],
                                            "round_number": active_reasoning["round_number"],
                                        },
                                    )
                                    active_reasoning = None
                                    active_reasoning_is_tagged = False
                                full_response.append(answer_part)
                                yield _sse_event("token", session_id, trace_id, {"content": answer_part})
                        continue

                    if stream_mode != "updates" or not isinstance(chunk, dict):
                        continue

                    agent_messages = _messages_from_update(chunk, "agent")
                    if agent_messages:
                        reasoning_parts, answer_parts, _ = reasoning_parser.finish()
                        for reasoning_part in reasoning_parts:
                            if active_reasoning is None:
                                active_reasoning = reasoning_collector.start()
                                active_reasoning_is_tagged = True
                            reasoning_content = reasoning_collector.append(active_reasoning, reasoning_part)
                            if reasoning_content:
                                yield _sse_event(
                                    "reasoning_token",
                                    session_id,
                                    trace_id,
                                    {
                                        "content": reasoning_content,
                                        "reasoning_id": active_reasoning["reasoning_id"],
                                        "phase": active_reasoning["phase"],
                                        "round_number": active_reasoning["round_number"],
                                    },
                                )
                        if active_reasoning is not None:
                            yield _sse_event(
                                "reasoning_done",
                                session_id,
                                trace_id,
                                {
                                    "reasoning_id": active_reasoning["reasoning_id"],
                                    "round_number": active_reasoning["round_number"],
                                },
                            )
                            active_reasoning = None
                            active_reasoning_is_tagged = False
                        for answer_part in answer_parts:
                            full_response.append(answer_part)
                            yield _sse_event("token", session_id, trace_id, {"content": answer_part})

                    for message in agent_messages:
                        if not isinstance(message, AIMessage):
                            continue
                        if not message.tool_calls:
                            if isinstance(message.content, str):
                                final_content = message.content
                            continue
                        round_number = int((chunk.get("agent") or {}).get("tool_round", 1))
                        for call in message.tool_calls:
                            call_id = str(call.get("id", ""))
                            if not call_id or call_id in seen_tool_calls:
                                continue
                            seen_tool_calls.add(call_id)
                            tool_name = str(call.get("name", ""))
                            arguments = call.get("args") if isinstance(call.get("args"), dict) else {}
                            metadata = tool_registry.metadata(tool_name)
                            if metadata is None:
                                continue
                            safe_arguments = redact_value(arguments)
                            async with async_session_factory() as db:
                                await ToolCallService(db).ensure_pending(
                                    sid,
                                    user_id,
                                    record_trace_id,
                                    call_id,
                                    tool_name,
                                    metadata.source,
                                    metadata.risk_level,
                                    safe_arguments if isinstance(safe_arguments, dict) else {},
                                    round_number,
                                )
                                await db.commit()
                    for message in _messages_from_update(chunk, "tools"):
                        if not isinstance(message, ToolMessage):
                            continue
                        call_id = str(message.tool_call_id)
                        if not call_id or call_id in seen_tool_results:
                            continue
                        seen_tool_results.add(call_id)
                        result = parse_result_envelope(message.content)
                        success = bool(result.get("success", True))
                        internal = bool(result.get("internal", False))
                        result_status = str(
                            result.get("status") or ("success" if success else "failed")
                        )
                        summary = truncate_text(str(result.get("summary") or "工具执行完成"), 500)
                        error_message = result.get("error")
                        duration_ms = result.get("duration_ms")
                        tool_name = message.name or "tool"
                        output_preview: str | None = None
                        if tool_name == "execute_shell" and result.get("output"):
                            output_preview = truncate_text(
                                str(redact_value(result.get("output") or ""))
                            )
                        async with async_session_factory() as db:
                            await ToolCallService(db).update_status(
                                sid,
                                call_id,
                                result_status,
                                result_summary=summary,
                                output_preview=output_preview,
                                error_message=str(error_message) if error_message else None,
                                duration_ms=int(duration_ms) if isinstance(duration_ms, int | float) else None,
                                visible=not internal,
                            )
                            await db.commit()
                        if internal:
                            continue
                        result_payload = {
                            "tool_call_id": call_id,
                            "tool_name": tool_name,
                            "success": success,
                            "status": result_status,
                            "result_summary": summary,
                            "duration_ms": duration_ms,
                        }
                        if output_preview is not None:
                            result_payload["output_preview"] = output_preview
                        # write_file 的整文件预览字段（若存在）透传给前端，其他工具不带
                        for preview_field in ("preview_path", "preview_language", "preview_content"):
                            if result.get(preview_field) is not None:
                                result_payload[preview_field] = result.get(preview_field)
                        yield _sse_event(
                            "tool_result",
                            session_id,
                            trace_id,
                            result_payload,
                        )

                    interrupts = chunk.get("__interrupt__")
                    if interrupts:
                        interrupt_items = interrupts if isinstance(interrupts, (list, tuple)) else [interrupts]
                        for interrupt_item in interrupt_items:
                            interrupt_id = str(getattr(interrupt_item, "id", ""))
                            value = getattr(interrupt_item, "value", {})
                            payload = value if isinstance(value, dict) else {"value": value}
                            calls = payload.get("tool_calls") if isinstance(payload.get("tool_calls"), list) else []
                            async with async_session_factory() as db:
                                service = ToolCallService(db)
                                for call in calls:
                                    if isinstance(call, dict) and call.get("tool_call_id"):
                                        await service.update_status(
                                            sid,
                                            str(call["tool_call_id"]),
                                            "pending_approval",
                                            interrupt_id=interrupt_id,
                                        )
                                await db.commit()
                            approval_payload = {**payload, "interrupt_id": interrupt_id}
                            yield _sse_event("tool_approval_required", session_id, trace_id, approval_payload)
                            yield _sse_event(
                                "paused",
                                session_id,
                                trace_id,
                                {"reason": "tool_approval", "interrupt_id": interrupt_id},
                            )
                            paused = True
                        break

            if paused:
                return

            reasoning_parts, answer_parts, _ = reasoning_parser.finish()
            for reasoning_part in reasoning_parts:
                if active_reasoning is None:
                    active_reasoning = reasoning_collector.start()
                    active_reasoning_is_tagged = True
                reasoning_content = reasoning_collector.append(active_reasoning, reasoning_part)
                if reasoning_content:
                    yield _sse_event(
                        "reasoning_token",
                        session_id,
                        trace_id,
                        {
                            "content": reasoning_content,
                            "reasoning_id": active_reasoning["reasoning_id"],
                            "phase": active_reasoning["phase"],
                            "round_number": active_reasoning["round_number"],
                        },
                    )
            if active_reasoning is not None:
                yield _sse_event(
                    "reasoning_done",
                    session_id,
                    trace_id,
                    {
                        "reasoning_id": active_reasoning["reasoning_id"],
                        "round_number": active_reasoning["round_number"],
                    },
                )
                active_reasoning = None
            for answer_part in answer_parts:
                full_response.append(answer_part)
                yield _sse_event("token", session_id, trace_id, {"content": answer_part})

            answer = "".join(full_response) or final_content
            if answer and not full_response:
                yield _sse_event("token", session_id, trace_id, {"content": answer})
            if answer:
                async with async_session_factory() as db:
                    message = await MessageService(db).save_message(
                        sid,
                        user_id,
                        "assistant",
                        answer,
                        sources=response_sources,
                        reasoning=[record for record in reasoning_collector.records if record["content"]],
                    )
                    await ToolCallService(db).link_message(record_trace_id, message.id)
                    await SessionService(db).touch(sid)
                    await db.commit()
            if answer and title_source_message:
                await self._enqueue_session_title(
                    sid,
                    user_id,
                    title_source_message,
                    answer,
                    model,
                )

            logger.info(
                "Agent对话完成: session_id=%s, trace_id=%s, answer_length=%d, cost=%dms",
                session_id,
                trace_id,
                len(answer),
                int((time.monotonic() - started) * 1000),
            )
            yield _sse_event(
                "final",
                session_id,
                trace_id,
                {"done": True, "tool_call_count": len(seen_tool_calls)},
            )
        except TimeoutError:
            await self._safe_cancel_running_tools(record_trace_id)
            error_content = "错误: Agent执行超时，请稍后重试"
            if full_response or final_content:
                error_content = f"{''.join(full_response) or final_content}\n\n{error_content}"
            await self._save_assistant_error_message(sid, user_id, record_trace_id, error_content)
            yield _sse_event(
                "status",
                session_id,
                trace_id,
                {"stage": "global_timeout", "timeout_seconds": settings.agent_timeout_seconds},
            )
            yield _sse_event("error", session_id, trace_id, {"message": "Agent执行超时，请稍后重试"})
        except asyncio.CancelledError:
            logger.warning(
                "Agent流式连接中断或任务被取消: session_id=%s, trace_id=%s, cost=%dms, tool_calls=%d",
                session_id,
                trace_id,
                int((time.monotonic() - started) * 1000),
                len(seen_tool_calls),
            )
            self._schedule_cancel_cleanup(record_trace_id)
            return
        except Exception:  # noqa: BLE001 - SSE 中返回受控错误
            logger.exception("Agent流式生成失败: session_id=%s, trace_id=%s", session_id, trace_id)
            await self._safe_cancel_running_tools(record_trace_id)
            error_content = "错误: 模型或工具服务异常，请稍后重试"
            if full_response or final_content:
                error_content = f"{''.join(full_response) or final_content}\n\n{error_content}"
            await self._save_assistant_error_message(sid, user_id, record_trace_id, error_content)
            yield _sse_event("error", session_id, trace_id, {"message": "模型或工具服务异常，请稍后重试"})
        finally:
            running = self._running_tasks.get(trace_id)
            if running is not None and running[2] is current_task:
                self._running_tasks.pop(trace_id, None)

    async def _persist_status_event(self, session_id: uuid.UUID, payload: dict[str, Any]) -> None:
        """将工具 custom 状态事件同步到数据库。"""
        call_id = payload.get("tool_call_id")
        stage = payload.get("stage")
        if not call_id or not stage:
            return
        status_map = {
            "tool_running": "running",
            "tool_done": "success",
            "tool_failed": "failed",
            "tool_timeout": "timeout",
            "tool_rejected": "rejected",
            "tool_cancelled": "cancelled",
        }
        status = status_map.get(str(stage))
        if status is None:
            return
        async with async_session_factory() as db:
            await ToolCallService(db).update_status(
                session_id,
                str(call_id),
                status,
                error_message=str(payload.get("message")) if payload.get("message") else None,
                duration_ms=int(payload["duration_ms"]) if isinstance(payload.get("duration_ms"), int | float) else None,
            )
            await db.commit()
