"""
@author: caoshuai.cs
@date: 2026-07-14
@description: RAG 向量存储与索引层——PGVector 托管向量表 + SQLRecordManager 切片索引，封装增量索引/按来源删除/检索
              langchain 的 PGVector/index/SQLRecordManager 为同步组件，异步 service 调用时须用 asyncio.to_thread 隔离
"""
from langchain.indexes import SQLRecordManager, index
from langchain_core.documents import Document
from langchain_postgres import PGVector

from app.core.config import settings
from app.services.model_provider import model_provider

# 全局单例，随首次使用惰性构建
_vector_store: PGVector | None = None
_record_manager: SQLRecordManager | None = None


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


def search_with_score(query: str, k: int) -> list[tuple[Document, float]]:
    """向量相似度检索，返回 (文档, 距离分数) 列表。"""
    return _get_vector_store().similarity_search_with_score(query, k=k)
