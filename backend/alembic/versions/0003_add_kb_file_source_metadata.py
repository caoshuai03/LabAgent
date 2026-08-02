# @author: caoshuai.cs
# @date: 2026-08-02
# @description: 为知识库文件增加来源地址与许可证元数据
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_kb_file_source_metadata"
down_revision: str | None = "0002_add_kb_file_content_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """增加文件级来源地址与许可证字段。"""
    op.add_column(
        "ali_oss_file",
        sa.Column("source_url", sa.String(length=2048), nullable=True, comment="原始资料来源地址"),
    )
    op.add_column(
        "ali_oss_file",
        sa.Column("license", sa.String(length=100), nullable=True, comment="资料许可证"),
    )


def downgrade() -> None:
    """移除文件级来源元数据。"""
    op.drop_column("ali_oss_file", "license")
    op.drop_column("ali_oss_file", "source_url")
