"""
@author: caoshuai.cs
@date: 2026-07-12
@description: AI 对话模块路由——SSE 流式对话、历史、会话列表与删除；用户 ID 取自 JWT
"""
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core.deps import CurrentUser, DbSession
from app.core.errors import BusinessException, ErrorCode
from app.schemas.chat import (
    ChatMessageVO,
    ChatRequest,
    ConversationTitleVO,
    DeleteSessionRequest,
    HistoryRequest,
)
from app.schemas.chat import ChatSessionVO
from app.schemas.memory import ConversationCompressionVO
from app.schemas.tool import AgentCancelRequest, AgentResumeRequest, ToolDefinitionVO, WorkspaceFileVO
from app.core.response import BaseResponse, success
from app.services.ai_service import AiService
from app.services.message_service import MessageService
from app.services.session_service import SessionService
from app.tools.file_tools import preview_language_for
from app.tools.registry import tool_registry
from app.tools.result import redact_value, truncate_text
from app.tools.workspace import WorkspaceError, workspace_manager
from app.core.config import settings

router = APIRouter(prefix="/ai", tags=["ai"])

_ai_service = AiService()


def _stream_response(
    message: str,
    session_id: str | None,
    user_id: int,
    model: str | None,
) -> StreamingResponse:
    """构建 SSE 流式响应。"""
    generator = _ai_service.stream_chat(message, session_id, user_id, model)
    return StreamingResponse(generator, media_type="text/event-stream")


@router.post("/react-agent")
async def agent_chat(req: ChatRequest, current_user: CurrentUser) -> StreamingResponse:
    """Agent 对话接口（RAG + ToolNode 工具循环）。"""
    return _stream_response(
        req.message or "你好",
        req.session_id,
        current_user.id,
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


@router.post("/sessions/{session_id}/compress")
async def compress_session(
    session_id: str,
    current_user: CurrentUser,
) -> BaseResponse[ConversationCompressionVO]:
    """主动压缩当前用户会话的 LangGraph 工作上下文。"""
    return success(await _ai_service.compress_session(session_id, current_user.id))


@router.get("/tools")
async def list_tools(current_user: CurrentUser) -> BaseResponse[list[ToolDefinitionVO]]:
    """查询可用的 Agent 工具。"""
    return success(tool_registry.definitions())


@router.get("/workspace/file", response_model=None)
async def get_workspace_file(
    current_user: CurrentUser,
    db: DbSession,
    session_id: Annotated[str, Query()],
    path: Annotated[str, Query()],
    disposition: Annotated[str, Query()] = "inline",
) -> StreamingResponse | BaseResponse[WorkspaceFileVO]:
    """读取当前用户工作区内的文件：inline 返回整文件预览内容，attachment 返回下载流。"""
    # 强校验会话归属，防止越权读取他人工作区
    await SessionService(db).get_owned_session(session_id, current_user.id)
    try:
        workspace = workspace_manager.ensure_workspace(current_user.id, session_id)
        target = workspace_manager.validate_relative_path(workspace, path, allow_missing=False)
    except WorkspaceError as exc:
        raise BusinessException(ErrorCode.PARAMS_ERROR, str(exc)) from exc
    if not target.is_file():
        raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "文件不存在")

    if disposition == "attachment":
        import io

        headers = {"Content-Disposition": f'attachment; filename="{target.name}"'}
        return StreamingResponse(
            io.BytesIO(target.read_bytes()),
            media_type="application/octet-stream",
            headers=headers,
        )

    language = preview_language_for(path)
    try:
        workspace_manager.validate_file_size(target, settings.tool_max_output_chars)
        raw = target.read_text(encoding="utf-8")
    except WorkspaceError as exc:
        raise BusinessException(ErrorCode.PARAMS_ERROR, str(exc)) from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise BusinessException(ErrorCode.PARAMS_ERROR, "该文件不支持文本预览，请下载查看") from exc
    content = truncate_text(str(redact_value(raw)))
    return success(
        WorkspaceFileVO(
            path=path,
            language=language,
            content=content,
            truncated=content != raw,
        )
    )


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


@router.get("/rag/sessions/{session_id}/title")
async def get_session_title(
    session_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> BaseResponse[ConversationTitleVO]:
    """查询当前用户所属会话的标题。"""
    return success(await SessionService(db).get_title(session_id, current_user.id))


@router.post("/rag/sessions/delete")
async def delete_sessions(req: DeleteSessionRequest, current_user: CurrentUser, db: DbSession) -> BaseResponse[bool]:
    """删除会话，支持单个或批量（逻辑删除 + 归属校验）。"""
    ids = req.session_ids if req.session_ids else ([req.session_id] if req.session_id else [])
    result = await SessionService(db).delete_sessions(ids, current_user.id)
    return success(result)
