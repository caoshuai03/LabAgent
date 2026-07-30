"""
@author: caoshuai.cs
@date: 2026-07-12
@description: LangGraph 短期记忆 checkpointer——基于 AsyncPostgresSaver，复用现有 PostgreSQL 持久化对话状态
"""
import importlib
from typing import Any

from psycopg_pool import AsyncConnectionPool

from app.core.config import settings

# 当前 LangGraph 0.x 依赖的 checkpoint 3.x 尚未显式设置 allowed_objects，
# 在依赖导入期间只跳过该兼容性告警，随后为 checkpoint 显式配置消息对象白名单。
_langchain_load = importlib.import_module("langchain_core.load.load")
_warn_deprecated = _langchain_load.warn_deprecated


def _warn_deprecated_except_checkpoint_policy(*args: Any, **kwargs: Any) -> None:
    message = kwargs.get("message", "")
    if isinstance(message, str) and message.startswith("The default value of `allowed_objects` will change"):
        return
    _warn_deprecated(*args, **kwargs)


_langchain_load.warn_deprecated = _warn_deprecated_except_checkpoint_policy
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.checkpoint.serde import jsonplus as jsonplus_serde
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
finally:
    _langchain_load.warn_deprecated = _warn_deprecated

# 全局连接池与 saver 单例，随应用生命周期创建/关闭
_pool: AsyncConnectionPool | None = None
_saver: AsyncPostgresSaver | None = None


def _create_checkpoint_serializer() -> JsonPlusSerializer:
    """创建仅允许恢复 LangChain 消息对象的 checkpoint 序列化器。"""
    jsonplus_serde.LC_REVIVER = _langchain_load.Reviver(allowed_objects="messages")
    return JsonPlusSerializer()


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
    _saver = AsyncPostgresSaver(conn=_pool, serde=_create_checkpoint_serializer())
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
