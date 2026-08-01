"""
@author: caoshuai.cs
@date: 2026-08-02
@description: 文档切分服务测试
"""
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from app.services import document_splitter


def test_normal_document_uses_offline_cached_encoding() -> None:
    """普通文档应使用镜像内预缓存的 o200k_base，避免离线运行时下载编码文件。"""
    splitter = MagicMock()
    splitter.split_documents.return_value = []

    with patch.object(
        document_splitter.RecursiveCharacterTextSplitter,
        "from_tiktoken_encoder",
        return_value=splitter,
    ) as factory:
        documents = [Document(page_content="普通文档")]
        document_splitter.split_documents(documents)

    factory.assert_called_once_with(
        encoding_name="o200k_base",
        chunk_size=document_splitter.settings.rag_chunk_size,
        chunk_overlap=document_splitter.settings.rag_chunk_overlap,
    )
    splitter.split_documents.assert_called_once_with(documents)
