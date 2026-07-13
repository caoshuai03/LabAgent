"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-12
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 初始管理员密码 admin 的 Argon2 哈希
_ADMIN_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$Xu4Ex/MhQD/lVApmL/lMCQ$IueV/HijB8baCKPQobjQpgdUeaI9Q4rSOae7cebahFY"


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
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_chat_message_user_id", "chat_message", ["user_id"])
    op.create_index("idx_chat_message_session_id", "chat_message", ["session_id"])

    op.create_table(
        "ali_oss_file",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("file_name", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("vector_id", sa.Text(), nullable=True),
        sa.Column("create_time", sa.DateTime(), nullable=True),
        sa.Column("update_time", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

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

    # 写入初始管理员（密码 admin，Argon2 哈希；替代参考项目 MD5）
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
    op.drop_table("ali_oss_file")
    op.drop_index("idx_chat_message_session_id", table_name="chat_message")
    op.drop_index("idx_chat_message_user_id", table_name="chat_message")
    op.drop_table("chat_message")
    op.drop_index("idx_chat_session_user_id", table_name="chat_session")
    op.drop_table("chat_session")
    op.drop_constraint("uq_tb_user_user_name", "tb_user", type_="unique")
    op.drop_table("tb_user")
