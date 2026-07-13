"""
@author: caoshuai.cs
@date: 2026-07-12
@description: LangGraph 短期记忆 checkpointer——基于 AsyncPostgresSaver，复用现有 PostgreSQL 持久化对话状态
"""
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import settings

# 全局连接池与 saver 单例，随应用生命周期创建/关闭
_pool: AsyncConnectionPool | None = None
_saver: AsyncPostgresSaver | None = None


async def init_checkpointer() -> AsyncPostgresSaver:
    """初始化 checkpointer：建立连接池并创建 checkpoint 表。应在应用启动时调用。"""
    global _pool, _saver
    if _saver is not None:
        return _saver
    # psycopg 连接串需以 postgresql:// 开头；autocommit 供 setup 建表使用
    _pool = AsyncConnectionPool(
        conninfo=settings.sync_database_url,
        max_size=10,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0},
    )
    await _pool.open()
    _saver = AsyncPostgresSaver(conn=_pool)
    await _saver.setup()
    return _saver


def get_checkpointer() -> AsyncPostgresSaver:
    """获取已初始化的 checkpointer。"""
    if _saver is None:
        raise RuntimeError("checkpointer 尚未初始化，请先调用 init_checkpointer()")
    return _saver


async def close_checkpointer() -> None:
    """关闭连接池，应在应用停止时调用。"""
    global _pool, _saver
    if _pool is not None:
        await _pool.close()
    _pool = None
    _saver = None
