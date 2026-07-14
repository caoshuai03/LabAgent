<!--
 @author: caoshuai.cs
 @date: 2026-07-14
 @description: 第三阶段产出——LabAgent RAG 闭环设计（文档解析、QA/普通切分、embedding 向量化、Indexing API 切片增量索引、pgvector 检索、大模型 rerank 精排、框架化上下文拼装、引用来源、知识库维护一致性、人工评测）
-->

# 第三阶段：RAG 闭环设计

> 本文档是 LabAgent 第三阶段产出，基于第二阶段 [基础后端设计](./02-基础后端设计.md)，
> 面向「RAG 闭环」落地：在已跑通的文件上传 / 存储 / 对话直连之上，补齐**文档解析 → 切分 → 向量化 → pgvector 写入 → 检索 → 大模型 rerank → 拼装上下文 → 引用来源**的完整链路，
> 并保证上传失败时 MinIO 与数据表一致、支持按文档增量更新、删除时三方一致。
> 目标是把参考项目 JavaLabAgent 的 RAG 能力平移到 Python 技术栈，**并做升级优化（不是原样照搬）**，同时沿用「框架能力优先、安全从第一天纳入」的方针。
> 本文档为设计方案，尚未落地；LangGraph Agent 与受控工具编排在第四阶段实现。

---

## 一、现状与本阶段目标

### 1.1 第二阶段已就绪（本阶段直接复用）

- 文件上传 / 分页 / 删除 / 下载到 MinIO，元数据落库（`KnowledgeService`、`StorageService`、`KbFile` 模型，表 `ali_oss_file`）。
- Chat 模型统一适配（`ModelProvider.get_chat_model` 路由 Ollama / OpenAI 兼容）。
- 对话 SSE 流式 + LangGraph 单节点 `chat_graph` + `AsyncPostgresSaver` 短期记忆（当前**纯直连模型，无检索**）。
- 数据库已 `CREATE EXTENSION vector`；`KbFile.vector_id` 字段已预留但未写入；`config.py` 已有 `ollama_embedding_model` 配置项但无代码引用。

### 1.2 本阶段实现

- 文档解析：PDF、Markdown、TXT 等格式统一解析为纯文本。
- 文档切分：QA 文档专用切分（保留完整问答对）+ 普通文档 Token 切分（可配置 chunk size / overlap）。
- Embedding 向量化：新增嵌入模型构建（`gte-large-zh`，维度可配），复用第二阶段的 provider 配置。
- 向量写入与切片索引：用 LangChain Indexing API（`index()` + `SQLRecordManager`）写入 pgvector，切片 id 由框架托管、内容不变的切片跳过。
- 向量检索 + 大模型 rerank：向量粗召回（topK 大）→ 大模型 rerank 精排（topN 小），阈值 / topK / rerank 参数从配置读取。
- 上下文拼装：用框架能力（`create_stuff_documents_chain` / `document_prompt`）拼装，替代手工字符串拼接。
- 引用来源：检索命中的来源（文件名 / 片段 / 分数）结构化返回给前端。
- RAG 对话：`chat_graph` 升级为 `retrieve → rerank → generate` 多节点检索图。
- 知识库维护：上传失败保证 MinIO 与数据表一致；按文档增量更新（不全量重建）；删除时同步清理 MinIO + DB + 向量。
- 20~50 条人工评测问题集与评测方法。

### 1.3 本阶段不实现（后续阶段）

- LangGraph 多节点 Agent 状态图与受控工具（第四阶段）。
- Skills 加载与注入（第四阶段）。
- 多模态、OSS、MCP 等（见第一阶段功能边界）。

> 接口契约保持稳定：`/api/v1/ai/rag` 仍是同一个对话入口，本阶段把它从「直连」升级为「检索增强」，前端无需改动契约。

---

## 二、技术选型与依赖

沿用第二阶段的「框架能力优先」方针：**凡是 langchain 生态已提供的解析 / 切分 / 向量库 / embedding 能力，一律优先使用，不自研**。

| 用途 | 选型 | 对应参考项目 |
| :--- | :--- | :--- |
| 文档解析 | `langchain-community` 的 loader（`PyPDFLoader` / `TextLoader` / `UnstructuredMarkdownLoader`），或统一走 `unstructured` | Spring AI `TikaDocumentReader` |
| 普通切分 | `langchain-text-splitters` 的 `RecursiveCharacterTextSplitter`（按 token 计数） | Spring AI `TokenTextSplitter` |
| QA 切分 | 自研 `QaDocumentSplitter`（保留完整问答对，贴合教学语料） | 参考项目 `QaDocumentSplitter`（同款自研） |
| Embedding | `langchain-ollama` 的 `OllamaEmbeddings`（`gte-large-zh`，维度可配） | Spring AI Ollama Embedding |
| 向量库 | `langchain-postgres` 的 `PGVector`（复用现有 PostgreSQL + pgvector） | `spring-ai-pgvector-store-starter` |
| 切片增量索引 | `langchain.indexes.index()` + `SQLRecordManager`（增量更新/去重，复用 PostgreSQL） | 无（参考项目全量重写） |
| rerank 精排 | `ContextualCompressionRetriever` + `LLMListwiseRerank`（大模型重排；备选 `CrossEncoderReranker`） | 无（参考项目仅术语过滤） |
| 上下文拼装 | `create_stuff_documents_chain` + `document_prompt` / `document_separator` | 手工字符串拼接 |
| Token 计数 | `tiktoken`（已作为 langchain-openai 传递依赖存在） | Spring AI 内置 |

**需新增依赖**（写入 `backend/pyproject.toml`）：`langchain`（含 indexes / chains / retrievers 能力）、`langchain-postgres`、`langchain-text-splitters`、`langchain-community`、`pypdf`（PDF）、`unstructured[md]` 或 `markdown`（Markdown）。embedding / rerank 复用 `langchain-ollama`、`langchain-openai` 已具备；`CrossEncoderReranker` 若启用需额外本地模型依赖。

> 落地约束：不确定某 loader / splitter / PGVector / Indexing API / rerank / chain 的 API 名称与用法时，先查 langchain 官方文档确认，**禁止臆测 API**。所有外部调用（Ollama embedding、pgvector、rerank）设置超时。

---

## 三、数据模型设计

### 3.1 向量表（PGVector 托管）

采用 `langchain-postgres` 的 `PGVector`，由框架自动建表管理，**不手写 ORM 模型**（对齐参考项目让 starter 托管 `vector_store` 表的做法）。

- PGVector 默认使用两张表：集合表 + 文档嵌入表（含 `embedding vector(N)`、`document`、`cmetadata jsonb`、`id`）。
- 向量维度 **N 可配置**（`rag_embedding_dim`，默认 1024）：嵌入模型可能更换，维度须与所选模型输出、PGVector collection 严格一致，否则写入报错。
- 使用固定 collection 名（如 `lab_agent_rag`），从配置读取。
- 距离度量用余弦距离，检索时按相似度分数过滤。

### 3.2 切片索引记录表（RecordManager 托管）

- 引入 LangChain Indexing API 后，`SQLRecordManager` 会在 PostgreSQL 建一张记录表，跟踪每个切片的 hash、`source_id`、写入时间，用于增量更新与去重（见第八章）。
- 该表同样由框架托管，**不手写 ORM**；命名空间（namespace）区分向量库与 collection。

> 说明：第二阶段 `alembic/0001_initial.py` 已 `CREATE EXTENSION vector`，PGVector 与 RecordManager 首次使用时可自动建其数据表；是否纳入 Alembic 版本管理见第九章落地约束。

### 3.3 KbFile 与来源标识

- **`source_id` 统一用 `kb_file.id`**（数据库主键，稳定、不重名）：作为 Indexing API 的 `source_id_key` 写入每个切片的 metadata，把"文档"与"其所有切片"关联起来，支撑按文档增量更新 / 删除。
- **`KbFile.vector_id` 字段废弃不用**：切片跟踪一律以 `RecordManager` 为准，不再回填 / 维护 `vector_id`。该字段保留在表结构里但不写入（避免改表），后续可在清理迁移时移除。

> 由于 `source_id = kb_file.id`，需先有 `kb_file` 记录（拿到 id）才能带着 `source_id` 做向量化，这会影响上传编排顺序，详见第八章 8.2。

### 3.4 chat_message.embedding

- 参考项目 `chat_message` 预留了 `embedding` 列，当前 LabAgent 的 `ChatMessage` 无此字段。**本阶段不新增**（消息级向量非 RAG 闭环必需，避免过度设计）。

---

## 四、文档解析设计

新增 `DocumentLoaderService`（或并入 `KnowledgeService`），职责：把上传的文件字节流按扩展名解析为 langchain `Document` 列表。

- 按扩展名路由 loader：`.pdf` → `PyPDFLoader`；`.md` → Markdown loader；`.txt` → `TextLoader`。或统一用 `unstructured` 自动识别（与参考项目 Tika 思路一致，减少分支）。
- 解析入口在上传流程内，接在文件校验之后、切分之前。
- 编码统一 UTF-8；解析失败抛业务异常并阻断后续入库（保证不产生「有文件无向量」的脏数据）。
- 扩展名白名单沿用第二阶段上传校验（pdf/md/txt），解析层与校验层白名单保持一致。

---

## 五、文档切分设计

切分入口 `split_documents(documents)`：先探测格式再分流（对齐参考项目 `splitDocuments`）。

### 5.1 格式探测

按内容是否含 `---` 分隔符与 `Q:` 问题前缀判定是否为 QA 语料。

- 命中 → QA 专用切分；否则 → 普通 Token 切分。
- 探测规则贴合教学 QA 语料的固定标识，仅用于 QA 语料。

### 5.2 QA 专用切分（自研 QaDocumentSplitter）

- 常量：分隔符 `---`、问题前缀 `Q:`、答案前缀 `A:`。
- 逻辑：按 `---` 切块 → 跳过空块 / 无 `Q:` 的标题块 → 解析出 question / answer → 每个 QA 对生成**一个不被打散的 chunk**。
- chunk 内容：`"问题: {question}\n\n答案: {answer}"`。
- metadata：继承原文档 + 写入 `qa_index`、`question`、`content_type=qa_pair`、`source`（文件名，供引用来源使用）。

### 5.3 普通 Token 切分

- 用 `RecursiveCharacterTextSplitter.from_tiktoken_encoder(chunk_size=..., chunk_overlap=...)`，按 token 计数切分。
- **参数从 Settings 读取**（不像参考项目写死默认值）：`rag_chunk_size`（默认建议 512）、`rag_chunk_overlap`（默认建议 100）。
- 每个 chunk 的 metadata 写入 `source`（文件名）便于引用。

---

## 六、Embedding 向量化设计

- `ModelProvider` 新增 `get_embedding_model()`：用 `OllamaEmbeddings(model=settings.ollama_embedding_model, base_url=settings.ollama_base_url)`，与 chat 模型共用 base_url / 超时配置。
- 向量维度可配（`rag_embedding_dim`），须与 PGVector collection 维度、所选嵌入模型输出严格一致（换模型时同步改配置与 collection）。
- 向量写入用 LangChain **Indexing API**：`index(docs, record_manager, vector_store, cleanup="incremental", source_id_key=...)`，框架自动 embedding、按 hash 去重、按 `source_id` 增量维护（见第八章），不再自己拼 `store_vectors` + 回填向量 id 列表。
- **上传编排与失败一致性**：解析 → 切分 → **向量化写入（`index()`，失败即抛异常，此时未产生 DB/MinIO 记录）** → MinIO 上传 → DB 落库。后置步骤失败时反向补偿（回滚向量 / MinIO），保证三方一致，详见第八章。

---

## 七、检索、重排与 RAG 对话设计

整体流程：**向量粗召回（topK 大）→ 大模型 rerank 精排（topN 小）→ 框架拼装上下文 → 生成**。检索、重排、拼装、生成尽量用 langchain / LangGraph 框架能力，不手写。

### 7.1 向量检索（粗召回）

新增 `RetrievalService`（或 `rag_support`）：

- 用 PGVector 的 retriever（`as_retriever(search_kwargs={"k": rag_top_k})`）或 `similarity_search_with_score(query, k)` 做粗召回，按分数初筛。
- **阈值 / topK 从 Settings 读取**：`rag_similarity_threshold`（默认建议 0.5，粗召回阶段放宽，把精排交给 rerank）、`rag_top_k`（默认建议 20，粗召回多召一些）。

### 7.2 大模型 rerank（精排，本阶段新增，优于参考项目）

参考项目只做了向量检索 + 术语过滤，没有 rerank。V2 引入重排，用**框架能力**实现，不手写：

- 用 langchain 的 `ContextualCompressionRetriever` 包裹基础向量 retriever，配一个压缩器（compressor）做重排：
  - 首选 **`LLMListwiseRerank`**（用大模型对候选文档做列表式重排，复用现有 `ModelProvider` 的 chat 模型，无需额外部署 rerank 服务，最贴合"调用大模型进行 rerank"的诉求）。
  - 备选 `CrossEncoderReranker`（本地交叉编码器，若后续要省 LLM 调用成本可切换）。
- rerank 后取前 `rag_rerank_top_n`（默认建议 5）条作为最终上下文。
- **粗召回 topK（20）大、精排 top_n（5）小**：先多召回保证覆盖，再让大模型精排提升相关性、压掉噪声，降低幻觉。
- rerank 用的模型与是否启用均从 Settings 读取（`rag_rerank_enabled`、`rag_rerank_top_n`、`rag_rerank_model`）；关闭时退化为纯向量检索。

### 7.3 拼装上下文（改用框架能力，不手写拼接）

参考项目手工 `\n\n` 拼接知识块并做字符串占位替换。V2 改用 langchain 内置的文档合并能力：

- 用 **`create_stuff_documents_chain`**：传入 `ChatPromptTemplate`（含 `{context}` 占位）与 chat 模型，框架自动把检索到的 `Document` 列表按模板塞进 prompt，无需手写拼接。
- 用 **`document_prompt`**（`PromptTemplate`）定义每条文档如何渲染（如带上 `source` 文件名），用 **`document_separator`** 定义多文档分隔符——来源信息由框架按 metadata 注入，替代手写字符串。
- 检索 + 拼装可用 **`create_retrieval_chain`** 串起来（retriever → stuff documents chain），但因本阶段要 SSE 流式且要与 LangGraph checkpointer 记忆协同，实际在 LangGraph 图内组合这些组件（见 7.5），而非直接用 `create_retrieval_chain` 的一体化封装。

### 7.4 引用来源

- 把最终（rerank 后）文档的 `source`（文件名）、片段摘要、相似度 / 重排分数收集为结构化 `sources` 列表，通过 SSE 专门事件（`event_type=sources`）或 `final` 事件 payload 回传前端展示「引用来源」。全字段蛇形（`file_name` / `score` / `snippet`）。
- **来源展示替代了参考项目的 `【根据知识库】/【根据通用知识】` 回答前缀**：既然有结构化来源，前端能直接呈现引用出处，无需再让模型在正文加前缀标签，正文更干净。系统提示词不再要求模型输出该类前缀。

### 7.5 chat_graph 插入检索与重排节点

当前图：`START → chat → END`（单节点直连）。本阶段升级为多节点检索图：

```
START → retrieve → rerank → generate → END
```

- `retrieve` 节点：取用户最新问题做向量粗召回，命中结果写入图 state。
- `rerank` 节点：用 `ContextualCompressionRetriever` / `LLMListwiseRerank` 对候选精排，取 top_n 写回 state；`rag_rerank_enabled=false` 时该节点直通。
- `generate` 节点：用 `create_stuff_documents_chain` 把 rerank 后的文档拼进 prompt，配合 `trim_messages` 裁剪历史 + 系统提示词 → 流式生成。
- 短期记忆仍由 `AsyncPostgresSaver` checkpointer 管理（`thread_id` = 会话 id），检索只针对当前问题、不污染记忆状态。
- 模型选择兜底沿用第二阶段：外部模型失败回退本地 Ollama。

> `/api/v1/ai/rag` 走检索增强图；`/api/v1/ai/react-agent` 仍留第四阶段。`ai_service.stream_chat` 编排不变，仅底层图从单节点换成检索图。

---

## 八、知识库维护（上传一致性、增量更新、删除一致性）

知识库不是一次性写入，而是长期要**更新、替换、删除**的。本章覆盖三件事：上传失败时的一致性、文档/切片的增量更新、删除时的三方一致性。核心思路是**尽量用 LangChain 官方 Indexing API 管理切片，不自己维护切片 id**。

### 8.1 切片管理：Indexing API + 以文档为维护单位

维护的**最小单位是「文档」**（不做切片级手动编辑）。切片的产生、id、增量全部交给 LangChain 官方 Indexing API，不自己维护切片 id：

- **LangChain Indexing API**（`langchain.indexes.index()` + `SQLRecordManager`，复用现有 PostgreSQL）：
  - `RecordManager` 为每个切片记录"指纹"：切片 hash（内容+metadata）、`source_id`、写入时间。
  - `index()` 写入时对每个切片算 hash：**内容没变的切片跳过（不重复 embedding、不重写）**，变了的才重新写。
  - 切片 id 由框架托管，我们只需给每个切片打上 **`source_id = kb_file.id`**。
- **更新一个文档**（`cleanup="incremental"` + `source_id_key`）：重新解析+切分该文档 → `index()` 只重写变化切片、删除该 `source_id` 下已不存在的旧切片、保留未变切片。**只动这一个文档的切片，不全量重建**。
- **不暴露"改单个切片"的接口**：切片级差异由 hash 自动处理，教学场景以文档为单位足够，避免过度设计。
- `cleanup` 模式：更新单个文档用 `incremental`；整库重建用 `full`；仅去重用 `None`。

### 8.2 上传编排与失败一致性

因为 `source_id = kb_file.id`，**必须先有 `kb_file` 记录拿到 id，才能带着 `source_id` 向量化**。编排顺序：

1. 文件校验（扩展名 / 大小 / 文件名净化）。
2. **写 `kb_file` DB 记录**（拿到自增 `id`，`url` 暂空或占位）。
3. 解析 → 切分 → **向量化 `index(docs, cleanup="incremental", source_id_key=kb_file.id)`**。
4. 上传 MinIO。
5. 回填 `kb_file.url`。

失败补偿（保证 MinIO 对象、DB 记录、向量三方一致）：

- 向量化失败：删除步骤 2 刚建的 `kb_file` 记录 → 天然一致（还没传 MinIO）。
- MinIO 上传失败：按 `source_id` 清理已写向量 + 删除 `kb_file` 记录。
- 回填 url 失败：回滚 MinIO 对象 + 向量 + `kb_file` 记录。
- 所有回滚失败项记录告警日志，便于后台巡检补偿。

> 相比参考项目"先向量化，失败即抛异常阻断后续"，V2 覆盖后置步骤失败的反向补偿，真正做到 MinIO 与数据表一致。

### 8.3 更新一个文档（回应"用户拿不到 source_id 怎么判断同一文档"）

关键点：**判断"是不是同一个文档"不靠内容猜测，而是靠用户在前端明确选中的那条记录的 `kb_file.id`**。前端的知识库列表本来就展示每条文件记录（含 `id`），更新是"针对某条已存在记录的操作"，前端把该记录的 `id` 传回来即可——用户不需要理解 source_id，它就是列表里那一行对应的主键。

因此更新走**独立更新接口**，而非"复用上传接口靠系统自动识别同一文档"（那样无法可靠判断）：

- 接口：`POST /api/v1/knowledge/file/update`，入参 = `kb_file_id`（必传，前端从列表行取）+ 新文件。
- 流程：按 `kb_file_id` 查到记录 → 解析+切分新文件 → `index(新切片, cleanup="incremental", source_id_key=该 kb_file_id)`（框架自动只改变化切片、清理旧切片）→ 替换 MinIO 对象 → 更新 `kb_file` 元数据（文件名 / url / update_time）。
- `source_id` 全程 = 这条记录的 `kb_file.id`，所以新旧切片天然归属同一文档，实现"只更新这一个文档、不全量重建"。
- 失败补偿同 8.2 思路（向量 / MinIO / DB 保持一致）。

> 说明：普通"重新上传同名文件"仍走上传接口，会创建**新记录 + 新 `kb_file.id`**（即新增一个文档），不会覆盖旧的。要"更新已有文档"必须走带 `kb_file_id` 的更新接口。

### 8.4 删除一致性

扩展 `KnowledgeService.delete_files(ids)`：

1. 空 `ids` 判空**前置**（参考项目把判空放在查询之后，V2 前置）。
2. 查出待删 `KbFile` 记录（`id` 即 `source_id`、`url`）。
3. 删向量：按 `source_id = kb_file.id` 调 Indexing API / `PGVector.delete`（不再依赖已废弃的 `vector_id`）。
4. 删 MinIO 对象：从 `url` 提取 object_name → `storage_service.delete`。
5. 删 DB 记录。

**改进点**（参考项目问题）：参考项目在 DB 事务里删向量 / MinIO，一旦 MinIO 已删却回滚 DB 会不一致。V2 建议**先删外部资源（向量、MinIO）再删 DB 记录**，外部删除失败做日志告警 + 记录失败项，避免残留 DB 记录指向已删对象；补偿清理作为可选增强。

---

## 九、配置项（新增到 Settings / .env）

| 配置项 | 环境变量 | 默认建议 | 说明 |
| :--- | :--- | :--- | :--- |
| `ollama_embedding_model` | `OLLAMA_EMBEDDING_MODEL` | `turingdance/gte-large-zh:latest` | 已存在，本阶段开始被引用 |
| `rag_collection_name` | `RAG_COLLECTION_NAME` | `lab_agent_rag` | PGVector collection 名 |
| `rag_embedding_dim` | `RAG_EMBEDDING_DIM` | `1024` | 向量维度，**可配置**（嵌入模型可能更换，须与所选模型输出维度、PGVector collection 严格一致） |
| `rag_chunk_size` | `RAG_CHUNK_SIZE` | `512` | 普通切分 token 数 |
| `rag_chunk_overlap` | `RAG_CHUNK_OVERLAP` | `100` | 切分重叠 token 数 |
| `rag_top_k` | `RAG_TOP_K` | `20` | 向量粗召回条数（多召回，交给 rerank 精排） |
| `rag_similarity_threshold` | `RAG_SIMILARITY_THRESHOLD` | `0.5` | 粗召回相似度阈值（放宽，精排把关） |
| `rag_rerank_enabled` | `RAG_RERANK_ENABLED` | `true` | 大模型 rerank 精排开关，关闭时退化为纯向量检索 |
| `rag_rerank_top_n` | `RAG_RERANK_TOP_N` | `5` | rerank 后保留的最终上下文条数 |
| `rag_rerank_model` | `RAG_RERANK_MODEL` | （复用 chat 模型） | 用于 LLM rerank 的模型名 |

> 沿用第二阶段：配置全部走 `Settings` / 环境变量（`@lru_cache` 单例），改 `.env` 后重启生效；禁止硬编码。

落地约束：

- PGVector 数据表创建方式二选一——A. 首次运行时 PGVector 自动建表；B. 纳入 Alembic 版本管理。建议 A（框架托管）+ 在文档注明，避免与 langchain 内部 schema 冲突。
- embedding 输出维度、PGVector collection 维度、`.env` `RAG_EMBEDDING_DIM` 三者必须一致。

---

## 十、API 契约（本阶段变更）

沿用第二阶段接口，本阶段的变更**都不破坏契约**：

- `/api/v1/knowledge/file/upload`：内部从「存文件」升级为「解析→切分→向量化(index)→存文件」，失败反向补偿保证一致，返回结构不变。
- `/api/v1/knowledge/delete`：内部增加向量 + MinIO 三方清理，返回结构不变。
- 知识库**更新**：新增独立接口 `POST /api/v1/knowledge/file/update`，入参 = `kb_file_id`（必传，前端从知识库列表行取）+ 新文件；语义是"按 `kb_file.id` 定位文档做增量更新，不全量重建"。判断"同一文档"靠前端选中记录的 `kb_file.id`，不靠系统内容猜测（详见 8.3）。
- `/api/v1/ai/rag`：内部从「直连」升级为「检索 + rerank + 生成」，SSE 事件在原有 `token`/`final`/`error` 基础上**新增可选 `sources` 事件**（引用来源，全蛇形字段）。
- 新增 schema：检索来源 VO（`file_name`、`snippet`、`score`），并入 SSE payload。

> 所有请求 / 响应 / SSE 字段遵循全蛇形零转换约定（见 AGENTS.md）。

### 10.1 前端适配点（本阶段需改前端）

对话主链路（`/api/v1/ai/rag`、上传 / 删除接口的入参与返回结构）不破坏契约，前端无需改；但以下两处是本阶段**新增能力**，前端当前尚未适配，需要落地时补上：

| 前端改动 | 涉及文件（现状） | 说明 |
| :--- | :--- | :--- |
| **知识库「更新文档」入口** | [api/knowledge.js](file:///Users/bytedance/learnAgent/LabAgent/frontend/src/api/knowledge.js)、[KnowledgeManagement.vue](file:///Users/bytedance/learnAgent/LabAgent/frontend/src/views/KnowledgeManagement.vue) | 当前只有上传 / 删除 / 下载，**没有更新**。需：① `knowledgeApi` 新增 `updateFile(kb_file_id, formData)` 调 `POST /v1/knowledge/file/update`（`multipart/form-data`，表单带 `kb_file_id` + 新文件）；② 文件卡片新增「更新」按钮，点击选文件后带**该行的 `file.id`** 传回。用户只需在列表里选中那条记录点更新，无需理解 `source_id`。 |
| **引用来源展示** | [api/chat.js](file:///Users/bytedance/learnAgent/LabAgent/frontend/src/api/chat.js)、[ChatInput.vue](file:///Users/bytedance/learnAgent/LabAgent/frontend/src/components/ChatInput.vue) | 当前 SSE 已处理 `session`/`token`/`tool_call`/`tool_result`/`status`/`skill_loaded`/`error`/`final`，**未处理 `sources`**。需在 `handleStreamEvent` 增加 `event_type === 'sources'` 分支，把 `payload` 里的来源列表（`file_name`/`snippet`/`score`，全蛇形）挂到当前助手消息上，并在消息组件里渲染「引用来源」。 |

> 说明：上传按钮的 `accept` 当前含 `.doc/.docx`，而后端白名单为 `pdf/md/markdown/txt`，落地时前端 `accept` 与后端白名单需对齐（去掉 doc/docx）。

---

## 十一、人工评测设计（20~50 条）

- 覆盖三类核心演示问题（第一阶段）：实验提交 / 报告要求、Java 报错（如空指针）、平台操作指引。
- 评测集组织：问题 + 期望要点 + 期望命中的来源文档 / QA。
- 评测维度：
  - 召回：应命中的问题是否检索到正确 QA / 文档片段。
  - rerank 效果：精排后 top_n 的相关性是否优于纯向量粗召回。
  - 准确：回答是否包含期望要点、引用来源是否正确。
  - 误召回：语义相近但不相关的问题是否被 rerank 挡住。
- 评测方式：人工逐条跑对话接口，记录命中来源与答案，形成基线；用于调 `rag_similarity_threshold` / `rag_top_k` / `rag_rerank_top_n` / `rag_chunk_size`。
- 评测语料与问题集放 `backend/` 或 `docs/` 下的评测文件（落地阶段确定路径），不写死在代码。

---

## 十二、会话用户隔离（安全加固）

> 本节回应"会话没有做用户基本的隔离"的排查。结论是：**Web 层（API / Service / Repository）的会话隔离已完备**，真正薄弱的是 **LangGraph checkpointer（会话记忆）层缺少用户维度、仅靠单点业务校验兜底**。本节沉淀现状核查、风险点与加固方案。

### 12.1 现状核查（已隔离的部分）

会话数据模型与全链路访问都带用户归属：

- 模型：[chat_session.py](file:///Users/bytedance/learnAgent/LabAgent/backend/app/models/chat_session.py) 有 `user_id`（当前 `nullable=True`）；[chat_message.py](file:///Users/bytedance/learnAgent/LabAgent/backend/app/models/chat_message.py) 有 `user_id`（`nullable=False`）。
- 接口：[ai.py](file:///Users/bytedance/learnAgent/LabAgent/backend/app/api/v1/ai.py) 的 5 个会话接口（rag / react-agent / history / sessions / sessions/delete）全部注入 `CurrentUser`，`user_id` 一律取自 JWT。
- 请求体 `user_id` 被忽略：[chat.py](file:///Users/bytedance/learnAgent/LabAgent/backend/app/schemas/chat.py) 的 `ChatRequest` 不含 `user_id` 字段，以 JWT 为准（符合 AGENTS.md「禁止相信请求体 userId」）。
- 归属校验（关键闸门）：
  - [session_service.py](file:///Users/bytedance/learnAgent/LabAgent/backend/app/services/session_service.py#L38-L43) `get_or_create_session` 命中已有会话时校验 `existing.user_id != user_id` → 抛 `NO_AUTH_ERROR`。
  - [message_service.py](file:///Users/bytedance/learnAgent/LabAgent/backend/app/services/message_service.py) `get_messages_by_session` 先校验会话归属再取消息。
  - Repository 层 `list_by_user` / `logical_delete` 均带 `WHERE user_id = :user_id` 过滤。

> 即：用户 A 无法通过任何 Web 接口查看 / 删除 / 续聊用户 B 的会话——只要请求进入了这些 Service 方法，就会被归属校验挡住。

### 12.2 风险点

1. **checkpointer 层无用户维度（主要隐患）**：[ai_service.py](file:///Users/bytedance/learnAgent/LabAgent/backend/app/services/ai_service.py#L53-L58) 里 `thread_id = str(session_id)`，即 **thread_id 直接等于会话 UUID，不含 user_id**；[checkpointer.py](file:///Users/bytedance/learnAgent/LabAgent/backend/app/graph/checkpointer.py) 的 `AsyncPostgresSaver` 建的 `checkpoints` 表以 `thread_id` 为键、**没有 user_id 列**。当前唯一防线是进入图之前 `get_or_create_session` 的归属校验，属**单点依赖**：将来任何新增的、直接拿外部 `thread_id` 调 `graph.astream` 的入口若漏掉归属校验，即可恢复他人会话的记忆上下文。
2. **`chat_session.user_id` 允许为 NULL**：与「会话必须归属用户」的安全目标不一致；当前创建路径总会写入 user_id，实际风险低，属字段定义卫生问题。
3. **前端遗留 `userId = 1` 默认值与请求体 `user_id`**：[chat.js](file:///Users/bytedance/learnAgent/LabAgent/frontend/src/api/chat.js)、[stores/chat.js](file:///Users/bytedance/learnAgent/LabAgent/frontend/src/stores/chat.js) 中大量 `userInfo?.id || 1` 与请求体 `user_id`。后端已忽略、不构成越权，但是误导性遗留代码，让人误以为隔离依赖前端传参。

### 12.3 加固方案（纵深防御）

> **有现成框架能力可用，无需自研**：LangGraph checkpointer 的隔离键是 `(thread_id, checkpoint_ns, checkpoint_id)`，其中 `thread_id` 与 `checkpoint_ns`（命名空间）都是框架原生的隔离维度——**会话隔离用的正是 `thread_id`**。用户隔离只需复用同源能力：把 `user_id` 编码进 `thread_id`（或用 `checkpoint_ns` 命名空间承载 `user_id`），与会话隔离一脉相承。

按优先级、最小改动排序：

1. **thread_id 绑定 user_id（推荐，核心加固，复用框架能力）**：把 `thread_id` 从 `str(session_id)` 改为 `f"{user_id}:{session_id}"`，让 checkpointer 记忆天然按「用户 + 会话」双键隔离，即使拿到他人 `session_id` 也凑不出正确 thread_id，与业务校验形成双保险。这不是新增机制，而是沿用会话隔离所依赖的同一套 `thread_id` 框架能力。
   - 权衡：thread_id 格式变更后，**旧会话在 checkpointer 中的历史记忆会「断档」**（业务表 `chat_message` 消息不受影响，仍可展示）。因当前处于开发阶段、无重要线上记忆，代价可接受；如需保留可清空 checkpoints 表重来。
   - 落地点：仅 [ai_service.py](file:///Users/bytedance/learnAgent/LabAgent/backend/app/services/ai_service.py#L53-L58) 一处 `config` 构造，改动面小。
2. **`chat_session.user_id` 收紧为 `nullable=False`**：模型改 + 一条 Alembic 迁移；确保历史数据无 NULL 后再收紧。
3. **清理前端 `userId = 1` 遗留**：移除请求体 `user_id` 与 `|| 1` 兜底，隔离完全以 JWT 为准（纯代码卫生，不影响功能）。

> 落地约束：以上为设计沉淀。thread_id 绑定属安全增强，建议优先落地；后两项为卫生优化，可随后处理。改动须遵循最小改动原则，不触碰无关代码。

---

## 十三、验收标准

- 上传 PDF / Markdown / TXT 能被解析、切分、向量化并写入 pgvector，切片由 Indexing API 托管。
- QA 语料按问答对切分（每对一个 chunk），普通文档按配置的 chunk_size / overlap 切分。
- `/api/v1/ai/rag` 能向量召回 + 大模型 rerank 精排，回答体现知识库内容，SSE 返回结构化 `sources`。
- 阈值 / topK / rerank / chunk / 维度参数全部可通过 `.env` 配置并生效。
- 更新一个文档时按 `source_id` 增量更新（只重写变化切片、清理旧切片），不全量重建。
- 上传中途失败（如向量化 / MinIO / DB）后，MinIO 与数据表、向量三方保持一致，无残留脏数据。
- 删除知识库文件后，MinIO 对象、DB 记录、pgvector 向量三方均被清理，无残留。
- 向量维度全链路一致（模型 = collection = 配置）。
- 20~50 条评测问题跑通并形成基线记录。
- 安全基线延续第二阶段：上传校验、请求体 `userId` 忽略、外部调用超时、日志不打敏感信息。

---

## 十四、本阶段结论

- 本阶段在第二阶段的文件存储与对话直连之上，补齐 RAG 完整闭环，坚持「解析 / 切分 / 向量库 / embedding / 增量索引 / rerank / 上下文拼装用 langchain 生态框架能力，QA 切分与教学业务逻辑自研」的分工。
- **这是一次带升级优化的迁移，而非把参考项目功能原样照搬**。相较参考项目的升级点：切分参数与向量维度可配置、引入大模型 rerank 精排、上下文拼装改用框架能力、引入 Indexing API 支持切片级增量更新、引用来源结构化回传前端（去掉 `【根据知识库】` 前缀标注）、上传失败反向补偿与删除失败边界优化。
- 对话主链路契约保持稳定，前端从直连升级为检索增强无需改动；但**新增的「知识库更新」入口与「引用来源」展示前端尚未适配，需按 10.1 补上**。
- 本文档为设计方案，尚未落地；LangGraph Agent 与受控工具编排见第四阶段。