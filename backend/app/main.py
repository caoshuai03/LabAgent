"""
@author: caoshuai.cs
@date: 2026-07-12
@description: FastAPI 应用入口——注册路由、异常处理，管理 checkpointer 生命周期
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import api_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.graph.checkpointer import close_checkpointer, init_checkpointer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("labagent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/停止钩子：初始化与释放 LangGraph checkpointer。"""
    try:
        await init_checkpointer()
        logger.info("checkpointer 初始化完成")
    except Exception:
        # 数据库不可用时记录但不阻断启动，便于本地排查
        logger.exception("checkpointer 初始化失败，对话接口将不可用")
    yield
    await close_checkpointer()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_version)


@app.get("/health")
async def health() -> dict[str, str]:
    """健康检查。"""
    return {"status": "ok"}
