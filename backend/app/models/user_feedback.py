"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 用户反馈表 ORM 模型，对应 tb_user_feedback
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserFeedback(Base):
    """用户反馈表。"""

    __tablename__ = "tb_user_feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="反馈提交人用户ID")
    type: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="类型 0-其它 1-BUG 2-建议 3-投诉")
    title: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="反馈内容")
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="状态 0-新建 1-处理中 2-已解决 3-已关闭")
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, comment="优先级 0-低 1-中 2-高")
    contact_email: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="联系邮箱")
    handler_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="处理人用户ID")
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="处理时间")
    handle_result: Mapped[str | None] = mapped_column(Text, nullable=True, comment="处理结论/回复")
    create_time: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), comment="创建时间"
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), comment="更新时间"
    )
