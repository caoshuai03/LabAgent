"""
@author: caoshuai.cs
@date: 2026-07-14
@description: 文档解析服务——把上传的文件字节按扩展名解析为 langchain Document 列表（PDF/Markdown/TXT）
"""
import os
import tempfile
from urllib.parse import urlparse

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
import yaml

from app.core.errors import BusinessException, ErrorCode

_FRONT_MATTER_DELIMITER = "---"
_MAX_FRONT_MATTER_CHARS = 16_384
_MAX_COURSE_NAME_CHARS = 200
_MAX_SOURCE_URL_CHARS = 2_048
_MAX_LICENSE_CHARS = 100


def load_documents(file_name: str, data: bytes) -> list[Document]:
    """按扩展名把文件字节解析为 Document 列表；解析失败抛业务异常，阻断入库避免脏数据。

    metadata 统一写入 source=file_name，供 Indexing API 的 source_id_key 与引用来源使用。
    """
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    file_metadata: dict[str, str] = {}
    parsed_data = data
    if ext in {"md", "markdown"}:
        markdown, file_metadata = parse_markdown_metadata(data)
        parsed_data = markdown.encode("utf-8")
    # 临时落盘：社区 loader 以文件路径为输入，写入后即删除
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp.write(parsed_data)
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
        doc.metadata["file_name"] = file_name
        if file_metadata.get("course_name"):
            doc.metadata["course_name"] = file_metadata["course_name"]
    return documents


def parse_markdown_metadata(data: bytes) -> tuple[str, dict[str, str]]:
    """解析 Markdown YAML front matter，返回去除 front matter 的正文与文件级元数据。"""
    try:
        content = data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError as exc:
        raise BusinessException(ErrorCode.FILE_ERROR, "Markdown 文件必须使用 UTF-8 编码") from exc
    if not content.startswith(f"{_FRONT_MATTER_DELIMITER}\n"):
        return content, {}
    end_marker = f"\n{_FRONT_MATTER_DELIMITER}\n"
    end_index = content.find(end_marker, len(_FRONT_MATTER_DELIMITER) + 1)
    if end_index == -1 or end_index > _MAX_FRONT_MATTER_CHARS:
        raise BusinessException(ErrorCode.FILE_ERROR, "Markdown front matter 格式错误或内容过大")
    raw_metadata = content[len(_FRONT_MATTER_DELIMITER) + 1:end_index]
    try:
        loaded = yaml.safe_load(raw_metadata) or {}
    except yaml.YAMLError as exc:
        raise BusinessException(ErrorCode.FILE_ERROR, "Markdown front matter YAML 格式错误") from exc
    if not isinstance(loaded, dict):
        raise BusinessException(ErrorCode.FILE_ERROR, "Markdown front matter 必须是对象")
    metadata = _normalize_file_metadata(loaded)
    body = content[end_index + len(end_marker):]
    return body, metadata


def extract_file_metadata(file_name: str, data: bytes) -> dict[str, str]:
    """提取可持久化的文件级元数据；非 Markdown 文件返回空字典。"""
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if ext not in {"md", "markdown"}:
        return {}
    _, metadata = parse_markdown_metadata(data)
    return metadata


def _normalize_file_metadata(metadata: dict[object, object]) -> dict[str, str]:
    """只接收受控的标量元数据，避免任意 YAML 内容进入数据库或向量 metadata。"""
    result: dict[str, str] = {}
    limits = {
        "course_name": _MAX_COURSE_NAME_CHARS,
        "source_url": _MAX_SOURCE_URL_CHARS,
        "license": _MAX_LICENSE_CHARS,
    }
    for key, max_chars in limits.items():
        value = metadata.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            raise BusinessException(ErrorCode.FILE_ERROR, f"front matter 字段 {key} 必须是字符串")
        normalized = value.strip()
        if len(normalized) > max_chars:
            raise BusinessException(ErrorCode.FILE_ERROR, f"front matter 字段 {key} 过长")
        if normalized:
            result[key] = normalized
    source_url = result.get("source_url")
    if source_url and urlparse(source_url).scheme not in {"http", "https"}:
        raise BusinessException(ErrorCode.FILE_ERROR, "front matter 字段 source_url 仅支持 HTTP/HTTPS")
    return result


def _build_loader(ext: str, path: str):
    """按扩展名返回对应 loader。"""
    if ext == "pdf":
        return PyPDFLoader(path)
    if ext in {"md", "markdown"}:
        return TextLoader(path, encoding="utf-8")
    if ext == "txt":
        return TextLoader(path, encoding="utf-8")
    raise BusinessException(ErrorCode.PARAMS_ERROR, f"不支持的文件类型：{ext}")
