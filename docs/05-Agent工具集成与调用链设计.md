<!--
 @author: caoshuai.cs
 @date: 2026-07-15 00:13
 @description: 第四阶段产出——LabAgent Agent 工具集成与完整调用链设计（LangChain 文件/Shell 工具、LangGraph ToolNode 循环、工作区隔离、人工审批、SSE 事件、持久化与前端适配）
-->

# 第四阶段：Agent 工具集成与完整调用链设计

> 本文档是 LabAgent 第四阶段设计与实现说明，基于第三阶段 [RAG 闭环设计](./03-RAG闭环设计.md) 及原有 `retrieve → rerank → generate` LangGraph 图。
> 2026-07-15 已完成第一版落地：接入 LangChain 文件管理与 Shell 工具，使用 LangGraph 框架能力完成模型选择工具、工具执行、结果回传、多轮调用和人工审批，并打通后端 Graph、SSE、数据库与前端展示的完整链路。
> Shell 工具保持默认关闭；仅在显式配置、角色授权和独立 Tool Runner 沙箱生效时允许执行。普通命令直接执行，文件删除和 Shell 删除类命令需要消息内审批。

---

## 一、现状与本阶段目标

### 1.1 第四阶段实施前基线（本阶段直接复用）

- 唯一对话入口 `POST /api/v1/ai/react-agent`，以 `StreamingResponse` 返回 SSE。
- JWT 身份解析、会话归属校验、用户/助手消息持久化。
- `AsyncPostgresSaver + MessagesState`短期记忆，`thread_id` 按「用户 + 会话」隔离。
- `retrieve → rerank → generate` RAG 图、结构化引用来源与 Token 流式输出。
- `ModelProvider` 统一路由 Ollama、OpenAI 兼容模型和 Azure OpenAI 网关。
- 前端已有 SSE 解析、按会话隔离的流式状态、`toolEvents` 内存结构和工具调用展示面板雏形。



### 1.3 本阶段实现

- 接入 `FileManagementToolkit` 的目录列表、文件搜索、读取、写入、复制、移动和删除工具。
- 接入 `ShellTool`，通过受控执行器在会话工作区执行命令。
- 建立 Tool Registry、Tool Policy、Workspace Manager 和工具执行记录。
- 将当前 RAG 图升级为「RAG 上下文 + Agent + ToolNode + 审批」图。
- 使用 `model.bind_tools`、`tools_condition`、`ToolNode`、`interrupt`和 `Command(resume=...)` 完成框架原生工具链路。
- 定义工具调用 SSE 协议，适配前端工具卡片、历史恢复和审批弹窗。
- 增加工具调用持久化、超时、取消、输出截断、路径隔离与 Prompt Injection 防护。


## 二、核心设计决策

### 2.1 使用 StateGraph + ToolNode，不手写工具循环

本阶段不直接使用完全封装的 `create_react_agent`，而是使用 `StateGraph + ToolNode`，原因如下：

- 当前已有 RAG 检索、rerank、引用来源和自定义 SSE 节点，需要继续保留。
- 文件删除和 Shell 删除类命令需在工具执行前插入权限与人工审批节点。
- 需要对 Agent 轮次、工具状态、超时和持久化做显式控制。
- `ToolNode` 仍负责工具参数校验、执行、并行调用与 `ToolMessage` 封装，项目不重复实现这些能力。

### 2.2 RAG 保留为 Agent 前置节点

第一版继续每轮执行当前 `retrieve → rerank`，然后进入 Agent 节点：

- 保留第三阶段已验证的知识库召回率和引用来源。
- 避免模型忘记调用知识库工具导致普通问答能力倒退。
- 本阶段只把文件和 Shell 等动作型能力工具化；将 RAG 改成按需 Tool 属于后续优化。

### 2.3 复用 LangChain 工具，只增加必要适配层

- 文件执行本体使用 `FileManagementToolkit`，不自己重写 `read_text`、`write_text`、`copy`、`move`、`delete` 等文件操作。
- Shell 工具使用 `ShellTool`，但替换其默认 `BashProcess`，由受控的 `SandboxShellProcess.run(commands)` 实际执行。
- 适配层只承担框架工具未覆盖的业务上下文注入、权限、超时、事件、脱敏和审计。

### 2.4 工具可见性与执行权限双重校验

- Agent 节点只向模型 `bind_tools`当前用户可用的工具。
- ToolNode 执行前，Tool Policy 再根据 JWT 用户、会话归属、配置开关和工作区校验一次。
- 即使恶意输入伪造了 `AIMessage.tool_calls`，未授权工具也不能执行。

---

## 三、技术选型与依赖

### 3.1 当前实际版本

| 依赖 | `uv.lock` 版本 | 本阶段用途 |
| :--- | :--- | :--- |
| `langgraph` | 0.6.11 | StateGraph、Command、interrupt、astream |
| `langgraph-prebuilt` | 0.6.5 | ToolNode、tools_condition、InjectedState |
| `langchain` | 0.3.30 | Agent/LangChain 组合能力 |
| `langchain-core` | 0.3.86 | BaseTool、ToolMessage、ChatPromptTemplate、Runnable |
| `langchain-community` | 0.3.31 | FileManagementToolkit、ShellTool |
| `langchain-ollama` | 0.3.10 | Ollama Tool Calling |
| `langchain-openai` | 0.3.35 | OpenAI/Azure Tool Calling |

### 3.2 依赖结论

- `FileManagementToolkit` 和 `ShellTool` 均已由当前 `langchain-community` 提供。
- 直接构建 `ShellTool()` 时，其默认 `BashProcess` 会从 `langchain-experimental` 加载，当前项目未安装该依赖。
- 本设计始终显式传入 `SandboxShellProcess`，不使用默认工厂，因此第一版**不需要增加 `langchain-experimental`**。
- 如后续改回框架默认 `BashProcess`，再引入与 LangChain 0.3.x 兼容的 `langchain-experimental` 并锁定版本。

### 3.3 模型 Tool Calling 兼容性

- `ChatOpenAI`、`AzureChatOpenAI` 和 `ChatOllama` 都通过统一 `BaseChatModel.bind_tools()` 接入。
- 不能仅根据 Provider 判定工具能力，具体模型必须能正确生成 `tool_calls` 及结构化参数。
- `ModelProvider` 需维护「支持工具」的模型配置；不支持时保留 RAG 问答，但不向模型暴露工具。
- 并行 Tool Calls 是可选能力。高风险工具不依赖 Provider 的并行开关，由授权节点统一处理调用批次。

---

## 四、工具清单与参数设计

### 4.1 FileManagementToolkit

| 工具名 | 框架参数 | 类型 | 默认开启 | 默认审批 |
| :--- | :--- | :--- | :--- | :--- |
| `list_directory` | `dir_path` | 只读 | 是 | 否 |
| `file_search` | `pattern`, `dir_path` | 只读 | 是 | 否 |
| `read_file` | `file_path` | 只读 | 是 | 否 |
| `write_file` | `file_path`, `text`, `append` | 写入 | 是 | 可配 |
| `copy_file` | `source_path`, `destination_path` | 写入 | 是 | 可配 |
| `move_file` | `source_path`, `destination_path` | 破坏性写入 | 是 | 可配 |
| `file_delete` | `file_path` | 破坏性写入 | 是 | 是 |

集成方式：

```python
FileManagementToolkit(
    root_dir=workspace_path,
    selected_tools=[
        "list_directory",
        "file_search",
        "read_file",
        "write_file",
        "copy_file",
        "move_file",
        "file_delete",
    ],
).get_tools()
```

上述代码是设计示意，实际落地时不能把不同用户的 `workspace_path` 固化在全局单例中。适配层需根据注入的运行上下文获取当前工作区，再委托给框架工具。

### 4.2 ShellTool

项目对模型暴露的工具名统一为 `execute_shell`：

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `commands` | `str \| list[str]` | ShellTool 原生参数；字符串或命令列表 |

构建方式：

```python
ShellTool(
    name="execute_shell",
    description="Execute commands inside the current isolated session workspace.",
    process=SandboxShellProcess(...),
    ask_human_input=False,
)
```

- `ask_human_input` 不能设为 `True`，因为 FastAPI 服务端不能使用终端 `input()` 与 Web 用户交互。
- Web 审批使用 LangGraph `interrupt` 和前端消息内联确认卡片实现。
- `ShellTool` 自带的 `ShellInput` 只校验 `commands` 类型，源码中明确没有真正的安全校验；命令策略必须由 Tool Policy 实现。

### 4.3 工具风险分级

| 风险等级 | 工具 | 策略 |
| :--- | :--- | :--- |
| `low` | `list_directory`, `file_search`, `read_file` | 工作区和输出校验通过后直接执行 |
| `medium` | `write_file`, `copy_file`, `move_file`, 普通 `execute_shell` | 工作区内或沙箱内直接执行 |
| `high` | `file_delete`, Shell 删除类命令 | 在助手消息内请求批准后执行 |

---

## 五、Tool Registry 与运行时上下文

### 5.1 Tool Registry 职责

Tool Registry 只做工具管理，不执行 Agent 循环：

- 注册框架工具和项目适配工具。
- 按工具名去重，拒绝重复名称静默覆盖。
- 保存工具元数据：名称、来源、风险等级、只读性、是否启用、是否需审批。
- 根据 Settings、当前用户角色和模型能力返回可绑定工具集合。
- 为 ToolNode 提供已注册的可执行工具集合。

### 5.2 AgentState 扩展

```python
class AgentState(MessagesState):
    documents: list[Document]
    sources: list[dict[str, str | float | None]]
    user_id: int
    session_id: str
    workspace_path: str
    tool_round: int
    approved_tool_call_ids: list[str]
```

约束：

- `user_id` 从 JWT 获取，`session_id` 从已校验的业务会话获取。
- `workspace_path` 由 Workspace Manager 计算，不接受请求体或模型输出。
- 这些字段通过 `InjectedState` 注入适配工具，不出现在模型可见的工具 Schema 中。
- 模型名等单次运行配置继续放在 `RunnableConfig.configurable`，不写入长期对话状态。

### 5.3 工具适配层职责

框架工具外围的适配层统一处理：

1. 从注入状态中获取当前用户、会话和工作区。
2. 调用 Tool Policy 做权限、路径、命令和参数校验。
3. 写入工具开始记录并通过 `get_stream_writer()` 发送进度。
4. 委托给 `FileManagementToolkit` 或 `ShellTool`。
5. 设置超时，捕获异常并转为可控的 Tool 结果。
6. 对结果脱敏、截断和摘要，更新工具记录。

---

## 六、工作区与文件安全设计

### 6.1 工作区目录

```text
{tool_workspace_root}/
└── {user_id}/
    └── {session_id}/
        ├── input/
        ├── output/
        └── tmp/
```

- 用户首次在会话中使用工具时惰性创建目录。
- 工具的 `root_dir` 为会话目录，模型只使用相对路径。
- 会话逻辑删除后，工作区按配置异步清理；不在删除 API 内做长时间阻塞式遍历。
- 本阶段不提供聊天附件上传，工作区文件来自部署预置、开发测试或 Agent 自身写入。

### 6.2 路径校验

`FileManagementToolkit` 已使用 `Path.resolve()` 检查路径是否位于 `root_dir` 内，但当前版本源码明确提示仍需额外处理软链接风险。项目在适配层再执行以下校验：

- 拒绝绝对路径和任何解析后越出工作区的路径。
- 对路径每一层做 `lstat`，拒绝经过指向工作区外部的软链接。
- 写入前同时校验父目录与最终目标，防止校验后替换路径的 TOCTOU 风险。
- 限制单文件读取和写入大小，超限时返回可理解错误，不把整个文件放入 Prompt。
- 必要时限制允许的文件类型；二进制文件不按文本直接读入模型。

### 6.3 文件工具阻塞 I/O

`FileManagementToolkit` 为同步文件工具。在异步 Graph 中必须通过 ToolNode/Runnable 的异步执行器运行，不在 FastAPI 事件循环中直接调用同步 `_run()`。

---

## 七、Shell 受控执行设计

### 7.1 为什么不使用默认 BashProcess

`ShellTool` 的当前实现会直接调用 `process.run(commands)`，默认实现无工作区、权限、资源和网络隔离，且工具源码会显式警告「默认没有安全防护」。

因此：

- 不在后端宿主环境直接执行默认 ShellTool。
- 不把后端 `.env`、数据库密码、MinIO 密钥和模型 API Key 注入 Shell 环境。
- 不挂载 Docker Socket、宿主用户目录和项目外部目录。

### 7.2 SandboxShellProcess

`SandboxShellProcess` 实现 ShellTool 需要的 `run(commands)` 协议：

1. 校验 Shell 开关、用户角色、工作区和审批结果。
2. 将命令、会话工作区标识和超时发送给独立 Tool Runner。
3. Tool Runner 使用非 root 用户启动子进程，工作目录限定为会话目录。
4. 限制 CPU、内存、进程数、执行时间和输出大小。
5. 终止时先发送正常终止信号，超过宽限期再强制结束整个进程组。
6. 只返回截断后的 stdout/stderr、退出码和耗时，不返回容器内部环境信息。

### 7.3 Tool Runner 部署

推荐在 Docker Compose 中增加内部 `tool-runner` 服务：

```text
backend ──内部 HTTP──> tool-runner
   │                         │
   └── read/write 共享工作区 ─┘
```

- `tool-runner` 不暴露宿主端口，只在 Compose 内部网络可见。
- backend 和 runner 共享 `tool_workspace_root` 数据卷，runner 仅挂载该目录。
- runner 使用独立内部 Token 验证请求，Token 从环境变量读取。
- runner 默认无外网权限；如需安装依赖，应使用预构建镜像或明确的网络白名单。
- 本地开发也优先启动 runner，不因为是开发环境就改为宿主直接 Shell。

### 7.4 命令策略

- 限制单次 `commands` 数量和总字符数。
- 默认拒绝提权、关机、挂载、设备读写、远程登录、反弹 Shell 和访问宿主资源的命令模式。
- 即使命令未命中禁止规则，仍必须在沙箱内执行；命令黑名单不替代沙箱。
- 不向模型暴露 runner 内部 Token、实际容器路径和后端网络信息。

---

## 八、LangGraph Agent 图设计

### 8.1 节点与路由

```text
START
  │
  ▼
prepare_context
  │
  ▼
retrieve ──> rerank
                  │
                  ▼
                agent
                  │
        tools_condition
           ┌────┴────┐
           ▼         ▼
    authorize_tools   finalize
           │         │
     ┌────┼───┐     ▼
     ▼     ▼   ▼    END
 execute approve reject
     │     │   │
     │  interrupt  └──> rejected_tool_message
     │     │                 │
     └─────┴────────────────┐
                         ▼
                       tools
                         │
                         └──> agent
```

### 8.2 节点职责

| 节点 | 职责 |
| :--- | :--- |
| `prepare_context` | 校验会话上下文，创建工作区，写入用户/会话/工具运行状态 |
| `retrieve` | 复用当前向量粗召回 |
| `rerank` | 复用当前大模型精排，发送引用来源 |
| `agent` | 裁剪历史，构造 RAG 上下文，绑定当前允许的工具，返回 `AIMessage` |
| `authorize_tools` | 检查工具白名单、角色、工作区、风险等级和是否需人工审批 |
| `tools` | `ToolNode`执行获批的工具，生成 `ToolMessage` |
| `rejected_tool_message` | 为被拒绝的调用生成受控 `ToolMessage`，使 Agent 能继续回答 |
| `finalize` | 取最后一条无 `tool_calls` 的 AI 消息，持久化回答、引用和工具记录 |

### 8.3 Agent 节点模型调用

Agent 节点使用 `ChatPromptTemplate + MessagesPlaceholder + model.bind_tools(tools)`：

- System Prompt 保留 LabAgent 教学助手身份、RAG 参考资料和不编造要求。
- 增加工具使用原则：需要真实读取/修改工作区或执行命令时必须调用工具，不得伪造执行结果。
- RAG 文档使用框架 Prompt 模板渲染为参考上下文，不把检索文档添加到 checkpointer 的历史消息中。
- 必须保留模型原始 `AIMessage`，不使用会把 `tool_calls` 解析成纯字符串的输出解析器。

### 8.4 循环与停止条件

- 最后 AI 消息有 `tool_calls`：`tools_condition` 路由到 `authorize_tools`。
- 无 `tool_calls`：路由到 `finalize`。
- ToolNode 执行完成后回到 `agent`，由模型基于 `ToolMessage` 判断继续调用或最终回答。
- `RunnableConfig.recursion_limit` 与 `agent_max_tool_rounds` 双重限制循环。
- 到达最大轮次时，不再绑定工具，向模型添加「必须基于已有结果给出最终回答」的系统约束。

---

## 九、人工审批与恢复设计

### 9.1 暂停流程

`authorize_tools` 发现文件删除或 Shell 删除类命令后：

1. 创建或更新工具记录为 `pending_approval`。
2. 调用 `interrupt(payload)`，payload 包含工具名、脱敏参数、风险等级和调用 ID。
3. checkpointer 保存图状态，当前 SSE 发送 `tool_approval_required` 及 `paused` 后结束，不发送 `final`。
4. 前端保留当前助手消息和待审批状态，不把消息标记为完成。

### 9.2 恢复流程

1. 前端调用 `POST /api/v1/ai/react-agent/resume`，传入 `session_id`、`interrupt_id` 和 `approved`。
2. 后端从 JWT 重新获取当前用户，校验会话归属、`thread_id`、待恢复 interrupt 和工具记录状态。
3. 使用 `graph.astream(Command(resume={...}), config=...)` 恢复图。
4. 批准后进入 ToolNode；拒绝后生成与原 `tool_call_id` 对应的 `ToolMessage`，再返回 Agent。
5. 恢复接口继续使用 SSE，前端把后续工具事件和 Token 追加到原助手消息。

### 9.3 并行工具与审批

- 同一 AI 消息包含多个无需确认的工具时，ToolNode 可保留框架并行执行。
- 只要存在一个需审批工具，`authorize_tools` 将整批调用作为审批上下文。
- 前端显示每个工具及其参数；第一版对整批统一批准或拒绝，不做单个勾选。

---

## 十、SSE 事件设计

### 10.1 统一外层结构

延用当前协议：

```json
{
  "event_type": "tool_call",
  "session_id": "...",
  "trace_id": "...",
  "ts": 1784044800000,
  "payload": {}
}
```

### 10.2 事件清单

| `event_type` | 发送时机 | payload 核心字段 |
| :--- | :--- | :--- |
| `session` | 会话创建/确认 | `session_id` |
| `sources` | RAG rerank 完成 | `sources` |
| `tool_call` | Agent 生成新 `tool_calls` | `tool_call_id`, `tool_name`, `arguments`, `round`, `risk_level` |
| `status` | 工具状态变化 | `stage`, `tool_call_id`, `tool_name`, `round`, `success` |
| `tool_result` | ToolMessage 产生 | `tool_call_id`, `tool_name`, `success`, `result_summary`, `duration_ms`, `round` |
| `tool_approval_required` | Graph interrupt | `interrupt_id`, `tool_calls`, `risk_level` |
| `paused` | 图已安全暂停 | `reason`, `interrupt_id` |
| `token` | 最终回答 Token | `content` |
| `error` | 不可恢复失败 | `message`, `error_code` |
| `final` | 当前运行已完成 | `done`, `tool_call_count` |

`status.stage` 取值：

- `tool_pending`
- `tool_running`
- `tool_done`
- `tool_failed`
- `tool_timeout`
- `tool_rejected`
- `tool_cancelled`
- `global_timeout`

### 10.3 工具调用事件示例

```json
{
  "event_type": "tool_call",
  "session_id": "0c31...",
  "trace_id": "4b9a...",
  "ts": 1784044800000,
  "payload": {
    "tool_call_id": "call_123",
    "tool_name": "read_file",
    "arguments": {"file_path": "input/Main.java"},
    "round": 1,
    "risk_level": "low"
  }
}
```

```json
{
  "event_type": "tool_result",
  "session_id": "0c31...",
  "trace_id": "4b9a...",
  "ts": 1784044800500,
  "payload": {
    "tool_call_id": "call_123",
    "tool_name": "read_file",
    "success": true,
    "result_summary": "Read 86 lines from input/Main.java",
    "duration_ms": 500,
    "round": 1
  }
}
```

### 10.4 事件来源

`AiService` 继续通过 `graph.astream` 消费多模式流：

- `messages`：捕获 Agent 节点生成的 Token 和完整 AI 消息。
- `updates`：捕获 Agent/authorize_tools/ToolNode 的状态更新和 `ToolMessage`。
- `custom`：捕获 RAG 来源、工具内部进度和沙箱执行进度。

不通过循环手工调用工具后再伪造 SSE；SSE 只是把图的真实运行状态转换为前端协议。

---

## 十一、数据模型与持久化设计

### 11.1 新增 chat_tool_call 表

| 字段 | 类型 | 约束/说明 |
| :--- | :--- | :--- |
| `id` | BIGSERIAL | 主键 |
| `session_id` | UUID | 非空，所属会话 |
| `user_id` | BIGINT | 非空，用于审计和归属校验 |
| `message_id` | BIGINT | 可空，最终助手消息保存后回填 |
| `trace_id` | VARCHAR(64) | 单次 SSE 链路标识 |
| `tool_call_id` | VARCHAR(128) | 模型生成的工具调用 ID |
| `interrupt_id` | VARCHAR(128) | 可空，人工审批暂停 ID |
| `round` | INTEGER | Agent 工具轮次 |
| `tool_name` | VARCHAR(100) | 工具名 |
| `tool_source` | VARCHAR(50) | `langchain_file` / `langchain_shell` / 后续其他来源 |
| `risk_level` | VARCHAR(20) | `low` / `medium` / `high` |
| `arguments` | JSONB | 脱敏、截断后参数 |
| `status` | VARCHAR(30) | `pending` / `pending_approval` / `running` / `success` / `failed` / `timeout` / `rejected` / `cancelled` |
| `result_summary` | TEXT | 给历史展示与模型观测的摘要 |
| `error_message` | TEXT | 可空，受控错误信息 |
| `started_at` | TIMESTAMP | 开始时间 |
| `finished_at` | TIMESTAMP | 可空，结束时间 |
| `duration_ms` | BIGINT | 执行耗时 |
| `created_at` | TIMESTAMP | 记录创建时间 |

索引与约束：

- 索引：`session_id`、`message_id`、`trace_id`、`tool_call_id`。
- 唯一约束建议：`(session_id, tool_call_id)`。
- `message_id` 可空，因为工具会在最终助手消息保存前执行。

### 11.2 持久化时机

1. 发现 `AIMessage.tool_calls` 时插入 `pending` 记录。
2. 需审批时更新为 `pending_approval` 并保存 `interrupt_id`。
3. 执行前更新为 `running`。
4. 执行后更新为 `success` / `failed` / `timeout`。
5. 用户拒绝或取消时更新为 `rejected` / `cancelled`。
6. 最终助手消息入库后，按本次 `trace_id` 回填 `message_id`。

工具记录在流式生命周期内使用独立短事务，不持有一个跨越整个 SSE 连接的数据库事务。

### 11.3 历史消息返回

`ChatMessageVO` 新增：

```python
tool_calls: list[ChatToolCallVO] = Field(default_factory=list)
```

`ChatToolCallVO` 至少返回：

- `tool_call_id`
- `tool_name`
- `arguments`
- `status`
- `result_summary`
- `error_message`
- `duration_ms`
- `round`
- `risk_level`

历史接口按消息 ID 批量查询工具记录，禁止对每条消息逐个查询造成 N+1。

---

## 十二、API 契约

### 12.1 Agent 对话

`POST /api/v1/ai/react-agent`，返回 SSE。

```json
{
  "message": "读取 input/Main.java 并帮我分析空指针问题",
  "session_id": "0c31...",
  "model": "qwen3:8b"
}
```

- 不接受 `user_id`，前端需删除当前多余传参。
- 后端必须先校验会话归属，再构造 `thread_id`。

### 12.2 恢复审批

`POST /api/v1/ai/react-agent/resume`，返回 SSE。

```json
{
  "session_id": "0c31...",
  "interrupt_id": "int_123",
  "approved": true
}
```

请求模型：

```python
class AgentResumeRequest(BaseModel):
    session_id: str
    interrupt_id: str
    approved: bool
```


### 12.4 会话历史

`POST /api/v1/ai/rag/history` 路径保持不变，`ChatMessageVO` 增加 `tool_calls`。

---

## 十三、后端模块设计

### 13.1 建议目录

```text
backend/app/
├── graph/
│   └── agent_graph.py             # RAG + Agent + ToolNode + 审批图
├── tools/
│   ├── registry.py                # Tool Registry
│   ├── policy.py                  # 工具权限、路径、命令策略
│   ├── workspace.py               # 用户/会话工作区
│   ├── result.py                  # 脱敏、截断、摘要
│   ├── file_tools.py              # FileManagementToolkit 适配
│   └── shell_tool.py              # ShellTool + SandboxShellProcess
├── services/
│   ├── tool_call_service.py       # 工具记录生命周期
│   └── tool_runner_client.py      # 调用内部 Tool Runner
├── repositories/
│   └── tool_call_repository.py
├── models/
│   └── chat_tool_call.py
└── schemas/
    └── tool.py
```

新增 Python 文件必须按项目规范添加 `caoshuai.cs` 文档注释、完整类型注解和必要中文说明。

### 13.2 职责边界

- API 路由只做请求校验、JWT 依赖与 StreamingResponse 组装。
- `AiService` 管理业务会话、Graph 调用、SSE 转换和最终消息保存。
- `agent_graph.py` 只定义状态、节点、边和框架循环。
- `tools/` 处理工具定义、策略和框架适配。
- Repository 与 Service 负责工具记录入库，工具函数中不直接编写 SQL。

---

## 十四、前端适配设计

> Codex 风格的命令执行与文件查看活动聚合、两级折叠和 Shell 输出预览，详见 [06-Codex风格工具活动展示设计](./06-Codex风格工具活动展示设计.md)。第一版已完成落地。

### 14.1 复用现有能力

- `ChatInput.vue` 已能处理 `tool_call`、`tool_result`和 `status` 事件。
- Chat Store 已在每个会话内保存 `toolEvents`，能避免切换会话后工具事件串流。
- `MessageItem.vue` 已有工具列表、超时状态和图标展示。

### 14.2 需要修改

1. API 边界使用蛇形字段：`tool_name`、`tool_call_id`、`result_summary`、`duration_ms`、`risk_level`。
2. 工具事件按 `tool_call_id` 关联，不再只使用 `round` 关联；同一轮可有多个工具。
3. 工具卡片显示状态、工具名、参数摘要、结果摘要和耗时；参数/结果支持折叠。
4. 对文件内容、Shell 输出和超长字段做纯文本展示，禁止作为 HTML 直接渲染。
5. 增加 `ToolApprovalInline.vue`，在当前助手消息下方显示删除命令/路径和允许、拒绝按钮，不使用遮罩弹窗。
6. `tool_approval_required` 后标记会话为 `awaiting_approval`，原 SSE 正常结束也不把助手消息标记完成。
7. 批准/拒绝时调用 resume SSE，继续追加到原会话和原助手消息。
8. 历史加载直接读取 `msg.tool_calls`，删除从 `content` 中解析 `thinking_process_start` 隐藏注释的逻辑。
9. 用户点击停止时，前端结束当前 Fetch；后端捕获取消后更新工具记录并终止 runner 进程。

### 14.3 前端状态

每个会话状态增加：

```javascript
{
  messages: [],
  isLoading: false,
  isStreaming: false,
  awaitingApproval: false,
  pendingApproval: null
}
```

组件内部可使用驼峰命名，但读取后端 API/SSE 时仍必须按蛇形字段取值。

---

## 十五、超时、异常、取消与降级

### 15.1 超时分层

| 层级 | 配置 | 处理 |
| :--- | :--- | :--- |
| 单工具 | `tool_timeout_seconds` | 工具记录标记 `timeout`，生成可控 ToolMessage |
| Shell | `shell_timeout_seconds` | 终止进程组，保留截断输出 |
| Agent 全局 | `agent_timeout_seconds` | 停止新工具调用，基于已有观测生成最终回答 |
| 循环 | `agent_max_tool_rounds` | 不再绑定工具，强制最终回答 |

### 15.2 工具异常

- Tool Policy 拒绝：返回「该工具或参数不允许」，不暴露内部路径和策略规则。
- Pydantic 参数校验失败：由 ToolNode/BaseTool 生成可返回模型的错误，允许模型修正参数后重试。
- 文件不存在/无权限：返回受控错误，不使整张图失败。
- runner 不可用：Shell 返回「执行环境暂不可用」，Agent 继续基于其他信息回答。
- 未预期异常：记录 `trace_id`、工具名和错误类型，不记录完整敏感参数。

### 15.3 客户端取消

- SSE 生成器收到取消时，取消 Graph `astream` 任务。
- 已经运行的 Shell 通过 runner 的 cancellation token 终止。
- 未执行工具标记 `cancelled`，不保存空助手消息。
- 如已有部分最终回答，是否保存由统一策略决定；第一版建议不保存未完成回答。

---

## 十六、安全设计

### 16.1 身份与资源

- 当前用户只从 JWT 获取，请求体中不存在 `user_id`。
- 对话、历史、审批恢复、工作区和工具记录都必须校验当前用户归属。
- Shell 可用性由服务端配置与角色决定，前端不能通过传参开启。

### 16.2 Prompt Injection

- 用户输入、RAG 文档、文件内容和 Shell 输出都视为不可信数据。
- System Prompt 明确说明工具结果中的指令、密钥索取或越权请求不得作为新的系统指令执行。
- 工具执行权限不依赖模型自律，始终由 Tool Policy 硬校验。

### 16.3 敏感信息

- 记录和 SSE 中的参数需递归脱敏 `password`、`token`、`secret`、`api_key`、`authorization` 等字段。
- 读文件或 Shell 输出中出现疑似密钥时，对前端展示和日志做遮蔽。
- 完整工具输出只在当前运行内作为 ToolMessage 使用，入库只保存摘要和受控错误。

---

## 十七、配置设计

| Settings 字段 | 建议默认值 | 说明 |
| :--- | :--- | :--- |
| `agent_tools_enabled` | `true` | Agent 工具总开关 |
| `file_tools_enabled` | `true` | 文件工具开关 |
| `shell_tool_enabled` | `false` | Shell 默认关闭，完成沙箱配置后显式开启 |
| `shell_allowed_roles` | `admin` | 允许使用 Shell 的角色 |
| `shell_delete_require_approval` | `true` | Shell 删除类命令是否审批 |
| `file_write_require_approval` | `false` | 普通写操作是否审批，当前保持关闭 |
| `file_move_require_approval` | `false` | 移动操作是否审批，当前保持关闭 |
| `file_delete_require_approval` | `true` | 删除默认审批 |
| `tool_workspace_root` | `/data/tool-workspaces` | 工作区根目录 |
| `tool_max_read_chars` | `12000` | 单次文件读取返回上限 |
| `tool_max_write_chars` | `24000` | 单次写入上限 |
| `tool_max_search_results` | `50` | 搜索结果上限 |
| `tool_max_output_chars` | `12000` | 通用工具输出上限 |
| `tool_timeout_seconds` | `60` | 通用单工具超时 |
| `shell_timeout_seconds` | `20` | Shell 执行超时 |
| `agent_timeout_seconds` | `180` | Agent 全局超时 |
| `agent_max_tool_rounds` | `8` | 最大工具轮次 |
| `tool_runner_base_url` | `http://tool-runner:8990` | 内部 runner 地址 |
| `tool_runner_token` | 无默认值 | 内部 runner 鉴权，只从环境变量读取 |

同步更新 `.env.example`、Docker Compose 和 README；禁止在代码中硬编码 runner Token。

---

## 十八、测试设计

### 18.1 后端单元测试

- Tool Registry：重名工具拒绝、开关/角色过滤、不支持 Tool Calling 模型过滤。
- Workspace Manager：用户/会话路径隔离、目录惰性创建、非法 ID 拒绝。
- 文件工具：`../`、绝对路径、软链接越界、文件不存在、读写超限、删除审批。
- Shell Policy：未启用、非授权角色、危险命令、超长命令和已批准命令。
- 结果处理：长输出截断、敏感字段递归脱敏、摘要生成。
- ToolCall Repository/Service：状态流转、批量历史查询和 `message_id` 回填。

### 18.2 Graph 集成测试

使用可控 Fake ChatModel 生成固定 `tool_calls`，验证：

- 无工具回答直接进入 `finalize`。
- 单工具：`agent → authorize_tools → tools → agent → finalize`。
- 多工具：同转生成多个 ToolMessage，按 `tool_call_id` 关联。
- 工具参数错误后模型可修正并重试。
- 高风险工具 interrupt，approve/reject 均能恢复。
- 最大轮次和全局超时能收敛，不出现无限循环。
- RAG 检索文档不污染 checkpointer 历史。

### 18.3 SSE 与 API 测试

- `session → sources → tool_call → status → tool_result → token → final` 事件顺序。
- 并行工具的 `tool_call_id` 不串联。
- 审批时返回 `tool_approval_required → paused`，不返回 `final`。
- resume 接口未登录、他人会话、无效 interrupt 和重复恢复均被拒绝。
- 客户端取消后工具记录转为 `cancelled`。

### 18.4 前端测试

- 工具调用与结果按 `tool_call_id` 匹配。
- 同一轮多工具独立展示。
- 工具成功、失败、超时、拒绝、取消状态正确。
- 审批弹窗批准/拒绝后能继续同一条助手消息。
- 页面刷新后可从 `tool_calls` 恢复工具卡片。
- 超长工具输出不影响页面渲染和滚动性能。

### 18.5 安全与容器验证

- runner 无法读取 backend `.env`、Docker Socket 或宿主用户目录。
- Shell 超时后子进程与孙进程均被结束。
- runner 的 CPU、内存、PIDs 和网络限制有效。
- `docker compose config` 通过，后端和 runner 共享工作区卷但不共享敏感卷。

---

## 十九、实施顺序

1. **依赖与配置**：确认使用现有 `langchain-community` 工具，补充 Settings、`.env.example`与模型 Tool Calling 能力配置。
2. **工作区和文件工具**：实现 Workspace Manager、Tool Policy 和 FileManagementToolkit 适配，先打通只读再打通写入/删除。
3. **工具记录**：新增 `chat_tool_call` 模型、Alembic、Repository、Service 和历史 VO。
4. **Agent 图**：把当前 RAG 图升级为 `agent + authorize_tools + ToolNode` 循环，先用 Fake Tool/Fake Model 验证。
5. **SSE 与前端卡片**：打通工具调用、结果、失败、超时和历史恢复。
6. **Shell Runner**：实现 SandboxShellProcess 与内部 runner，完成资源、网络、超时和取消隔离。
7. **人工审批**：接入 interrupt/resume 和消息内联审批卡片，验收文件删除和 Shell 删除类命令。
8. **回归与文档**：运行后端测试、前端测试/构建、Docker Compose 检查，同步 README。

---

## 二十、验收标准

- Agent 可根据用户指令选择正确的文件工具，不伪造工具执行结果。
- 单次请求可连续执行多个工具，工具结果通过 ToolMessage 返回模型后继续推理。
- 文件工具只能访问当前用户/会话工作区，路径遍历和软链接越界均失败。
- Shell 集成完成但默认关闭；启用后只在 runner 沙箱内执行，普通命令直行，删除类命令需审批。
- 工具调用的开始、运行、成功、失败、超时、拒绝和取消均有结构化 SSE 事件。
- 前端能实时展示多工具调用，能审批/拒绝高风险工具，刷新后可恢复历史。
- 用户不能恢复他人会话的 interrupt，不能通过前端传参开启未授权工具。
- Agent 在工具异常、runner 不可用、超时或达到最大轮次时能可控收敛。
- 现有 RAG 检索、引用来源、会话隔离、SSE Token 和历史消息功能不回归。

---

## 二十一、本阶段结论

- 第四阶段不是只增加几个工具函数，而是建立一条可持续扩展的「工具注册 → 模型选择 → 策略/审批 → ToolNode 执行 → ToolMessage 回传 → SSE 展示 → 历史持久化」链路。
- 文件和 Shell 的实际功能优先复用 LangChain，LangGraph 负责 Agent 循环和人工审批；项目自研部分聚焦在身份、工作区、安全、持久化与前端协议。
- 第一版保留 RAG 前置节点，避免 Agent 改造导致第三阶段知识问答能力倒退。
- Shell 能力只有在受控 runner、工作区隔离和服务端授权满足时才可开启；删除类命令额外经过前端内联审批，不因为框架提供了 `ShellTool` 就直接执行宿主命令。

## 二十二、工具粒度演进：从细粒度文件工具到统一终端工具（调研）

> 本节为 2026-07-15 追加的调研，起因：实测中「当前文件夹有什么，把这个任务保存到 test.py」这类简单指令，
> Agent 需要连续调用 `list_directory` + `write_file` 多个细粒度文件工具，前端工具卡片信息零散、无法直观展示，
> 用户体感是「一堆看不到细节的文件操作」。调研 Codex 等主流编码 Agent 的做法后沉淀改造方向。**本节仅设计，暂不改代码。**

### 22.1 现状问题

当前 LabAgent 对模型暴露 8 个工具（见 [四、工具清单](#四工具清单与参数设计)）：
`list_directory`、`file_search`、`read_file`、`write_file`、`copy_file`、`move_file`、`file_delete`、`execute_shell`。

- **工具太多太碎**：一个「看目录 + 写文件」任务要 2~3 次工具往返，Agent 轮次多、延迟高、Token 消耗大。
- **展示零散**：每个细粒度工具是一张独立卡片，用户看不到「到底做了什么」的连贯过程（如截图：只有「查看了文件」「已写入文件 test.py」两条干巴巴的记录，展开也没有命令细节）。
- **能力仍有限**：细粒度文件工具无法覆盖「运行代码、跑测试、grep、组合管道」等真实编码场景，而这些用一条 shell 命令就能完成。

### 22.2 Codex / GPT-5.1 的做法（调研结论）

主流本地编码 Agent（OpenAI Codex CLI、GPT-5.1）收敛到**极少数通用工具**：

- **`shell`（exec）工具**：让模型运行任意 shell 命令。查看目录（`ls`）、读文件（`cat`）、搜索（`grep`/`rg`）、运行代码、跑测试，全部通过一条命令完成，不再为每种文件操作单独造工具。
- **`apply_patch` 工具**：专门用于**可靠地编辑/创建文件**（以结构化 patch 形式增删改），比让模型直接 `echo >` 写文件更精确、更可控。
- Codex 的安全不靠「限制工具种类」，而靠**沙箱 + 审批策略**（execpolicy / linux-sandbox）：命令在受限沙箱执行，越权操作需用户批准。

核心理念：**工具少而通用，安全交给沙箱和审批，而不是靠切碎工具粒度。** 这与本项目第七章「Shell 受控执行」的沙箱思路一致。

### 22.3 LabAgent 改造方向

保留第七章已设计的沙箱 + 审批体系，把工具从「8 个细粒度」收敛为「统一终端工具为主」：

**方案（推荐）：以 `execute_shell` 为主工具 + 保留 `write_file` 做可靠写入**

| 能力 | 现状 | 改造后 |
| :--- | :--- | :--- |
| 看目录 / 读文件 / 搜索 | `list_directory` / `read_file` / `file_search` | 统一走 `execute_shell`（`ls` / `cat` / `grep`） |
| 复制 / 移动 / 删除 | `copy_file` / `move_file` / `file_delete` | 统一走 `execute_shell`（`cp` / `mv` / `rm`，`rm` 命中删除类审批） |
| 写入 / 创建文件 | `write_file` | **保留**：多行内容、代码写入用专门工具比 shell 里 `echo`/heredoc 更可靠（对齐 Codex 的 `apply_patch` 思路） |

- **好处**：工具从 8 个降到 2 个（`execute_shell` + `write_file`），Agent 单轮就能完成「看目录 + 写文件」，轮次和延迟显著下降；前端只需展示「执行的命令 + 输出」，天然对齐第六章 Codex 风格活动展示。
- **安全不降级**：所有 shell 命令仍走第七章沙箱 + 命令策略（`_BLOCKED_EXECUTABLES` / 危险模式拦截）+ 删除类审批；写文件仍受工作区路径隔离约束。
- **风险分级调整**：`execute_shell` 只读类命令（`ls`/`cat`/`grep`）视为 `low`，写/删类命令按现有策略升级为 `medium`/`high`。这需要命令解析来区分（比按工具名分级更细，属实现细节）。

**取舍说明**：

- 是否引入 Codex 式 `apply_patch`（结构化 diff 编辑）本阶段**不做**，成本高且当前 `write_file` 已能满足教学场景的整文件写入；先用「shell + write_file」验证收敛效果。
- 若要完全对齐 Codex 只留一个 shell 工具，需让模型用 heredoc 写文件，可靠性和可读性都更差，不推荐。

### 22.4 待办（不在本次）

- [ ] `registry.py` 收敛工具集：默认只暴露 `execute_shell` + `write_file`，其余文件工具降级为「可选/关闭」或移除。
- [ ] `policy.py` 增加 shell 命令**读写分级**：只读命令 `low` 直行，写/删命令按 `medium`/`high` 审批。
- [ ] 前端工具卡片以「命令 + 输出」为主视图（第六章已有 Codex 风格展示基础，减少细粒度文件卡片类型）。
- [ ] 确认沙箱（第七章 Tool Runner）落地后再放开 shell 为主力工具；沙箱未就绪前维持现状。
- [ ] 评估是否需要 `apply_patch` 式结构化编辑（后续阶段，非本阶段）。

---

## 二十三、工作区文件预览：对齐 Codex 的「产物可见」体验（调研）

> 本节为 2026-07-15 追加的调研，起因：Agent 通过 `write_file` 写入 `test.py` 后，
> 前端工具卡片只显示「已写入文件 test.py」一行文字，用户无法直接看到写了什么内容、也无法预览代码或 Markdown。
> 用户希望像 Codex 那样「产物可见」——写完文件能在界面上预览，且不仅是代码，还包括 Markdown 等常见内容。**本节仅设计，暂不改代码。**

### 23.1 现状问题

- `write_file` 工具执行后，`result_envelope` 只回传 `summary="已写入文件 {path}"`（见 [file_tools.py](../backend/app/tools/file_tools.py)），
  `output` 是 `FileManagementToolkit` 的文字回执，**不含文件正文**。
- 前端 [ToolActivityPanel.vue](../frontend/src/components/ToolActivityPanel.vue) 对 `write_file` 只走默认分支展示一行摘要，没有预览入口。
- 工作区文件（`data/tool-workspaces/{user_id}/{session_id}/`）目前**没有任何对前端可读的接口**：
  知识库文件走 MinIO + `GET /knowledge/downloadFile/{id}`（见 [knowledge.py](../backend/app/api/v1/knowledge.py)），
  但 Agent 工作区文件在本地磁盘卷里，前端拿不到。

### 23.2 Codex 的做法与本项目的取舍（调研结论）

主流本地编码 Agent（OpenAI Codex CLI）的「产物可见」是：

- **编辑通过 `apply_patch` 完成**，其参数本身就是结构化 diff（哪些行增/删/改），TUI 直接渲染成带颜色的「+ 绿 / - 红」变更视图——预览的数据来自工具调用本身。
- **查看/读取通过 `shell`（`cat`/`sed -n`）完成**，输出即命令结果。

**本项目明确不做 diff 展示**：LabAgent 用的是 `write_file`（整文件写入，非 diff patch），面向的是高校实验教学场景（写作业代码、生成 Markdown 说明等整文件产物），而非在既有大代码库里改几行。
因此**预览就是「整文件内容」**，按内容类型（代码 / Markdown / 纯文本）渲染即可，不需要计算和渲染逐行 diff。真正值得借鉴 Codex 的只有一点：**展示层按内容类型渲染工具产物**。

### 23.3 LabAgent 改造方向

分两层，**推荐组合 A + B**：

**A. `write_file` 结果携带内容预览（轻量，改动小）**

- `write_file` 成功后，在 `result_envelope` 里新增预览字段，随 `tool_result` SSE 事件下发：
  - `preview_path`：相对工作区路径（如 `output/test.py`）。
  - `preview_language`：由扩展名推断（`.py`→python、`.md`→markdown、`.java`→java、`.txt`→text…）。
  - `preview_content`：写入的**整文件正文**，复用现有 `truncate_text` 截断（超长只给前 N 字符 + 提示，避免 SSE 过大）。
- 优点：无需新接口，写完即可预览，数据就是刚写入的内容（无一致性问题）。
- 局限：只覆盖「刚写入」的文件；用户想看**别的已存在文件**或**完整超长文件**时不够。

**B. 新增工作区文件只读接口（通用，覆盖 A 的局限，兼顾预览与下载）**

- 新增 `GET /ai/workspace/file`，入参 `session_id` + 相对路径，用 `disposition` 区分两种用途：
  - `disposition=inline`（默认）：返回文件内容供**预览**，前端按 `preview_language` 渲染。
  - `disposition=attachment`：以 `StreamingResponse` + `Content-Disposition: attachment` 返回**下载**流
    （对齐知识库 [knowledge.py](../backend/app/api/v1/knowledge.py) 的 `GET /knowledge/downloadFile/{id}` 下载方式）。
- 复用既有安全设施：
  - `CurrentUser` 从 JWT 取 `user_id`，`WorkspaceManager.ensure_workspace(user_id, session_id)` 定位工作区，
    **强校验会话归属**（防止越权读他人工作区）。
  - `validate_relative_path(..., allow_missing=False)` 做路径穿越 / 软链接越界防护（工作区安全能力已在 [workspace.py](../backend/app/tools/workspace.py) 就绪）。
  - `validate_file_size` 做大小上限：超限的文本/代码不内联预览，改为提示走**下载**；二进制文件一律只提供下载。
- 前端点击文件卡片的「预览」入口时，按需调此接口拉取内容渲染；「下载」入口则以 `attachment` 拉流保存。

**前端渲染（整文件预览，不做 diff；对齐图2 的「代码 + Markdown 等常见内容」）**

- 代码类（`.py`/`.java`/`.js`/`.json`…）：整文件语法高亮代码块（前端已有 Markdown 渲染栈，可复用其代码高亮）。
- Markdown（`.md`/`.markdown`）：渲染为富文本预览，可提供「源码 / 渲染」切换。
- 纯文本（`.txt`/`.log`）：等宽纯文本展示。
- 其他二进制（图片等）：本阶段不做内联预览，仅提供**下载**（走接口 B 的 `disposition=attachment`），避免范围膨胀。
- 每类文件卡片统一提供「下载」入口（无论能否预览都可下载），预览仅对可读文本/代码/Markdown 生效。

### 23.4 SSE 与契约影响

- 沿用第十章统一外层结构，仅在 `tool_result` 的 `payload` 里为 `write_file` 增补可选字段
  `preview_path` / `preview_language` / `preview_content`（其他工具不带，前端按存在与否判断）。
- 字段全程蛇形命名，与既有契约一致（见 [十、SSE 事件设计](#十sse-事件设计)）。
- 安全：预览内容同样经 `redact_value` 脱敏（工具产物本就视为不可信数据，且可能含密钥）。

### 23.5 待办（不在本次）

- [ ] `file_tools.py`：`write_file` 成功时在 envelope 增补 `preview_path`/`preview_language`/`preview_content`（复用 `truncate_text`）。
- [ ] `result.py`：`result_envelope` 支持可选预览字段（保持对其他工具零影响）。
- [ ] 新增 `GET /ai/workspace/file` 只读接口：JWT 归属校验 + `validate_relative_path(allow_missing=False)` + 大小上限；`disposition=inline` 预览、`disposition=attachment` 流式下载。
- [ ] `ToolActivityPanel.vue`：`write_file` 卡片加「预览」与「下载」入口，预览按 `preview_language` 分代码 / Markdown / 纯文本渲染。
- [ ] 二进制/图片仅下载，不做内联预览。

> **落地进度（2026-07-15）**：23.5 前四项已实现——`result_envelope` 支持可选预览字段、`write_file` 成功回传整文件正文、
> 新增 `GET /ai/workspace/file`（inline/attachment 双模式）、`ToolActivityPanel.vue` 工具卡片内可展开预览 + 下载。
> 但工具卡片内预览属于「工具调用详情」，用户默认不会展开查看，见下方 23.6 的交互升级。

### 23.6 交互升级：正文超链接 + 右侧预览侧栏（调研，暂不改代码）

> 起因（2026-07-15 二次反馈）：工具卡片内的预览「不是每个人都会去看」，但**正文里 AI 返回的产物路径才是用户真正会关注的**。
> 期望对齐 Codex/IDE 式体验：**正文中的产物路径渲染成超链接，点击后在右侧新开预览侧栏**，支持多文件同时预览（tab 页签）、可收起侧栏、显示文件路径与整文件正文；**不需要代码行号**。

#### 23.6.1 目标交互

- **正文超链接**：AI 回答正文里出现的工作区产物路径（如 `output/20260715_test.py`）渲染为可点击超链接，而非纯文本。
- **右侧预览侧栏**：点击超链接在聊天区右侧滑出独立预览面板（不遮挡对话），面板内：
  - **多文件 tab**：点击多个不同路径时以页签并存，可切换、可关闭单个 tab（对齐图2 顶部 `workspace.py +` 的多标签形态）。
  - **顶部工具条**：显示当前文件相对路径、下载按钮、收起侧栏按钮。
  - **正文内容**：整文件渲染（代码高亮 / Markdown / 纯文本），**不显示行号**、不做 diff。
- **降级**：窄屏（移动端）无右侧空间时，超链接点击回退为「就地展开」或全屏浮层，不强行分栏。

#### 23.6.2 「正文如何知道哪些路径是产物」——落到「产物注册」

这一步正是上一轮讨论的**产物注册与会话绑定**的真正用武之地。核心问题：AI 正文是自由文本，不能靠正则乱猜哪个词是文件路径（会误伤普通文本里的 `a/b`）。因此需要一份**权威的本会话产物清单**来做「路径 → 是否可预览」的判定：

- **数据来源（无需建新表）**：本会话所有 `write_file` 的 `chat_tool_call` 记录，其 `arguments.file_path` 即产物相对路径集合。这就是「产物注册表」的等价物——**产物 = 工作区文件、注册 = write_file 的 tool_call 记录、绑定 = session_id**。
- **前端消费**：前端已持有本轮 `toolEvents`（含 `write_file` 的 `preview_path`）。渲染正文时，用「本会话产物路径集合」做匹配——**只有命中集合的路径才渲染成超链接**，其余文本原样输出。这样既精准又零误伤。
- **历史消息**：会话历史里同样能从 `chat_tool_call` 取回产物清单（已有归属校验），保证刷新/重进会话后正文超链接依旧可点。

> 结论：**不需要新增 artifact 表**；「产物注册」通过既有 `chat_tool_call` 的 write_file 记录 + 前端产物路径集合即可实现。若未来要做跨会话资产库/版本管理再单独抽象。

#### 23.6.3 前端改造点（调研，非本次实现）

- **正文渲染管道**（[markdown.js](../frontend/src/utils/markdown.js) / [MessageItem.vue](../frontend/src/components/MessageItem.vue)）：
  在 `renderMarkdown` 结果基础上，对命中本会话产物集合的路径包一层 `<a class="artifact-link" data-path="...">`；
  点击事件统一在 `MessageItem` 的 `handleCodeBlockClick` 同级处理（事件委托），阻止默认跳转，改为通知预览侧栏。
- **预览侧栏组件**（新增，如 `WorkspacePreviewPanel.vue`）：
  - 状态放在 chat store（`previewTabs: [{path, language, content, loading}]` + `activePath` + `panelOpen`），保证多 tab、跨消息共享。
  - 打开某路径时：若 `toolEvents` 已带整文件正文直接用；否则调 `GET /ai/workspace/file?disposition=inline` 按需拉取（接口已就绪）。
  - 顶部下载按钮复用 `downloadWorkspaceFile`（`disposition=attachment`）。
  - 渲染复用现有代码高亮/Markdown 栈，但**关闭行号**、去掉工具卡片里的语言小标签冗余。
- **布局**（[Chat.vue](../frontend/src/views/Chat.vue)）：`chat-container` 由 `Sidebar + ChatMain` 两栏扩展为「Sidebar + ChatMain +（可选）PreviewPanel」；`panelOpen` 控制右栏显隐，宽屏分栏、窄屏浮层。
- **后端**：无需新增接口，`GET /ai/workspace/file` 的 inline/attachment 已覆盖预览与下载。

#### 23.6.4 待办（后续实现）

- [ ] 前端：在 chat store 增加预览侧栏状态（多 tab、activePath、panelOpen）与打开/关闭/切换 action。
- [ ] 前端：正文渲染时按「本会话产物路径集合」把命中路径渲染为 `artifact-link` 超链接，事件委托打开侧栏。
- [ ] 前端：新增 `WorkspacePreviewPanel.vue`（多 tab、路径展示、下载、收起，**无行号**、非 diff）。
- [ ] 前端：`Chat.vue` 布局支持右侧预览栏，宽屏分栏 / 窄屏浮层降级。
- [ ] 复用：产物路径集合从 `toolEvents`（实时）与 `chat_tool_call`（历史）两处获取，无需新建表、无需新接口。

---

## 参考文档

- [LangChain Tools](https://docs.langchain.com/oss/python/langchain/tools)
- [LangGraph Workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [OpenAI Codex](https://github.com/openai/codex)（shell + apply_patch 双工具、sandbox/execpolicy 安全模型）
