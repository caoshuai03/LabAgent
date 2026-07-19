# 10 - Agent Loop 与 Agentic RAG 改造

> 本文只记录：**当前情况 → 要做什么 → 怎么做**（优先复用 LangChain / LangGraph 框架能力，不手写）。不含原理讲解。
>
> **本轮已确认改造：**
> 1. 最大迭代次数（工具轮次上限）可配置，默认 **50**。
> 2. 工具「重复调用检测」+ 统一的「失败 / 超时处理」。
> 3. RAG 改为 **检索即工具（Retrieval-as-Tool）**，检索交给模型自主决策，不再固定前置。
> 4. 检索侧默认启用 **MultiQueryRetriever（多角度扩展）** + **混合检索（向量 + BM25，`EnsembleRetriever` RRF 融合）**，再接现有 rerank。

## 1. 当前情况

### 1.1 图结构

当前图见 [chat_graph.py](../backend/app/graph/chat_graph.py#L227-L251)：

```
START → prepare_context → retrieve → rerank → agent
                                                 │ tools_condition
                          ┌──────────────────────┴──────────────┐
                          ▼                                      ▼
                    authorize_tools                          finalize → END
                     │ route_authorized
              ┌──────┴──────┐
              ▼             ▼
            tools ──────► agent
```

- **RAG 固定前置、只跑一次**：`retrieve` → `rerank` 在 `agent` 之前主干上（[chat_graph.py](../backend/app/graph/chat_graph.py#L235-L238)），每次请求无条件跑一次向量召回 + LLM 精排，不在工具循环内。
- **Agent Loop 是 `agent ↔ tools` 自循环**：`tools_condition` 判断最后一条 AIMessage 是否带 `tool_calls`，有则经 `authorize_tools` 进 `ToolNode`，`add_edge("tools","agent")` 回到模型（[chat_graph.py](../backend/app/graph/chat_graph.py#L239-L249)）。LangGraph 原生 ReAct 循环，无手写 while。

### 1.2 循环收敛现状（只针对工具调用）

| 闸门 | 位置 | 机制 |
| --- | --- | --- |
| 最大工具轮次 | [chat_graph.py](../backend/app/graph/chat_graph.py#L128-L132) | `tool_round >= agent_max_tool_rounds`（默认 8）时置 `tools=[]`，模型无工具可调，自然走向 `finalize`（软收敛） |
| recursion_limit | [ai_service.py](../backend/app/services/ai_service.py#L186) | `max(agent_max_tool_rounds*4+10, 30)`，super-step 硬上限，超限抛 `GraphRecursionError` |
| 全局超时 | [ai_service.py](../backend/app/services/ai_service.py#L200) | `asyncio.timeout(agent_timeout_seconds)`（默认 180s）包住整个 `astream` |

`tool_round` 仅在「本轮带 tool_calls」时 +1（[chat_graph.py](../backend/app/graph/chat_graph.py#L140-L145)）。

### 1.3 工具失败 / 超时现状

- **失败已转可控 ToolMessage**：`write_file`（[file_tools.py](../backend/app/tools/file_tools.py#L125-L146)）、`execute_shell`（[shell_tool.py](../backend/app/tools/shell_tool.py#L116-L137)）均 `try/except` 转 `result_envelope(success=False, error=...)` 回传模型，并发 `tool_failed` 事件；`ToolNode` 配了 `handle_tool_errors`（[chat_graph.py](../backend/app/graph/chat_graph.py#L233)）兜底。
- **超时不统一**：Shell 有 `shell_timeout_seconds`（20s）（[shell_tool.py](../backend/app/tools/shell_tool.py#L35-L38)）；文件工具**无单工具超时**，`tool_timeout_seconds`（60）目前未生效，仅靠全局 180s 兜底。
- **无重复调用检测**：同工具 + 同参数反复调用不被拦截。

## 2. 改造设计

### 2.1 最大迭代次数可配置，默认 50

**要做什么**：工具轮次上限默认从 8 提到 50。

**怎么做**：

- 沿用现有 `agent_max_tool_rounds`（[config.py](../backend/app/core/config.py#L88)），默认值改 `50`，本就是环境变量可配。
- `recursion_limit` 公式不变（[ai_service.py](../backend/app/services/ai_service.py#L186)），50 轮算得 210 步；需确认足够。
- 收敛策略不变，仍是「到限不绑工具」软收敛（[chat_graph.py](../backend/app/graph/chat_graph.py#L128-L132)）。
- 评估 `agent_timeout_seconds`（180s）是否随轮次上调。

### 2.2 工具重复调用 / 失败 / 超时

**（1）重复调用检测（新增）**

- **判定**：同一 `tool_name` + 参数稳定序列化后哈希，在同一次 agent run 内计数。
- **处理**：命中重复返回 `success=False` 的 ToolMessage 提示模型换路（软）；同签名超过 `agent_duplicate_tool_call_limit`（默认 3）才终止本轮工具绑定、走软收敛。
- **怎么做**：在 `authorize_tools_node`（[chat_graph.py](../backend/app/graph/chat_graph.py#L147-L217)）遍历 `tool_calls` 时比对签名；签名记录存入 `AgentState` 新增字段（如 `tool_call_signatures: dict[str,int]`）。

**（2）失败处理（保留 + 加固）**

- 现状转 `success=False` ToolMessage 的方向正确，**保留不改**。
- 加固：`result_envelope` 增加可选 `error_type`（参数错误 / 权限拒绝 / 超时 / 执行异常），便于模型区分重试还是换路（不破坏既有契约）。

**（3）超时统一（新增）**

- **怎么做**：工具适配层（`_invoke_file_tool` / `execute_shell`）用 `asyncio.timeout(settings.tool_timeout_seconds)` 包住执行，超时转 `success=False` + `error_type="timeout"` 的 ToolMessage，发 `tool_timeout` 事件。让 `tool_timeout_seconds`（60）对所有本地工具生效，Shell 仍保留更短的 `shell_timeout_seconds`。
- 超时分层：单工具超时 → 全局超时兜底。

### 2.3 RAG 改为检索即工具（Retrieval-as-Tool）

**要做什么**：把检索从固定前置节点改为模型自主调用的工具，是否检索、检索几次由模型决定。

**怎么做（结合框架能力）**：

- 图移除主干 `retrieve` → `rerank` 节点，`prepare_context` 后直接进 `agent`。
- 新增 `@tool search_knowledge_base(query: str)`，内部复用现有 `rag_retrieval.retrieve` + `rerank`（[rag_retrieval.py](../backend/app/services/rag_retrieval.py#L39-L73)），返回命中片段 + 来源。
- 注册进 `tool_registry`，与 `write_file` / `execute_shell` 同白名单，天然复用 `ToolNode` 与 agent↔tools 循环。
- `ToolMetadata` 标 `risk_level="low"`、`read_only=True`，`authorize_tools_node` 直接放行。
- **sources**：改在工具内部经 `safe_stream_writer` 下发 `sources` 事件（现由 `rerank_node` 下发，[chat_graph.py](../backend/app/graph/chat_graph.py#L112)），SSE 事件类型/字段契约不变，但触发时机变为「模型每次调检索工具时」，一次对话可能下发多次。**需联动前端**：当前前端 `sources` 为覆盖式（[chat.js](../frontend/src/stores/chat.js#L577-L582) 的 `setLastMessageSources` 直接整体赋值），多次下发会只保留最后一次、丢失前几次检索来源，需改为按 `file_name` / 内容去重的追加合并（见 §2.6）。
- **上下文**：检索结果作为 `ToolMessage` 进消息序列，移除 `_SYSTEM_PROMPT` 的 `{context}` 占位符。
- **降级**：沿用现有「Ollama 不可达 → 快速失败降级为无资料」，返回 `success=True` + 空命中说明。
- **提示词**：system prompt 新增指引——涉及课程知识 / 实验要求先调 `search_knowledge_base`；闲聊或纯文件/命令操作无需检索。
- **检索次数**：无需单独上限，受 §2.1 工具轮次约束；重复检索由 §2.2 重复调用检测覆盖。

### 2.4 检索链路：MultiQuery + 混合检索（向量 + BM25，RRF）

**要做什么**：`search_knowledge_base` 内部把「单次向量检索」升级为「多角度扩展 + 向量/BM25 混合召回 + RRF 融合 + rerank」。均默认启用、无开关。

**链路（全部封装在 `search_knowledge_base` 内部，对图结构零影响）**：

```
query
  ├─ MultiQueryRetriever 多角度扩展成多条 query
  │
  ├─ 向量检索 ─┐
  │            ├─ EnsembleRetriever（RRF 融合去重）→ LLMListwiseRerank 精排 top_n → 命中片段 + sources
  └─ BM25 ─────┘
```

**怎么做（全用 LangChain 现成组件，不手写融合）**：

- **MultiQuery**：`MultiQueryRetriever.from_llm(retriever=..., llm=...)` 包住底层检索器。
- **BM25 一路**：`BM25Retriever.from_documents(...)` 从现有 `rag_store` 切片文档建索引，与向量库同源（同一批 chunk）。BM25 为内存实现，无需部署 ES。
- **融合**：`EnsembleRetriever(retrievers=[向量, BM25], weights=[...])`，内置 RRF；权重后续按效果调。
- **精排**：融合结果仍走现有 `rerank`（[rag_retrieval.py](../backend/app/services/rag_retrieval.py#L62-L73)）。

### 2.5 配置汇总

写入 [config.py](../backend/app/core/config.py#L76-L90)：

| 配置项 | 变化 | 默认值 |
| --- | --- | --- |
| `agent_max_tool_rounds` | 调整默认值（工具调用总轮次上限，含检索） | 8 → **50** |
| `agent_duplicate_tool_call_limit` | 新增（同签名重复达到即终止） | 3 |
| `tool_timeout_seconds` | 使其真正作用于本地文件工具 | 60（不变） |
| `agent_timeout_seconds` | 评估是否随轮次上调 | 180（待定） |

### 2.6 前端改动

前端排查结论：**只有 sources 一处必须改**，其余无需改动。

**（1）sources 改覆盖式为去重合并（必须改）**

- **现状**：`sources` 为覆盖式——[ChatInput.vue](../frontend/src/components/ChatInput.vue#L445-L448) 每次收到 `sources` 事件调 [chat.js](../frontend/src/stores/chat.js#L577-L582) 的 `setLastMessageSources`，内部 `lastMessage.sources = sources` 整体赋值。
- **问题**：检索即工具后一次对话多次下发 `sources`，前端只保留最后一次、丢失前几次检索来源。
- **怎么做**：`setLastMessageSources` 改为按 `file_name` / 内容去重的追加合并，保留本轮对话所有检索来源。

**（2）无需改动（已确认）**

- `tool_timeout` 事件：[ToolActivityPanel.vue](../frontend/src/components/ToolActivityPanel.vue#L160-L172) 的 `statusFromStage` 已映射 `tool_timeout`，有「执行超时」文案与样式；前提是后端仍以 `status` 事件 + `stage:"tool_timeout"` 下发（即 §2.2 设计）。未知 stage 有兜底不崩溃。
- 工具轮次 8→50：前端 [ToolActivityPanel.vue](../frontend/src/components/ToolActivityPanel.vue#L199-L264) 全量遍历渲染，无硬编码上限，不受影响。
- `error_type`（§2.2）：放在工具结果 JSON 里给模型看，不走 `error` 事件通道，前端无需识别。

## 3. 落地待办

- [ ] §2.1：`agent_max_tool_rounds` 默认改 50；核对 `recursion_limit` 在 50 轮下步数是否充足；评估 `agent_timeout_seconds`。
- [ ] §2.2：`AgentState` 加签名记录；`authorize_tools_node` 加重复调用检测（软返回 + 超阈值升级）；新增 `agent_duplicate_tool_call_limit`。
- [ ] §2.2：`result_envelope` 加 `error_type`；文件工具用 `asyncio.timeout(tool_timeout_seconds)` 统一超时，发 `tool_timeout` 事件。
- [ ] §2.3：新增 `search_knowledge_base` 工具（low / read_only），注册进 registry；sources 改从工具内部下发；图移除 `retrieve`/`rerank` 节点，`prepare_context` → `agent`；移除 `_SYSTEM_PROMPT` 的 `{context}`，加检索使用指引。
- [ ] §2.4：工具内接入 `MultiQueryRetriever` + `BM25Retriever` + `EnsembleRetriever`（RRF）+ 现有 rerank，默认启用。
- [ ] §2.6：前端 `setLastMessageSources`（[chat.js](../frontend/src/stores/chat.js#L577-L582)）改为按 `file_name`/内容去重的追加合并，避免多次检索只保留最后一次来源。
- [ ] 补充单测与图集成测试：重复调用检测、工具超时、检索命中/空命中/降级、sources 事件时机。
- [ ] 与 [08-上下文管理调研](08-上下文管理调研.md) 联动：检索结果以 ToolMessage 独立消息进入上下文。
