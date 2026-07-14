"""
@author: caoshuai.cs
@date: 2026-07-15 00:41
@description: 新增 Agent 工具调用记录表
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_add_chat_tool_call"
down_revision: str | None = "0002_add_chat_message_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建工具调用记录表。"""
    op.create_table(
        "chat_tool_call",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("tool_call_id", sa.String(length=128), nullable=False),
        sa.Column("interrupt_id", sa.String(length=128), nullable=True),
        sa.Column("round", sa.Integer(), server_default="1", nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("tool_source", sa.String(length=50), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("arguments", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "tool_call_id", name="uq_chat_tool_call_session_call"),
    )
    op.create_index("idx_chat_tool_call_session_id", "chat_tool_call", ["session_id"])
    op.create_index("idx_chat_tool_call_user_id", "chat_tool_call", ["user_id"])
    op.create_index("idx_chat_tool_call_message_id", "chat_tool_call", ["message_id"])
    op.create_index("idx_chat_tool_call_trace_id", "chat_tool_call", ["trace_id"])
    op.create_index("idx_chat_tool_call_tool_call_id", "chat_tool_call", ["tool_call_id"])


def downgrade() -> None:
    """删除工具调用记录表。"""
    op.drop_index("idx_chat_tool_call_tool_call_id", table_name="chat_tool_call")
    op.drop_index("idx_chat_tool_call_trace_id", table_name="chat_tool_call")
    op.drop_index("idx_chat_tool_call_message_id", table_name="chat_tool_call")
    op.drop_index("idx_chat_tool_call_user_id", table_name="chat_tool_call")
    op.drop_index("idx_chat_tool_call_session_id", table_name="chat_tool_call")
    op.drop_table("chat_tool_call")
