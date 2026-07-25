"""
@author: caoshuai.cs
@date: 2026-07-26 01:42
@description: 移除会话标题生成状态字段，标题更新改为前端静默检测
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_remove_title_status"
down_revision: str | None = "0007_add_title_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """删除标题生成状态字段。"""
    op.drop_column("chat_session", "title_status")


def downgrade() -> None:
    """恢复标题生成状态字段。"""
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
