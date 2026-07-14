"""
@author: caoshuai.cs
@date: 2026-07-15 02:11
@description: 工具调用记录增加受控输出预览字段
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_add_tool_output_preview"
down_revision: str | None = "0003_add_chat_tool_call"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """增加工具输出预览字段。"""
    op.add_column("chat_tool_call", sa.Column("output_preview", sa.Text(), nullable=True))


def downgrade() -> None:
    """删除工具输出预览字段。"""
    op.drop_column("chat_tool_call", "output_preview")
