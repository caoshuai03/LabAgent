"""
@author: caoshuai.cs
@date: 2026-07-12
@description: FastAPI 应用入口——注册路由、异常处理，管理 checkpointer 与 Skills 生命周期
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.graph.checkpointer import close_checkpointer, init_checkpointer
from app.api.v1 import api_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.services.memory_extraction_service import memory_extraction_scheduler
from app.services.skill_service import skill_catalog

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("labagent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/停止钩子：初始化 Skills 与 LangGraph checkpointer。"""
    try:
        result = await asyncio.to_thread(skill_catalog.refresh)
        logger.info(
            "Skills: loaded=%d, skipped=%d",
            result.loaded_count,
            result.skipped_count,
        )
        for diagnostic in result.diagnostics:
            logger.warning("Skill 已跳过: %s", diagnostic)
    except Exception:
        logger.exception("Skills 目录加载失败，Agent 将不绑定 Skill 工具")
    try:
        await init_checkpointer()
        logger.info("checkpointer init done")
    except Exception:
        # 数据库不可用时记录但不阻断启动，便于本地排查
        logger.exception("checkpointer 初始化失败，对话接口将不可用")
    yield
    await memory_extraction_scheduler.close()
    await close_checkpointer()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_version)


@app.get("/health")
async def health() -> dict[str, str]:
    """健康检查。"""
    return {"status": "ok"}
