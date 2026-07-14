"""
@author: caoshuai.cs
@date: 2026-07-14 23:32
@description: 为对话消息增加 RAG 引用来源持久化字段
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_add_chat_message_sources"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """增加引用来源 JSONB 字段。"""
    op.add_column(
        "chat_message",
        sa.Column("sources", postgresql.JSONB(), nullable=True, comment="RAG引用来源"),
    )


def downgrade() -> None:
    """移除引用来源字段。"""
    op.drop_column("chat_message", "sources")
