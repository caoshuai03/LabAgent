"""
@author: caoshuai.cs
@date: 2026-08-01
@description: 为用户消息增加主动选择的Skill名称字段
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_add_message_skill_names"
down_revision: str | None = "0010_add_chat_message_images"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """增加消息Skill名称字段。"""
    op.add_column(
        "chat_message",
        sa.Column(
            "skill_names",
            postgresql.JSONB(),
            nullable=True,
            comment="用户消息主动选择的Skill名称",
        ),
    )


def downgrade() -> None:
    """移除消息Skill名称字段。"""
    op.drop_column("chat_message", "skill_names")
