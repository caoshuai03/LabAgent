"""
@author: caoshuai.cs
@date: 2026-07-16 10:00
@description: 知识库检索工具 search_knowledge_base——检索即工具，由模型自主决定检索时机与次数
              内部复用 MultiQuery + 向量/BM25 混合召回(RRF) + rerank，命中来源经 custom writer 下发前端
"""
import asyncio
import logging
import time
from typing import Annotated, Any

from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState

from app.core.config import settings
from app.services import rag_retrieval
from app.services import rag_store
from app.services.model_provider import model_provider
from app.tools.result import result_envelope, safe_stream_writer, truncate_text

logger = logging.getLogger("labagent")

# 单条命中片段进入模型上下文的最大长度，避免长文档挤占对话窗口
_HIT_SNIPPET_MAX_LEN = 600
_MIN_RETRIEVAL_TOP_K = 1
_MAX_RETRIEVAL_TOP_K = 20


class _EmbeddingModelUnavailableError(RuntimeError):
    """Ollama Embedding 模型预检不可用。"""


def _format_hits(documents: list) -> str:
    """把命中文档渲染为供模型阅读的参考资料文本。"""
    parts: list[str] = []
    for document in documents:
        citation_id = rag_retrieval.build_citation_id(document)
        source = document.metadata.get("source") or document.metadata.get("file_name") or "未知来源"
        title_path = [
            str(document.metadata[key])
            for key in ("course_name", "chapter_name", "section_name")
            if document.metadata.get(key)
        ]
        location = f"\n标题路径: {' > '.join(title_path)}" if title_path else ""
        content = truncate_text(
            rag_retrieval.strip_title_context(document.page_content or ""),
            _HIT_SNIPPET_MAX_LEN,
        )
        parts.append(f"[资料{citation_id}] 来源: {source}{location}\n{content}")
    return "\n\n".join(parts)


def _resolve_top_k(value: Any) -> int:
    """解析评测注入的 top_k，避免异常值放大检索开销。"""
    try:
        top_k = int(value)
    except (TypeError, ValueError):
        top_k = settings.rag_rerank_top_n
    return min(max(top_k, _MIN_RETRIEVAL_TOP_K), _MAX_RETRIEVAL_TOP_K)


@tool("search_knowledge_base")
async def search_knowledge_base(
    query: str,
    state: Annotated[dict[str, Any], InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str:
    """Search the course knowledge base for materials relevant to the query.

    Call this whenever the user asks about course knowledge, lab requirements, or
    concepts that may be documented. Pass a focused, self-contained search query.
    """
    started = time.monotonic()
    writer = safe_stream_writer()
    writer({
        "tool_event": {
            "event_type": "status",
            "payload": {
                "stage": "tool_running",
                "tool_call_id": tool_call_id,
                "tool_name": "search_knowledge_base",
            },
        }
    })
    try:
        if not await model_provider.embedding_model_available():
            raise _EmbeddingModelUnavailableError("Ollama Embedding 模型不可用")
        current_state = state or {}
        retrieval_mode = str(current_state.get("rag_retrieval_mode") or "current")
        top_k = _resolve_top_k(current_state.get("rag_retrieval_top_k"))
        if retrieval_mode == "vector_only":
            retriever = rag_store.build_vector_retriever(top_k)
            documents = await asyncio.to_thread(lambda: list(retriever.invoke(query)))
        else:
            documents = await rag_retrieval.retrieve(query)
            documents = await rag_retrieval.rerank(query, documents)
        sources = rag_retrieval.build_sources(documents)
        if sources:
            writer({"sources": sources})
        duration_ms = int((time.monotonic() - started) * 1000)
        writer({
            "tool_event": {
                "event_type": "status",
                "payload": {
                    "stage": "tool_done",
                    "tool_call_id": tool_call_id,
                    "tool_name": "search_knowledge_base",
                    "success": True,
                    "duration_ms": duration_ms,
                },
            }
        })
        if not documents:
            return result_envelope(
                success=True,
                output="（知识库中未检索到相关资料）",
                summary="知识库未命中相关资料",
                duration_ms=duration_ms,
            )
        return result_envelope(
            success=True,
            output=_format_hits(documents),
            summary=f"命中 {len(documents)} 条知识库资料",
            duration_ms=duration_ms,
        )
    except TimeoutError as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.warning(
            "知识库检索超时，已降级: query_len=%d, cost=%dms",
            len(query), duration_ms,
        )
        writer({
            "tool_event": {
                "event_type": "status",
                "payload": {
                    "stage": "tool_timeout",
                    "tool_call_id": tool_call_id,
                    "tool_name": "search_knowledge_base",
                    "success": False,
                    "duration_ms": duration_ms,
                    "message": "知识库检索超时",
                },
            }
        })
        return result_envelope(
            success=False,
            output="知识库检索超时。",
            summary="知识库检索超时，已降级",
            error=truncate_text(str(exc) or "知识库检索超时", 500),
            error_type="timeout",
            duration_ms=duration_ms,
        )
    except _EmbeddingModelUnavailableError as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.warning(
            "知识库检索已降级: model=%s, query_len=%d, cost=%dms",
            settings.ollama_embedding_model, len(query), duration_ms,
        )
        message = str(exc)
        writer({
            "tool_event": {
                "event_type": "status",
                "payload": {
                    "stage": "tool_failed",
                    "tool_call_id": tool_call_id,
                    "tool_name": "search_knowledge_base",
                    "success": False,
                    "duration_ms": duration_ms,
                    "message": message,
                },
            }
        })
        return result_envelope(
            success=False,
            output="（知识库检索暂不可用，请基于已有信息回答或稍后重试）",
            summary="Embedding模型不可用，知识库检索已降级",
            error=message,
            error_type="embedding_unavailable",
            duration_ms=duration_ms,
        )
    except asyncio.CancelledError:
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.warning(
            "知识库工具被取消: query_len=%d, cost=%dms",
            len(query), duration_ms,
        )
        writer({
            "tool_event": {
                "event_type": "status",
                "payload": {
                    "stage": "tool_cancelled",
                    "tool_call_id": tool_call_id,
                    "tool_name": "search_knowledge_base",
                    "success": False,
                    "duration_ms": duration_ms,
                    "message": "知识库工具被取消",
                },
            }
        })
        raise
    except Exception as exc:  # noqa: BLE001 - 检索失败降级为无资料，不阻断对话
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.exception("知识库检索失败，已降级: query_len=%d", len(query))
        message = truncate_text(str(exc), 500)
        writer({
            "tool_event": {
                "event_type": "status",
                "payload": {
                    "stage": "tool_failed",
                    "tool_call_id": tool_call_id,
                    "tool_name": "search_knowledge_base",
                    "success": False,
                    "duration_ms": duration_ms,
                    "message": message,
                },
            }
        })
        return result_envelope(
            success=False,
            output="（知识库检索暂不可用，请基于已有信息回答或稍后重试）",
            summary="知识库检索失败，已降级",
            error=message,
            error_type="exception",
            duration_ms=duration_ms,
        )


KNOWLEDGE_TOOLS = [search_knowledge_base]
