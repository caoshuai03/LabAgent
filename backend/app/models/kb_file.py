"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 知识库文件表 ORM 模型，对应 ali_oss_file（V2 复用为通用文件表）
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KbFile(Base):
    """知识库文件表，记录文件名、URL 及其向量片段 ID。"""

    __tablename__ = "ali_oss_file"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键id")
    file_name: Mapped[str | None] = mapped_column(String, nullable=True, comment="文件名")
    url: Mapped[str | None] = mapped_column(String, nullable=True, comment="链接地址")
    vector_id: Mapped[str | None] = mapped_column(Text, nullable=True, comment="文件分割出的向量文本ID")
    create_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="创建时间")
    update_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="更新时间")
