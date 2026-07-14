"""
@author: caoshuai.cs
@date: 2026-07-14
@description: RAG 检索支持层——向量粗召回 + 大模型 rerank 精排，供检索图节点调用
              rag_store 为同步组件，用 asyncio.to_thread 隔离；rerank 复用 LLMListwiseRerank 框架能力
"""
import asyncio
import logging

from langchain.retrievers.document_compressors.listwise_rerank import LLMListwiseRerank
from langchain_core.documents import Document

from app.core.config import settings
from app.services import rag_store
from app.services.model_provider import model_provider

logger = logging.getLogger("labagent")

# 命中相似度写入 doc.metadata 的键，供引用来源展示相似度分数
_SIMILARITY_KEY = "_similarity"
# 引用来源摘要最大长度
_SNIPPET_MAX_LEN = 120


def build_sources(documents: list[Document]) -> list[dict]:
    """把 rerank 后的文档整理为结构化引用来源（file_name / snippet / score，全蛇形）。"""
    sources: list[dict] = []
    for doc in documents:
        content = doc.page_content or ""
        snippet = content[:_SNIPPET_MAX_LEN].strip()
        sources.append({
            "file_name": doc.metadata.get("source"),
            "snippet": snippet,
            "score": round(float(doc.metadata.get(_SIMILARITY_KEY, 0.0)), 4),
        })
    return sources


async def retrieve(query: str) -> list[Document]:
    """向量粗召回 + 相似度初筛，返回命中文档（相似度写入 metadata）。"""
    pairs = await asyncio.to_thread(rag_store.search_with_score, query, settings.rag_top_k)
    logger.info(
        "RAG 向量召回: query=%r, top_k=%d, threshold=%.2f, 原始召回=%d",
        query, settings.rag_top_k, settings.rag_similarity_threshold, len(pairs),
    )
    documents: list[Document] = []
    for doc, distance in pairs:
        # PGVector 默认 COSINE 距离，转为相似度分数（1 - 距离），按阈值初筛
        similarity = 1.0 - float(distance)
        source = doc.metadata.get("source")
        if similarity < settings.rag_similarity_threshold:
            continue
        doc.metadata[_SIMILARITY_KEY] = similarity
        documents.append(doc)
    logger.info(
        "RAG 粗召回完成: query_len=%d, 原始召回=%d, 最终 hit=%d",
        len(query), len(pairs), len(documents),
    )
    return documents


async def rerank(query: str, documents: list[Document]) -> list[Document]:
    """大模型 rerank 精排取 top_n；未启用或无候选时退化为按粗召回顺序截断。"""
    if not documents:
        return documents
    top_n = settings.rag_rerank_top_n
    if not settings.rag_rerank_enabled:
        return documents[:top_n]
    reranker = LLMListwiseRerank.from_llm(llm=model_provider.get_rerank_model(), top_n=top_n)
    logger.info("RAG rerank 开始: in=%d, top_n=%d", len(documents), top_n)
    reranked = await reranker.acompress_documents(documents, query)
    logger.info("RAG rerank 完成: in=%d, out=%d", len(documents), len(reranked))
    return list(reranked)
