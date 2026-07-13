"""
@author: caoshuai.cs
@date: 2026-07-12
@description: LangGraph 对话图——StateGraph + MessagesState + trim_messages 上下文裁剪，模型调用与流式由框架管理
"""
from langchain_core.messages import SystemMessage, trim_messages
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.config import settings
from app.graph.checkpointer import get_checkpointer
from app.services.model_provider import model_provider

# 系统提示词，约束模型作为实验教学助手回答
_SYSTEM_PROMPT = (
    "你是 LabAgent，一个面向高校实验教学场景的智能学习与教学辅助助手。"
    "请用简洁、准确的中文回答学生关于实验要求、课程知识与代码问题的提问；"
    "无法确定时如实说明，不要编造。"
)

# 编译后的图缓存
_graph: CompiledStateGraph | None = None


def _build_graph() -> CompiledStateGraph:
    """构建并编译对话状态图，绑定 checkpointer 提供短期记忆。"""

    async def chat_node(state: MessagesState, config: RunnableConfig) -> dict:
        """调用模型生成回复；上下文历史由 checkpointer 恢复，超长用 trim_messages 裁剪。"""
        # 用框架能力裁剪历史消息，按消息条数控制窗口，避免手写滑动窗口
        trimmed = trim_messages(
            state["messages"],
            strategy="last",
            token_counter=len,
            max_tokens=settings.memory_max_messages,
            start_on="human",
            include_system=False,
        )
        model_name = (config.get("configurable") or {}).get("model")
        chat_model = model_provider.get_chat_model(model_name)
        messages = [SystemMessage(content=_SYSTEM_PROMPT), *trimmed]
        response = await chat_model.ainvoke(messages)
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("chat", chat_node)
    builder.add_edge(START, "chat")
    builder.add_edge("chat", END)
    return builder.compile(checkpointer=get_checkpointer())


def get_chat_graph() -> CompiledStateGraph:
    """获取已编译的对话图（惰性构建，依赖 checkpointer 已初始化）。"""
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph
