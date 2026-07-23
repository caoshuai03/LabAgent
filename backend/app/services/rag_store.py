"""
@author: caoshuai.cs
@date: 2026-07-14
@description: RAG 向量存储与索引层——PGVector 托管向量表 + SQLRecordManager 切片索引，封装增量索引/按来源删除/检索
              langchain 的 PGVector/index/SQLRecordManager 为同步组件，异步 service 调用时须用 asyncio.to_thread 隔离
"""
import re

from langchain.indexes import SQLRecordManager, index
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_postgres import PGVector

from app.core.config import settings
from app.services.model_provider import model_provider

# 全局单例，随首次使用惰性构建
_vector_store: PGVector | None = None
_record_manager: SQLRecordManager | None = None

# BM25 内存索引缓存：切片集合未变时复用，避免每次检索都全量重建倒排索引
_bm25_retriever: BM25Retriever | None = None
_bm25_fingerprint: int | None = None

# BM25 中文分词：默认空格分词对中文无效，这里按「英文/数字词 + 中文单字」切分，
# 无需引入额外分词依赖即可让关键词召回对中文生效
_BM25_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]")


def _bm25_preprocess(text: str) -> list[str]:
    """BM25 分词：英文/数字按词、中文按单字，统一小写。"""
    return _BM25_TOKEN_PATTERN.findall(text.lower())


def _get_vector_store() -> PGVector:
    """获取 PGVector 单例（同步 psycopg 连接），维度由配置固定以约束嵌入模型一致性。"""
    global _vector_store
    if _vector_store is None:
        _vector_store = PGVector(
            embeddings=model_provider.get_embedding_model(),
            collection_name=settings.rag_collection_name,
            connection=settings.vector_database_url,
            embedding_length=settings.rag_embedding_dim,
            use_jsonb=True,
        )
    return _vector_store


def _get_record_manager() -> SQLRecordManager:
    """获取 SQLRecordManager 单例，命名空间区分向量库与 collection。"""
    global _record_manager
    if _record_manager is None:
        namespace = f"pgvector/{settings.rag_collection_name}"
        _record_manager = SQLRecordManager(namespace, db_url=settings.vector_database_url)
        _record_manager.create_schema()
    return _record_manager


def index_documents(documents: list[Document], source_id: str) -> dict:
    """按来源增量索引切片：写入变化切片、清理该来源下已不存在的旧切片、跳过未变切片。

    source_id 会写入每个切片 metadata 的 source_id_key 字段。返回 index() 的统计结果。
    """
    for doc in documents:
        doc.metadata["source_id"] = source_id
    return index(
        documents,
        _get_record_manager(),
        _get_vector_store(),
        cleanup="incremental",
        source_id_key="source_id",
    )


def delete_by_source(source_id: str) -> int:
    """按来源删除该文档的全部切片（向量 + 索引记录），返回删除的切片数。"""
    record_manager = _get_record_manager()
    keys = record_manager.list_keys(group_ids=[source_id])
    if not keys:
        return 0
    _get_vector_store().delete(ids=keys)
    record_manager.delete_keys(keys)
    return len(keys)


def search_with_relevance_scores(query: str, k: int) -> list[tuple[Document, float]]:
    """向量相似度检索，返回 (文档, 框架归一化相关度分数) 列表。"""
    return _get_vector_store().similarity_search_with_relevance_scores(query, k=k)


def _get_bm25_retriever(top_k: int) -> BM25Retriever | None:
    """构建/复用 BM25 内存检索器；切片集合的键指纹未变时复用缓存，无切片时返回 None。"""
    global _bm25_retriever, _bm25_fingerprint
    keys = _get_record_manager().list_keys()
    if not keys:
        _bm25_retriever = None
        _bm25_fingerprint = None
        return None
    fingerprint = hash(tuple(sorted(keys)))
    if _bm25_retriever is None or fingerprint != _bm25_fingerprint:
        documents = _get_vector_store().get_by_ids(keys)
        if not documents:
            return None
        _bm25_retriever = BM25Retriever.from_documents(
            documents, preprocess_func=_bm25_preprocess
        )
        _bm25_fingerprint = fingerprint
    _bm25_retriever.k = top_k
    return _bm25_retriever


def build_hybrid_retriever(vector_top_k: int, bm25_top_k: int) -> BaseRetriever:
    """构建向量 + BM25 的 EnsembleRetriever（内置 RRF 融合）。

    无 BM25 语料（向量库为空或取不到切片）时降级为纯向量检索器，保证检索链路不中断。
    """
    vector_retriever = _get_vector_store().as_retriever(search_kwargs={"k": vector_top_k})
    bm25_retriever = _get_bm25_retriever(bm25_top_k)
    if bm25_retriever is None:
        return vector_retriever
    return EnsembleRetriever(retrievers=[vector_retriever, bm25_retriever], weights=[0.5, 0.5])


def build_vector_retriever(vector_top_k: int) -> BaseRetriever:
    """构建纯向量检索器，供评测 baseline 使用。"""
    return _get_vector_store().as_retriever(search_kwargs={"k": vector_top_k})
