"""
@author: caoshuai.cs
@date: 2026-07-17 06:30
@description: 工具调用记录增加前端可见性字段
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_add_tool_call_visible"
down_revision: str | None = "0004_add_tool_output_preview"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """增加工具调用前端可见性字段。"""
    op.add_column(
        "chat_tool_call",
        sa.Column("visible", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.execute(
        sa.text(
            "UPDATE chat_tool_call SET visible = false "
            "WHERE status = 'rejected' "
            "AND (error_message IS NULL OR error_message <> '用户已拒绝该工具调用')"
        )
    )


def downgrade() -> None:
    """删除工具调用前端可见性字段。"""
    op.drop_column("chat_tool_call", "visible")
