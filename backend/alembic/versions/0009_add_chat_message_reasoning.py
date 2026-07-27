"""
@author: caoshuai.cs
@date: 2026-07-26
@description: 为对话消息增加主Agent思考过程持久化字段
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_add_chat_message_reasoning"
down_revision: str | None = "0008_remove_title_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """增加主 Agent 思考过程字段。"""
    op.add_column(
        "chat_message",
        sa.Column("reasoning", postgresql.JSONB(), nullable=True, comment="主Agent思考过程"),
    )


def downgrade() -> None:
    """移除主 Agent 思考过程字段。"""
    op.drop_column("chat_message", "reasoning")
