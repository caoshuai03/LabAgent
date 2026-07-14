"""
@author: caoshuai.cs
@date: 2026-07-14
@description: 文档切分服务——QA 语料专用切分（保留完整问答对）+ 普通文档 Token 切分（chunk 参数可配）
"""
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings

# QA 语料标识常量：分隔符、问题前缀、答案前缀
_QA_SEPARATOR = "---"
_QUESTION_PREFIX = "Q:"
_ANSWER_PREFIX = "A:"


def split_documents(documents: list[Document]) -> list[Document]:
    """切分入口：探测是否为 QA 语料，命中走 QA 切分，否则走普通 Token 切分。"""
    if _is_qa_corpus(documents):
        return _split_qa(documents)
    return _split_token(documents)


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


def _split_token(documents: list[Document]) -> list[Document]:
    """普通文档按 token 计数切分，chunk_size / overlap 从 Settings 读取。"""
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
    )
    return splitter.split_documents(documents)
