"""
@author: caoshuai.cs
@date: 2026-07-12
@description: LangGraph 检索增强对话图——retrieve(粗召回)→rerank(精排)→generate(拼装上下文生成)
              检索只针对当前问题不污染 checkpointer 记忆；引用来源经 custom 流事件回传；生成 token 由框架流式捕获
"""
import logging

from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, trim_messages
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.config import settings
from app.graph.checkpointer import get_checkpointer
from app.services import rag_retrieval
from app.services.model_provider import model_provider

logger = logging.getLogger("labagent")

# 系统提示词：约束模型作为实验教学助手，基于参考资料作答；来源由前端结构化展示，正文不再加前缀标签
_SYSTEM_PROMPT = (
    "你是 LabAgent，一个面向高校实验教学场景的智能学习与教学辅助助手。"
    "请优先依据下方参考资料，用简洁、准确的中文回答学生关于实验要求、课程知识与代码问题的提问；"
    "参考资料不足或为空时，可结合通用知识作答，但无法确定时应如实说明，不要编造。\n\n"
    "参考资料：\n{context}"
)

# 编译后的图缓存
_graph: CompiledStateGraph | None = None


class RagState(MessagesState):
    """检索增强对话状态：在消息状态基础上携带检索到的文档。"""

    documents: list[Document]


def _latest_question(state: RagState) -> str:
    """取用户最新一条问题文本，用于检索。"""
    for message in reversed(state["messages"]):
        if message.type == "human":
            return message.content if isinstance(message.content, str) else str(message.content)
    return ""


def _build_graph() -> CompiledStateGraph:
    """构建并编译检索增强对话图，绑定 checkpointer 提供短期记忆。"""

    async def retrieve_node(state: RagState) -> dict:
        """向量粗召回，命中文档写入 state（仅针对当前问题）。

        检索属对话增强而非主链路，embedding/向量库不可用时降级为空参考资料，
        由 generate 节点结合通用知识作答，避免整个对话因检索失败而中断。
        """
        question = _latest_question(state)
        if not question:
            return {"documents": []}
        try:
            documents = await rag_retrieval.retrieve(question)
        except Exception as exc:  # noqa: BLE001 - 检索失败降级，不阻断对话主链路
            # 属预期内可恢复降级（如 embedding 服务不可用），记 WARNING 单行即可，不打堆栈污染日志
            logger.warning("RAG 检索失败，降级为无参考资料继续对话: %s", exc)
            documents = []
        return {"documents": documents}

    async def rerank_node(state: RagState) -> dict:
        """大模型精排取 top_n，并通过 custom 流事件回传结构化引用来源。"""
        question = _latest_question(state)
        documents = await rag_retrieval.rerank(question, state["documents"])
        writer = get_stream_writer()
        writer({"sources": rag_retrieval.build_sources(documents)})
        return {"documents": documents}

    async def generate_node(state: RagState, config: RunnableConfig) -> dict:
        """用 create_stuff_documents_chain 把文档拼进 prompt，配合裁剪后的历史流式生成。"""
        # 框架能力裁剪历史，按消息条数控制窗口，避免手写滑动窗口
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
        prompt = ChatPromptTemplate.from_messages(
            [("system", _SYSTEM_PROMPT), MessagesPlaceholder("messages")]
        )
        # create_stuff_documents_chain 自动把 Document 列表按模板塞进 {context}，无需手写拼接
        chain = create_stuff_documents_chain(chat_model, prompt)
        answer = await chain.ainvoke({"context": state["documents"], "messages": trimmed})
        return {"messages": [AIMessage(content=answer)]}

    builder = StateGraph(RagState)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("rerank", rerank_node)
    builder.add_node("generate", generate_node)
    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "rerank")
    builder.add_edge("rerank", "generate")
    builder.add_edge("generate", END)
    return builder.compile(checkpointer=get_checkpointer())


def get_chat_graph() -> CompiledStateGraph:
    """获取已编译的对话图（惰性构建，依赖 checkpointer 已初始化）。"""
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph
