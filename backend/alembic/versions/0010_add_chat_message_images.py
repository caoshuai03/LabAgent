"""
@author: caoshuai.cs
@date: 2026-07-31
@description: 为对话消息增加图片附件元数据字段
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_add_chat_message_images"
down_revision: str | None = "0009_add_chat_message_reasoning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """增加聊天图片附件字段。"""
    op.add_column(
        "chat_message",
        sa.Column("images", postgresql.JSONB(), nullable=True, comment="用户消息图片附件"),
    )


def downgrade() -> None:
    """移除聊天图片附件字段。"""
    op.drop_column("chat_message", "images")
