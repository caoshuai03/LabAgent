"""
@author: caoshuai.cs
@date: 2026-07-12
@description: AI 对话模块路由——SSE 流式对话、历史、会话列表与删除；用户 ID 取自 JWT
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.deps import CurrentUser, DbSession
from app.schemas.chat import (
    ChatMessageVO,
    ChatRequest,
    DeleteSessionRequest,
    HistoryRequest,
)
from app.schemas.chat import ChatSessionVO
from app.schemas.tool import AgentCancelRequest, AgentResumeRequest, ToolDefinitionVO
from app.core.response import BaseResponse, success
from app.services.ai_service import AiService
from app.services.message_service import MessageService
from app.services.session_service import SessionService
from app.tools.registry import tool_registry

router = APIRouter(prefix="/ai", tags=["ai"])

_ai_service = AiService()


def _stream_response(
    message: str,
    session_id: str | None,
    user_id: int,
    user_role: int,
    model: str | None,
) -> StreamingResponse:
    """构建 SSE 流式响应。"""
    generator = _ai_service.stream_chat(message, session_id, user_id, user_role, model)
    return StreamingResponse(generator, media_type="text/event-stream")


@router.post("/react-agent")
async def agent_chat(req: ChatRequest, current_user: CurrentUser) -> StreamingResponse:
    """Agent 对话接口（RAG + ToolNode 工具循环）。"""
    return _stream_response(
        req.message or "你好",
        req.session_id,
        current_user.id,
        current_user.role or 0,
        req.model,
    )


@router.post("/react-agent/resume")
async def resume_agent(req: AgentResumeRequest, current_user: CurrentUser) -> StreamingResponse:
    """批准或拒绝高风险工具后恢复 Agent 图。"""
    generator = _ai_service.stream_resume(
        req.session_id,
        req.interrupt_id,
        req.approved,
        current_user.id,
    )
    return StreamingResponse(generator, media_type="text/event-stream")


@router.post("/react-agent/cancel")
async def cancel_agent(req: AgentCancelRequest, current_user: CurrentUser) -> BaseResponse[bool]:
    """取消当前用户指定会话中的 Agent 运行。"""
    return success(await _ai_service.cancel_run(req.session_id, req.trace_id, current_user.id))


@router.get("/tools")
async def list_tools(current_user: CurrentUser) -> BaseResponse[list[ToolDefinitionVO]]:
    """查询当前用户可用的 Agent 工具。"""
    return success(tool_registry.definitions(current_user.role or 0))


@router.post("/rag/history")
async def get_history(req: HistoryRequest, current_user: CurrentUser, db: DbSession) -> BaseResponse[list[ChatMessageVO]]:
    """获取会话历史消息（校验归属）。"""
    messages = await MessageService(db).get_messages_by_session(req.session_id, current_user.id)
    return success(messages)


@router.post("/rag/sessions")
async def list_sessions(current_user: CurrentUser, db: DbSession) -> BaseResponse[list[ChatSessionVO]]:
    """获取当前用户的会话列表。"""
    sessions = await SessionService(db).list_sessions_by_user(current_user.id)
    return success(sessions)


@router.post("/rag/sessions/delete")
async def delete_sessions(req: DeleteSessionRequest, current_user: CurrentUser, db: DbSession) -> BaseResponse[bool]:
    """删除会话，支持单个或批量（逻辑删除 + 归属校验）。"""
    ids = req.session_ids if req.session_ids else ([req.session_id] if req.session_id else [])
    result = await SessionService(db).delete_sessions(ids, current_user.id)
    return success(result)
