# AGENTS.md

## 项目定位

本项目是面向教学实验的 Agentic RAG 平台，名为 LabAgent。

核心目标：

- 帮助学生理解实验要求和课程知识。
- 帮助学生使用实验教学平台。
- 对代码错误提供解释和排查建议。
- 基于 Agentic RAG 与三级检索回答问题，减少模型幻觉。
- 借助 RAGAS 评测沉淀检索和回答效果优化闭环。
- 通过沙箱隔离与工具安全控制降低工具调用风险。
- 降低教师重复答疑成本。

## 阶段情况
阅读 [阶段情况](docs/阶段.md)
要从javalabagent迁移过来
第一阶段已完成 done，产出文档：[第一阶段：产品与架构设计](./docs/01-产品与架构设计.md)
第二阶段设计已完成 done，产出文档：[第二阶段：基础后端设计](./docs/02-基础后端设计.md)
第三阶段已完成 done，产出文档：[第三阶段：RAG闭环设计](./docs/03-RAG闭环设计.md)、[RAG全流程实现与理解](./docs/04-RAG全流程实现与理解.md)
第四阶段已完成 done，产出文档：[第四阶段：Agent工具集成与调用链设计](./docs/05-Agent工具集成与调用链设计.md)、[Agent工具调用流程与实现理解](./docs/07-Agent工具调用流程与实现理解.md)
做一些具体的设计之前，可以跟我先讨论具体的实现，可以先给出你的建议；
重点要了解清楚LangGraph如何进行agent构建，对应文档[文档](https://docs.langchain.com/oss/python/langgraph/overview)

## 当前技术栈

- Python 3.12
- FastAPI
- LangGraph
- SQLAlchemy 2.0
- Alembic
- PostgreSQL + pgvector
- MinIO
- Vue 3
- Ollama
- OpenAI兼容模型接口
- Docker Compose

前端可参考javalabagent的前端，进行适配过来

## 当前范围

需要支持：

- 用户认证和角色权限。
- 会话与消息管理。
- RAG文档上传、解析、切分、向量化和检索。
- QA文档专用切分。
- Ollama和外部模型调用。
- SSE流式输出。
- 原生Tools。
- Markdown Skills。
- MinIO文件存储。
- Docker一键部署。
- 回答来源引用。
- 基础RAG评测。



## 开发原则

- 回答用户时使用中文。
- 优先进行最小改动，不修改与需求无关的代码。
- 质量优化、规范沉淀、重构和复用抽取必须保持现有功能和交互行为不变；除非用户明确要求，不允许借优化名义调整业务流程、接口契约、视觉样式或默认配置。
- 新功能必须保持模块职责清晰。
- 新增代码应补充必要的类型注解和中文说明。
- 文件末尾不添加多余空行。
- 不修改用户已有且与当前任务无关的改动。

## 框架能力优先（重要）

- 迁移是升级优化，不是原样照搬：从 javalabagent 迁移到 Python/LangGraph 技术栈时，目标是做出更好的版本，而非把参考项目的所有功能与实现方式全量搬过来。参考项目的过时做法、被语言/框架限制的妥协、可用框架能力替代的手写逻辑，都应在迁移时纠正或升级；能用更优方案（如框架能力、结构化返回、可配置化）就不要照搬旧实现。举例：RAG 用结构化「引用来源」替代 `【根据知识库】/【根据通用知识】` 回答前缀；切分参数、向量维度等改为可配置；上下文拼装、切片增量索引、rerank 用框架能力实现。
- 参考项目javalabagent的一个突出问题是：把本应由框架提供的能力都自己手写了（如手写滑动窗口记忆、手写滚动摘要、手写会话状态拼接、手写工具调用循环）。迁移到LangGraph后必须纠正这一点。
- 编排框架统一采用LangGraph。凡是LangGraph（含其底层依赖langchain-core，以及langchain-ollama/langchain-openai等模型集成包）已提供的能力，一律优先使用框架能力，禁止重复造轮子；只有框架未覆盖或需贴合教学业务的部分才自己实现。
- 明确应改用框架能力的场景：短期记忆与对话上下文用LangGraph checkpointer（AsyncPostgresSaver）+ MessagesState；上下文裁剪用trim_messages、消息删除用RemoveMessage、摘要按官方summarize模式；流式输出用图的astream；Agent与工具调用循环用create_react_agent或StateGraph+ToolNode；工具定义与参数校验用@tool+Pydantic；模型调用用langchain-ollama/langchain-openai的统一Runnable接口；提示词用ChatPromptTemplate。
- 仍需自研的是Web层（认证/JWT/权限）、业务数据表与Repository、MinIO封装、受控工具的内部业务逻辑、会话业务级增删查。
- 不确定框架是否提供某能力时，先查LangGraph官方文档确认，禁止臆测API名称与用法后就自行造轮子。

## Python代码规范

- 使用Python 3.12语法。
- 使用完整类型注解。
- 变量、函数、方法、模块、包名、以及 Pydantic 模型字段名一律使用蛇形命名（snake_case），禁止在 Python 代码中直接用驼峰命名字段/变量（类名用 PascalCase、常量用大写，属正常约定不受此限）。用户用驼峰描述字段时，需自行转换为蛇形理解与编码。
- 前后端 API 契约统一使用蛇形命名（snake_case），前后端零命名转换：后端 Pydantic 模型字段、路由的 Query/Form 参数、SSE 事件 JSON key（如 `event_type`/`session_id`）全部用蛇形直出；前端请求体、query 参数、以及读取后端响应/SSE 的字段也全部用蛇形对齐。禁止为了迁就前端历史驼峰而做任何 alias 转换（不得使用 `CamelModel`/`alias_generator=to_camel`/`Query(alias=...)`/`Form(alias=...)` 等命名转换），前端有非蛇形字段时应同步改成蛇形，而不是让后端迁就。前端组件内部纯本地状态（不跨后端边界的变量名，如 store 中的 `userName`、toolEvents 的 `eventType`）可保留原命名，仅在读写后端契约字段的边界处做一次显式映射。
- 后端内部数据链路全程蛇形、零字段名转换：数据库列名、SQLAlchemy 模型属性、Pydantic 请求/VO/DTO 字段一律同名蛇形（如 `user_name` 贯穿 DB 列 → ORM 属性 → VO 字段 → API 输出）。Service 层构造 VO 时禁止做 `user_name`→`userName` 之类的命名转换（这是 Java 因语言规范被迫的做法，Python 本身即蛇形，无需也不应转换）。
- API请求和响应使用Pydantic模型。
- 所有 API 接口必须统一用 `BaseResponse[T]` 包装返回（结构为 `{code, data, message}`，成功时 code=0、message="ok"）；成功用 `success(data)`、失败用 `error(error_code, message)`（见 [app/core/response.py](backend/app/core/response.py)）。禁止直接返回裸 dict、list 或实体对象。唯一例外是 SSE 流式接口（返回 `StreamingResponse`，如 `/ai/rag`、`/ai/react-agent`）。
- 接口的返回类型注解须写成 `BaseResponse[具体类型]`（如 `BaseResponse[list[ChatSessionVO]]`、`BaseResponse[bool]`），保证 OpenAPI 文档与前端契约一致。
- 分页返回统一用 `PageResult[T]`（`{total, records}`）作为 `data`，即 `BaseResponse[PageResult[T]]`。
- 数据库访问通过Repository或明确的数据访问层完成。
- 禁止在Controller/API路由中直接编写复杂业务逻辑。
- 配置统一通过环境变量和Settings读取。
- 禁止在代码中写死密钥、Token、密码和服务地址。
- 异步函数中禁止调用阻塞式IO；必须使用异步客户端或线程池隔离。
- 外部调用必须设置连接超时和读取超时。

## 前端代码规范

- 前端 API 契约字段必须与后端保持蛇形命名（snake_case）；跨后端边界的数据不做隐式驼峰转换，只有纯前端 UI 状态才允许使用驼峰命名。
- 前端质量优化应优先做行为保持型改造；抽取公共工具、替换重复逻辑或调整渲染方式时，必须保持原有入口、状态流转、交互路径和展示结果不变。
- 前端渲染用户输入、模型输出、工具结果、文件内容和 Skill 文档时，全部视为不可信内容；默认禁止直接使用 `v-html`。
- 必须使用 `v-html` 时，内容必须先经过统一的转义或白名单净化；Markdown 默认禁止原始 HTML，不能配置为直接信任 HTML。
- axios 请求、fetch 请求和 SSE 请求必须共用统一 API 基础路径，禁止在不同文件中分别写死 `/api` 或 `/api/v1`。
- Authorization 只保留一个注入入口，优先通过请求拦截器从本地状态读取，避免同时维护 axios 默认头和拦截器两套状态。
- 多组件复用逻辑应沉淀到 `utils`、`directives`、`constants` 或 `composables`，例如 HTML 转义、点击外部关闭、模型列表、下载 Blob、sleep 等。
- 从 javalabagent 迁移前端代码时必须清理 Java/Spring Boot 历史注释，注释和文档以当前 FastAPI/Vue/LabAgent 实现为准。

## 安全要求

- 当前用户ID必须从JWT身份中获取，禁止相信请求体中的userId。
- 管理接口必须验证管理员角色。
- 数据查询必须校验资源所有权或课程权限。
- 密码必须使用Argon2或bcrypt存储。
- JWT密钥必须从环境变量读取。
- 文件上传必须校验大小、类型、扩展名和文件名。
- Tool必须采用白名单机制。
- Tool参数必须经过Pydantic校验。
- 禁止默认提供任意Shell执行能力。
- 日志中禁止输出密码、JWT、API Key和完整敏感文档。
- 用户输入和工具结果进入Prompt前需要考虑Prompt Injection风险。

## 测试与验证

代码修改完成后，根据改动范围执行：

- 类型检查。
- pytest单元测试。
- 前端构建。
- Docker Compose配置检查。
- 如果只修改了前端，就重新构建前端的docker，默认开发者正在实时调试。
- 如果本次只修改了前端，最终答复只提供前端 Docker 重新构建与部署命令，不提供或要求执行后端及其他服务的重启命令。

## 文档要求

- 技术栈版本以实际配置文件为准。
- 修改接口、环境变量或部署方式时同步更新README。
- 架构文档不得把设计方案描述为已落地功能。
