"""
@author: caoshuai.cs
@date: 2026-07-12
@description: SQLAlchemy 声明式基类
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """ORM 模型基类。"""
