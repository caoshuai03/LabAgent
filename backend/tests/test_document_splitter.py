"""
@author: caoshuai.cs
@date: 2026-08-02
@description: 文档切分服务测试
"""
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from app.services import document_splitter
from app.services.context_token_counter import context_token_counter


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


def test_markdown_splits_by_headers_before_token_limit() -> None:
    """Markdown 应先按标题分段，二次 Token 切分后仍保留来源与标题层级。"""
    long_section = "这是线性回归实验步骤。" * 300
    documents = [
        Document(
            page_content=f"# 机器学习\n\n课程介绍。\n\n## 线性回归\n\n{long_section}",
            metadata={
                "source": "机器学习.md",
                "file_name": "机器学习.md",
                "course_name": "机器学习基础",
            },
        )
    ]

    chunks = document_splitter.split_documents(documents)
    section_chunks = [
        chunk for chunk in chunks if chunk.metadata.get("section_name") == "线性回归"
    ]

    assert len(section_chunks) > 1
    assert all(chunk.metadata["source"] == "机器学习.md" for chunk in chunks)
    assert all(chunk.metadata["chapter_name"] == "机器学习" for chunk in section_chunks)
    assert all(chunk.metadata["section_name"] == "线性回归" for chunk in section_chunks)
    assert [chunk.metadata["chunk_index"] for chunk in chunks] == list(range(len(chunks)))
    assert all(
        chunk.page_content.startswith("标题路径：机器学习基础 > 机器学习 > 线性回归")
        for chunk in section_chunks
    )
    assert all(
        context_token_counter.count_text(chunk.page_content)
        <= document_splitter.settings.rag_chunk_size
        for chunk in chunks
    )
    assert any("# 机器学习" in chunk.page_content for chunk in chunks)


def test_markdown_qa_corpus_keeps_qa_pair_splitter_priority() -> None:
    """Markdown QA 语料仍应保持完整问答对，不进入标题切分。"""
    documents = [
        Document(
            page_content="# 常见问题\n\nQ: 如何提交实验？\nA: 在实验平台提交。\n---",
            metadata={"source": "faq.md"},
        )
    ]

    chunks = document_splitter.split_documents(documents)

    assert len(chunks) == 1
    assert chunks[0].metadata["content_type"] == "qa_pair"
    assert chunks[0].metadata["source"] == "faq.md"
