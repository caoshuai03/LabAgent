"""
@author: caoshuai.cs
@date: 2026-07-26 01:24
@description: 增加会话标题异步生成状态字段
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_add_title_status"
down_revision: str | None = "0006_add_kb_upload_task"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """增加标题生成状态；历史会话视为已完成。"""
    op.add_column(
        "chat_session",
        sa.Column(
            "title_status",
            sa.String(length=20),
            server_default="succeeded",
            nullable=False,
            comment="标题生成状态",
        ),
    )


def downgrade() -> None:
    """删除标题生成状态字段。"""
    op.drop_column("chat_session", "title_status")
