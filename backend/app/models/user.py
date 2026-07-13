"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 用户表 ORM 模型，对应 tb_user
"""
from datetime import date

from sqlalchemy import BigInteger, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    """用户信息表。"""

    __tablename__ = "tb_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键")
    name: Mapped[str] = mapped_column(String, nullable=False, comment="姓名")
    user_name: Mapped[str] = mapped_column(String, nullable=False, comment="用户名")
    password: Mapped[str] = mapped_column(String, nullable=False, comment="密码（Argon2 哈希）")
    phone: Mapped[str | None] = mapped_column(String, nullable=True, comment="手机号")
    sex: Mapped[str | None] = mapped_column(String, nullable=True, comment="性别")
    id_number: Mapped[str | None] = mapped_column(String, nullable=True, comment="身份证号")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="状态 0：禁用 1：启用")
    role: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="角色 0-普通用户 1-管理员")
    create_time: Mapped[date | None] = mapped_column(Date, nullable=True, comment="创建时间")
    update_time: Mapped[date | None] = mapped_column(Date, nullable=True, comment="更新时间")
    create_user: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="创建人")
    update_user: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="修改人")
