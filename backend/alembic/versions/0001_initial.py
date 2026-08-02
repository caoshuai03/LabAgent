# @author: caoshuai.cs
# @date: 2026-08-01
# @description: LabAgent 当前完整数据库基线
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ADMIN_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$GIn7WZoWLsPNPtVYgNsk/A$9GHMgcvokPqf9PFjK31+vj+J/ii/EyA+99bP2eJljYo"


def upgrade() -> None:
    """创建基础表结构并写入初始管理员。"""
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "tb_user",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("user_name", sa.String(), nullable=False),
        sa.Column("password", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("sex", sa.String(), nullable=True),
        sa.Column("id_number", sa.String(), nullable=True),
        sa.Column("status", sa.Integer(), server_default="1", nullable=False),
        sa.Column("role", sa.Integer(), server_default="0", nullable=False),
        sa.Column("create_time", sa.Date(), nullable=True),
        sa.Column("update_time", sa.Date(), nullable=True),
        sa.Column("create_user", sa.BigInteger(), nullable=True),
        sa.Column("update_user", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_unique_constraint("uq_tb_user_user_name", "tb_user", ["user_name"])

    op.create_table(
        "chat_session",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted", sa.SmallInteger(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_chat_session_user_id", "chat_session", ["user_id"])

    op.create_table(
        "chat_message",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("sources", postgresql.JSONB(), nullable=True, comment="RAG引用来源"),
        sa.Column("reasoning", postgresql.JSONB(), nullable=True, comment="主Agent思考过程"),
        sa.Column("images", postgresql.JSONB(), nullable=True, comment="用户消息图片附件"),
        sa.Column("skill_names", postgresql.JSONB(), nullable=True, comment="用户消息主动选择的Skill名称"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_chat_message_user_id", "chat_message", ["user_id"])
    op.create_index("idx_chat_message_session_id", "chat_message", ["session_id"])

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
        sa.Column("visible", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("output_preview", sa.Text(), nullable=True),
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

    op.create_table(
        "ali_oss_file",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("file_name", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("vector_id", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="ready", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("upload_user_id", sa.BigInteger(), nullable=True),
        sa.Column("create_time", sa.DateTime(), nullable=True),
        sa.Column("update_time", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["upload_user_id"],
            ["tb_user.id"],
            name="fk_ali_oss_file_upload_user_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ali_oss_file_upload_user_id", "ali_oss_file", ["upload_user_id"])

    op.create_table(
        "kb_upload_task",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kb_file_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("stage", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("arq_job_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["kb_file_id"], ["ali_oss_file.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["tb_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kb_upload_task_kb_file_id", "kb_upload_task", ["kb_file_id"])
    op.create_index("ix_kb_upload_task_user_id", "kb_upload_task", ["user_id"])
    op.create_index("ix_kb_upload_task_status", "kb_upload_task", ["status"])

    op.create_table(
        "tb_user_feedback",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("priority", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("contact_email", sa.String(length=100), nullable=True),
        sa.Column("handler_user_id", sa.BigInteger(), nullable=True),
        sa.Column("handled_at", sa.DateTime(), nullable=True),
        sa.Column("handle_result", sa.Text(), nullable=True),
        sa.Column("create_time", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("update_time", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_tb_user_feedback_user_id", "tb_user_feedback", ["user_id"])

    op.execute(
        sa.text(
            "INSERT INTO tb_user (name, user_name, password, phone, sex, id_number, status, role, create_time, update_time) "
            "VALUES ('管理员', 'admin', :pwd, '13800138000', '男', '11010519491231002X', 1, 1, CURRENT_DATE, CURRENT_DATE)"
        ).bindparams(pwd=_ADMIN_PASSWORD_HASH)
    )


def downgrade() -> None:
    """回滚基础表结构。"""
    op.drop_index("idx_tb_user_feedback_user_id", table_name="tb_user_feedback")
    op.drop_table("tb_user_feedback")
    op.drop_index("ix_kb_upload_task_status", table_name="kb_upload_task")
    op.drop_index("ix_kb_upload_task_user_id", table_name="kb_upload_task")
    op.drop_index("ix_kb_upload_task_kb_file_id", table_name="kb_upload_task")
    op.drop_table("kb_upload_task")
    op.drop_index("ix_ali_oss_file_upload_user_id", table_name="ali_oss_file")
    op.drop_table("ali_oss_file")
    op.drop_index("idx_chat_tool_call_tool_call_id", table_name="chat_tool_call")
    op.drop_index("idx_chat_tool_call_trace_id", table_name="chat_tool_call")
    op.drop_index("idx_chat_tool_call_message_id", table_name="chat_tool_call")
    op.drop_index("idx_chat_tool_call_user_id", table_name="chat_tool_call")
    op.drop_index("idx_chat_tool_call_session_id", table_name="chat_tool_call")
    op.drop_table("chat_tool_call")
    op.drop_index("idx_chat_message_session_id", table_name="chat_message")
    op.drop_index("idx_chat_message_user_id", table_name="chat_message")
    op.drop_table("chat_message")
    op.drop_index("idx_chat_session_user_id", table_name="chat_session")
    op.drop_table("chat_session")
    op.drop_constraint("uq_tb_user_user_name", "tb_user", type_="unique")
    op.drop_table("tb_user")
