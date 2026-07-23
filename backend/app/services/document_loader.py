"""
@author: caoshuai.cs
@date: 2026-07-14
@description: 文档解析服务——把上传的文件字节按扩展名解析为 langchain Document 列表（PDF/Markdown/TXT）
"""
import os
import tempfile

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document

from app.core.errors import BusinessException, ErrorCode


def load_documents(file_name: str, data: bytes) -> list[Document]:
    """按扩展名把文件字节解析为 Document 列表；解析失败抛业务异常，阻断入库避免脏数据。

    metadata 统一写入 source=file_name，供 Indexing API 的 source_id_key 与引用来源使用。
    """
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    # 临时落盘：社区 loader 以文件路径为输入，写入后即删除
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        loader = _build_loader(ext, tmp_path)
        documents = loader.load()
    except BusinessException:
        raise
    except Exception as exc:  # noqa: BLE001 - 解析失败统一转业务异常
        raise BusinessException(ErrorCode.FILE_ERROR, f"文件解析失败：{file_name}") from exc
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    if not documents:
        raise BusinessException(ErrorCode.FILE_ERROR, f"文件内容为空：{file_name}")
    for doc in documents:
        doc.metadata["source"] = file_name
    return documents


def _build_loader(ext: str, path: str):
    """按扩展名返回对应 loader。"""
    if ext == "pdf":
        return PyPDFLoader(path)
    if ext in {"md", "markdown"}:
        return TextLoader(path, encoding="utf-8")
    if ext == "txt":
        return TextLoader(path, encoding="utf-8")
    raise BusinessException(ErrorCode.PARAMS_ERROR, f"不支持的文件类型：{ext}")
