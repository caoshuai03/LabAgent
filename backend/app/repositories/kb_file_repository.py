"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 知识库文件数据访问层
"""
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_file import KbFile
from app.models.knowledge_status import KbFileStatus


class KbFileRepository:
    """知识库文件表数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        file_name: str,
        url: str,
        *,
        status: str = KbFileStatus.READY.value,
        upload_user_id: int | None = None,
    ) -> KbFile:
        """新增文件记录。"""
        now = datetime.now()
        kb_file = KbFile(
            file_name=file_name,
            url=url,
            status=status,
            upload_user_id=upload_user_id,
            create_time=now,
            update_time=now,
        )
        self.session.add(kb_file)
        await self.session.flush()
        return kb_file

    async def get_by_id(self, file_id: int) -> KbFile | None:
        """根据 ID 查询文件记录。"""
        return await self.session.get(KbFile, file_id)

    async def page(self, file_name: str | None, page: int, page_size: int) -> tuple[int, list[KbFile]]:
        """分页查询文件记录，可按文件名模糊过滤。"""
        count_stmt = select(func.count()).select_from(KbFile)
        list_stmt = select(KbFile).order_by(KbFile.id.desc())
        if file_name:
            cond = KbFile.file_name.like(f"%{file_name}%")
            count_stmt = count_stmt.where(cond)
            list_stmt = list_stmt.where(cond)
        total = (await self.session.execute(count_stmt)).scalar_one()
        offset = max(page - 1, 0) * page_size
        records = (await self.session.execute(list_stmt.offset(offset).limit(page_size))).scalars().all()
        return total, list(records)

    async def delete_by_ids(self, ids: list[int]) -> int:
        """按 ID 批量删除，返回影响行数。"""
        result = await self.session.execute(delete(KbFile).where(KbFile.id.in_(ids)))
        return result.rowcount or 0

    async def delete_by_id(self, file_id: int) -> None:
        """按 ID 删除单个文件。"""
        await self.session.execute(delete(KbFile).where(KbFile.id == file_id))
