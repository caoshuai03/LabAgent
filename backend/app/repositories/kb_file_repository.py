"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 知识库文件数据访问层
"""
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_file import KbFile
from app.models.kb_upload_task import KbUploadTask
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
        content_hash: str | None = None,
        source_url: str | None = None,
        license: str | None = None,
        status: str = KbFileStatus.READY.value,
        upload_user_id: int | None = None,
    ) -> KbFile:
        """新增文件记录。"""
        now = datetime.now()
        kb_file = KbFile(
            file_name=file_name,
            url=url,
            content_hash=content_hash,
            source_url=source_url,
            license=license,
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

    async def get_by_content_hash(
        self,
        content_hash: str,
        *,
        exclude_file_id: int | None = None,
    ) -> KbFile | None:
        """按文件内容哈希查询，可排除当前更新的文件。"""
        stmt = select(KbFile).where(KbFile.content_hash == content_hash)
        if exclude_file_id is not None:
            stmt = stmt.where(KbFile.id != exclude_file_id)
        return (await self.session.execute(stmt.limit(1))).scalar_one_or_none()

    async def get_by_ids(self, file_ids: list[int]) -> dict[int, KbFile]:
        """批量查询文件记录并按 ID 返回，避免逐条查询。"""
        if not file_ids:
            return {}
        records = (
            await self.session.execute(select(KbFile).where(KbFile.id.in_(file_ids)))
        ).scalars().all()
        return {record.id: record for record in records}

    async def page(
        self,
        file_name: str | None,
        page: int,
        page_size: int,
        sort_by: str = "create_time",
        sort_order: str = "desc",
    ) -> tuple[int, list[KbFile]]:
        """分页查询文件记录，可按文件名模糊过滤。"""
        count_stmt = select(func.count()).select_from(KbFile)
        list_stmt = select(KbFile)
        if file_name:
            cond = KbFile.file_name.like(f"%{file_name}%")
            count_stmt = count_stmt.where(cond)
            list_stmt = list_stmt.where(cond)

        sort_columns = {
            "file_name": func.lower(KbFile.file_name),
            "create_time": KbFile.create_time,
        }
        if sort_by == "total_chunks":
            latest_task_ids = (
                select(
                    KbUploadTask.kb_file_id.label("kb_file_id"),
                    func.max(KbUploadTask.id).label("task_id"),
                )
                .group_by(KbUploadTask.kb_file_id)
                .subquery()
            )
            list_stmt = list_stmt.outerjoin(
                latest_task_ids,
                latest_task_ids.c.kb_file_id == KbFile.id,
            ).outerjoin(
                KbUploadTask,
                KbUploadTask.id == latest_task_ids.c.task_id,
            )
            sort_column = KbUploadTask.total_chunks
        else:
            sort_column = sort_columns.get(sort_by, KbFile.create_time)

        order_expression = (
            sort_column.asc().nulls_last()
            if sort_order == "asc"
            else sort_column.desc().nulls_last()
        )
        list_stmt = list_stmt.order_by(order_expression, KbFile.id.desc())
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
