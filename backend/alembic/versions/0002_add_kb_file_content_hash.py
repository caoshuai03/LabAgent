# @author: caoshuai.cs
# @date: 2026-08-02
# @description: 为知识库文件增加 SHA-256 内容哈希与唯一约束
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_kb_file_content_hash"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """增加内容哈希列；PostgreSQL 唯一约束允许历史记录保留 NULL。"""
    op.add_column(
        "ali_oss_file",
        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=True,
            comment="文件内容 SHA-256，用于重复上传检测",
        ),
    )
    op.create_unique_constraint(
        "uq_ali_oss_file_content_hash",
        "ali_oss_file",
        ["content_hash"],
    )


def downgrade() -> None:
    """移除内容哈希唯一约束与字段。"""
    op.drop_constraint(
        "uq_ali_oss_file_content_hash",
        "ali_oss_file",
        type_="unique",
    )
    op.drop_column("ali_oss_file", "content_hash")
