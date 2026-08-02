"""
@author: caoshuai.cs
@date: 2026-07-14
@description: 文档切分服务——QA 专用切分、Markdown 标题感知切分与普通文档 Token 切分
"""
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from app.core.config import settings
from app.services.context_token_counter import context_token_counter

# QA 语料标识常量：分隔符、问题前缀、答案前缀
_QA_SEPARATOR = "---"
_QUESTION_PREFIX = "Q:"
_ANSWER_PREFIX = "A:"
_MARKDOWN_EXTENSIONS = {".md", ".markdown"}
_MARKDOWN_HEADERS = [
    ("#", "chapter_name"),
    ("##", "section_name"),
    ("###", "subsection_name"),
]
_MAX_TITLE_CONTEXT_RATIO = 0.25


def split_documents(documents: list[Document]) -> list[Document]:
    """切分入口：QA 优先，Markdown 先按标题分段，其余文档直接按 Token 切分。"""
    if _is_qa_corpus(documents):
        chunks = _split_qa(documents)
        return _finalize_chunks(chunks, add_title_context=False)
    is_markdown = _is_markdown(documents)
    chunks = _split_markdown(documents) if is_markdown else _split_token(documents)
    return _finalize_chunks(chunks, add_title_context=is_markdown)


def _is_markdown(documents: list[Document]) -> bool:
    """根据 loader 写入的 source 扩展名判断是否为 Markdown。"""
    return bool(documents) and all(
        str(doc.metadata.get("source", "")).lower().endswith(tuple(_MARKDOWN_EXTENSIONS))
        for doc in documents
    )


def _split_markdown(documents: list[Document]) -> list[Document]:
    """先按 Markdown 标题层级切分并保留章节元数据，再按 Token 控制最终切片大小。"""
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_MARKDOWN_HEADERS,
        strip_headers=False,
    )
    sections: list[Document] = []
    for document in documents:
        for section in header_splitter.split_text(document.page_content):
            section.metadata = {**document.metadata, **section.metadata}
            sections.append(section)
    chunks: list[Document] = []
    for section in sections:
        title_context = _build_title_context(section.metadata)
        if not title_context:
            chunks.extend(_split_token([section]))
            continue
        max_title_tokens = max(1, int(settings.rag_chunk_size * _MAX_TITLE_CONTEXT_RATIO))
        title_context = context_token_counter.truncate_text(title_context, max_title_tokens)
        prefix = f"标题路径：{title_context}\n\n"
        body_chunk_size = max(1, settings.rag_chunk_size - context_token_counter.count_text(prefix))
        section.metadata["_title_context"] = title_context
        chunks.extend(
            _split_token(
                [section],
                chunk_size=body_chunk_size,
                chunk_overlap=min(settings.rag_chunk_overlap, max(body_chunk_size - 1, 0)),
            )
        )
    return chunks


def _finalize_chunks(chunks: list[Document], *, add_title_context: bool) -> list[Document]:
    """补齐稳定切片元数据，并让 Markdown 标题路径参与 embedding。"""
    for index, chunk in enumerate(chunks):
        source = str(chunk.metadata.get("source") or "")
        chunk.metadata["file_name"] = str(chunk.metadata.get("file_name") or source)
        chunk.metadata["chunk_index"] = index
        if not add_title_context:
            continue
        title_context = str(chunk.metadata.pop("_title_context", ""))
        if title_context:
            chunk.page_content = f"标题路径：{title_context}\n\n{chunk.page_content}"
    return chunks


def _build_title_context(metadata: dict[str, object]) -> str:
    """根据课程与标题层级构造用于 embedding 的短路径。"""
    title_path = [
        str(metadata[key])
        for key in ("course_name", "chapter_name", "section_name", "subsection_name")
        if metadata.get(key)
    ]
    return " > ".join(title_path)


def _is_qa_corpus(documents: list[Document]) -> bool:
    """按内容是否含 --- 分隔符与 Q: 问题前缀判定是否为 QA 语料。"""
    for doc in documents:
        content = doc.page_content
        if _QA_SEPARATOR in content and _QUESTION_PREFIX in content:
            return True
    return False


def _split_qa(documents: list[Document]) -> list[Document]:
    """QA 专用切分：按 --- 切块，每个 Q/A 对生成一个不被打散的 chunk。"""
    result: list[Document] = []
    for doc in documents:
        blocks = doc.page_content.split(_QA_SEPARATOR)
        for index, raw in enumerate(blocks):
            block = raw.strip()
            if not block or _QUESTION_PREFIX not in block:
                continue
            question, answer = _parse_qa_pair(block)
            if not question or not answer:
                continue
            metadata = dict(doc.metadata)
            metadata.update({"qa_index": index, "question": question, "content_type": "qa_pair"})
            result.append(Document(page_content=f"问题: {question}\n\n答案: {answer}", metadata=metadata))
    return result


def _parse_qa_pair(block: str) -> tuple[str, str]:
    """从 QA 块中解析出问题与答案；解析失败返回空串。"""
    question_start = block.find(_QUESTION_PREFIX)
    answer_start = block.find(_ANSWER_PREFIX, question_start + len(_QUESTION_PREFIX))
    if question_start == -1 or answer_start == -1:
        return "", ""
    question = block[question_start + len(_QUESTION_PREFIX):answer_start].strip()
    answer = block[answer_start + len(_ANSWER_PREFIX):].strip()
    return question, answer


def _split_token(
    documents: list[Document],
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Document]:
    """普通文档按 token 计数切分，chunk_size / overlap 从 Settings 读取。"""
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="o200k_base",
        chunk_size=chunk_size if chunk_size is not None else settings.rag_chunk_size,
        chunk_overlap=chunk_overlap if chunk_overlap is not None else settings.rag_chunk_overlap,
    )
    return splitter.split_documents(documents)
