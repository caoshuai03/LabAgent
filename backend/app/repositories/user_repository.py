"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 用户数据访问层
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """用户表数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        """根据 ID 查询用户。"""
        return await self.session.get(User, user_id)

    async def get_by_username(self, user_name: str) -> User | None:
        """根据用户名查询用户。"""
        result = await self.session.execute(select(User).where(User.user_name == user_name))
        return result.scalar_one_or_none()

    async def add(self, user: User) -> User:
        """新增用户。"""
        self.session.add(user)
        await self.session.flush()
        return user

    async def page(self, name: str | None, page: int, page_size: int) -> tuple[int, list[User]]:
        """分页查询用户，可按姓名模糊过滤。"""
        conditions = []
        if name:
            conditions.append(User.name.like(f"%{name}%"))

        count_stmt = select(func.count()).select_from(User)
        list_stmt = select(User).order_by(User.id.desc())
        for cond in conditions:
            count_stmt = count_stmt.where(cond)
            list_stmt = list_stmt.where(cond)

        total = (await self.session.execute(count_stmt)).scalar_one()
        offset = max(page - 1, 0) * page_size
        records = (await self.session.execute(list_stmt.offset(offset).limit(page_size))).scalars().all()
        return total, list(records)
