"""
@author: caoshuai.cs
@date: 2026-08-02
@description: Markdown front matter 文档元数据解析测试
"""
import pytest

from app.core.errors import BusinessException
from app.services.document_loader import extract_file_metadata, load_documents


def test_markdown_front_matter_is_extracted_and_removed_from_content() -> None:
    """受控 front matter 应进入 metadata，且不作为正文参与切分和 embedding。"""
    data = b"""---
course_name: "Machine Learning"
source_url: "https://example.com/course"
license: "MIT"
ignored: "value"
---
# Linear Regression

Content.
"""

    documents = load_documents("course.md", data)

    assert len(documents) == 1
    assert documents[0].page_content.startswith("# Linear Regression")
    assert documents[0].metadata == {
        "source": "course.md",
        "file_name": "course.md",
        "course_name": "Machine Learning",
    }
    assert extract_file_metadata("course.md", data) == {
        "course_name": "Machine Learning",
        "source_url": "https://example.com/course",
        "license": "MIT",
    }


def test_markdown_front_matter_rejects_unsafe_source_url() -> None:
    """来源链接只允许 HTTP/HTTPS，避免危险协议进入后续展示。"""
    data = b"""---
source_url: "javascript:alert(1)"
---
# Course
"""

    with pytest.raises(BusinessException, match="仅支持 HTTP/HTTPS"):
        load_documents("course.md", data)
