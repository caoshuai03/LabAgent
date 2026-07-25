"""
@author: caoshuai.cs
@date: 2026-07-14
@description: RAG 检索支持层——MultiQuery 多角度扩展 + 向量/BM25 混合召回(RRF) + 大模型 rerank 精排，供 search_knowledge_base 工具调用
              rag_store 为同步组件，用 asyncio.to_thread 隔离；MultiQuery/Ensemble/rerank 均复用 LangChain 框架能力
"""
import asyncio
import logging
import time

from langchain.retrievers import EnsembleRetriever, MultiQueryRetriever
from langchain.retrievers.document_compressors.listwise_rerank import LLMListwiseRerank
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate

from app.core.config import settings
from app.services import rag_store
from app.services.model_provider import model_provider

logger = logging.getLogger("labagent")

# 命中相关度写入 doc.metadata 的键，供引用来源展示相关度分数
_RELEVANCE_SCORE_KEY = "_relevance_score"
# 引用来源摘要最大长度
_SNIPPET_MAX_LEN = 120


def _build_query_rewrite_prompt() -> PromptTemplate:
    """构建 MultiQuery 改写提示词：生成固定数量改写，并由框架额外包含原问题。"""
    query_count = max(1, settings.rag_multi_query_count)
    return PromptTemplate(
        input_variables=["question"],
        partial_variables={"query_count": str(query_count)},
        template=(
            "你是课程知识库检索查询改写助手。请从不同表述角度生成 {query_count} 个检索问题，"
            "用于提升向量检索和关键词检索的召回。不要回答问题，不要解释。\n"
            "原问题：{question}\n"
            "每行只输出一个改写后的检索问题："
        ),
    )


def build_sources(documents: list[Document]) -> list[dict]:
    """把 rerank 后的文档整理为结构化引用来源（file_name / snippet / score，全蛇形）。

    混合检索(RRF)与 rerank 均不产生可比的相关度分数，仅当文档带有向量相关度时才输出 score。
    """
    sources: list[dict] = []
    for doc in documents:
        content = doc.page_content or ""
        snippet = content[:_SNIPPET_MAX_LEN].strip()
        source: dict = {
            "file_name": doc.metadata.get("source"),
            "snippet": snippet,
        }
        if _RELEVANCE_SCORE_KEY in doc.metadata:
            source["score"] = round(float(doc.metadata[_RELEVANCE_SCORE_KEY]), 4)
        sources.append(source)
    return sources


def _build_retriever():
    """构建「MultiQuery 多角度扩展 → 向量 + BM25 混合召回(RRF)」检索器（同步，供 to_thread 调用）。"""
    hybrid_retriever = rag_store.build_hybrid_retriever(
        vector_top_k=settings.rag_top_k, bm25_top_k=settings.rag_bm25_top_k
    )
    return MultiQueryRetriever.from_llm(
        retriever=hybrid_retriever,
        llm=model_provider.get_query_rewrite_model(),
        prompt=_build_query_rewrite_prompt(),
        include_original=True,
    )


def _retrieve_sync(query: str) -> list[Document]:
    """在线程内使用同步接口完成检索，避免同步 PGVector 被框架切换到异步接口。"""
    return list(_build_retriever().invoke(query))


def _deduplicate_queries(queries: list[str]) -> list[str]:
    """保持顺序去重，避免同一个改写重复进入全局 RRF。"""
    seen: set[str] = set()
    unique_queries: list[str] = []
    for query in queries:
        stripped = query.strip()
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        unique_queries.append(stripped)
    return unique_queries


def _retrieve_with_query_rrf_sync(query: str) -> list[Document]:
    """对原问题和 MultiQuery 改写的召回结果再做一次 RRF 融合。"""
    multi_query_retriever = _build_retriever()
    generated_queries = list(multi_query_retriever.llm_chain.invoke({"question": query}))
    queries = _deduplicate_queries([query, *generated_queries])
    document_lists = [
        list(multi_query_retriever.retriever.invoke(item))
        for item in queries
    ]
    if not document_lists:
        return []
    fusion_retriever = EnsembleRetriever(
        retrievers=[],
        weights=[1.0] * len(document_lists),
    )
    return list(fusion_retriever.weighted_reciprocal_rank(document_lists))


async def retrieve(query: str) -> list[Document]:
    """MultiQuery 多角度扩展 + 向量/BM25 混合召回(RRF 融合)，返回去重后的候选文档。"""
    started = time.monotonic()
    logger.info("RAG 混合召回开始: query_len=%d", len(query))
    documents = await asyncio.to_thread(_retrieve_sync, query)
    logger.info(
        "RAG 混合召回完成: query_len=%d, rewrite_count=%d, include_original=%s, top_k=%d, bm25_top_k=%d, 候选=%d, cost=%dms",
        len(query), settings.rag_multi_query_count, True, settings.rag_top_k, settings.rag_bm25_top_k, len(documents),
        int((time.monotonic() - started) * 1000),
    )
    return documents


async def retrieve_with_query_rrf(query: str) -> list[Document]:
    """MultiQuery 多路召回后按 query 维度 RRF 融合，供关闭 rerank 的评测分支使用。"""
    started = time.monotonic()
    logger.info("RAG 多查询 RRF 召回开始: query_len=%d", len(query))
    documents = await asyncio.to_thread(_retrieve_with_query_rrf_sync, query)
    logger.info(
        "RAG 多查询 RRF 召回完成: query_len=%d, rewrite_count=%d, include_original=%s, 候选=%d, cost=%dms",
        len(query), settings.rag_multi_query_count, True, len(documents),
        int((time.monotonic() - started) * 1000),
    )
    return documents


async def rerank(query: str, documents: list[Document]) -> list[Document]:
    """大模型 rerank 精排取 top_n；未启用或无候选时退化为按召回顺序截断。"""
    if not documents:
        return documents
    top_n = settings.rag_rerank_top_n
    if not settings.rag_rerank_enabled:
        return documents[:top_n]
    reranker = LLMListwiseRerank.from_llm(llm=model_provider.get_rerank_model(), top_n=top_n)
    started = time.monotonic()
    try:
        async with asyncio.timeout(settings.rag_rerank_timeout_seconds):
            reranked = await reranker.acompress_documents(documents, query)
    except TimeoutError:
        logger.warning(
            "RAG rerank 超时，退化为召回顺序: query_len=%d, in=%d, timeout=%ds, cost=%dms",
            len(query), len(documents), settings.rag_rerank_timeout_seconds,
            int((time.monotonic() - started) * 1000),
        )
        return documents[:top_n]
    except asyncio.CancelledError:
        logger.warning(
            "RAG rerank 被取消: query_len=%d, in=%d, cost=%dms",
            len(query), len(documents), int((time.monotonic() - started) * 1000),
        )
        raise
    except Exception:  # noqa: BLE001 - rerank 是增强步骤，异常时保留粗召回结果
        logger.exception(
            "RAG rerank 异常，退化为召回顺序: query_len=%d, in=%d, cost=%dms",
            len(query), len(documents), int((time.monotonic() - started) * 1000),
        )
        return documents[:top_n]
    logger.info(
        "RAG rerank 完成: query_len=%d, in_chunks=%d, out_chunks=%d, cost=%dms",
        len(query), len(documents), len(reranked), int((time.monotonic() - started) * 1000),
    )
    return list(reranked)
