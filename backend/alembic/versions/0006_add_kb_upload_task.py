"""
@author: caoshuai.cs
@date: 2026-07-25
@description: 增加知识库文件处理状态与异步上传任务表
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_add_kb_upload_task"
down_revision: str | None = "0005_add_tool_call_visible"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """增加文件处理字段并创建异步上传任务表。"""
    op.add_column(
        "ali_oss_file",
        sa.Column("status", sa.String(length=20), server_default="ready", nullable=False),
    )
    op.add_column("ali_oss_file", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("ali_oss_file", sa.Column("upload_user_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_ali_oss_file_upload_user_id",
        "ali_oss_file",
        "tb_user",
        ["upload_user_id"],
        ["id"],
        ondelete="SET NULL",
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


def downgrade() -> None:
    """删除异步上传任务表与文件处理字段。"""
    op.drop_index("ix_kb_upload_task_status", table_name="kb_upload_task")
    op.drop_index("ix_kb_upload_task_user_id", table_name="kb_upload_task")
    op.drop_index("ix_kb_upload_task_kb_file_id", table_name="kb_upload_task")
    op.drop_table("kb_upload_task")
    op.drop_index("ix_ali_oss_file_upload_user_id", table_name="ali_oss_file")
    op.drop_constraint("fk_ali_oss_file_upload_user_id", "ali_oss_file", type_="foreignkey")
    op.drop_column("ali_oss_file", "upload_user_id")
    op.drop_column("ali_oss_file", "error_message")
    op.drop_column("ali_oss_file", "status")
