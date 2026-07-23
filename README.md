# LabAgent

面向高校实验教学的智能学习与教学辅助 Agent，提供课程知识问答、实验指导、代码排查和知识库检索能力。

![LabAgent 首页演示](docs/images/labagent-readme-gif.gif)

![LabAgent 对话工作流](docs/images/labagent-chat-workflow.png)


## 核心能力

- **Agentic RAG**：由 Agent 自主检索课程知识库，结合向量与 BM25 混合召回生成带来源的回答。
- **工具调用**：支持文件读写、内容搜索等受控工具，高风险操作需用户确认。
- **Skills 扩展**：通过 Markdown Skills 扩展 Agent 的任务处理能力。
- **多模型接入**：支持 Ollama 本地模型和 OpenAI 兼容接口。
- **完整应用体验**：包含用户认证、会话管理、流式输出、知识库管理和响应式 Web 界面。

## 技术栈

FastAPI · LangGraph · Vue 3 · PostgreSQL + pgvector · MinIO · Docker Compose

## 快速开始

环境要求：Python 3.12、Node.js 20.19+、Docker 和 [uv](https://docs.astral.sh/uv/)。

### 本地开发

1. 准备配置并启动 PostgreSQL 与 MinIO：

```bash
cp .env.example backend/.env
docker compose up -d postgres minio
```

2. 启动后端：

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8989 --reload
```

3. 新开终端并启动前端：

```bash
cd frontend
npm install
npm run dev
```

根据终端提示访问前端页面，API 文档位于 `http://localhost:8989/docs`。

### Docker 部署

```bash
cp .env.example backend/.env
docker compose up -d --build
```

访问 `http://localhost:8080`。使用宿主机 Ollama 时，将 `backend/.env` 中的 `OLLAMA_BASE_URL` 设置为 `http://host.docker.internal:11434`。
如果 Docker 构建下载 Python 依赖超时，可在项目根目录 `.env` 中把 `PYPI_INDEX_URL` 改为可访问的内网 PyPI 镜像。

## 配置

完整配置见 [.env.example](.env.example)。部署前至少需要确认模型配置，并替换 `JWT_SECRET_KEY` 等默认敏感值。

Shell 工具默认关闭。启用时需同时设置 `SHELL_TOOL_ENABLED=true` 和高强度 `TOOL_RUNNER_TOKEN`，并仅向可信管理员开放。

## 文档

- [产品与架构设计](docs/01-产品与架构设计.md)
- [RAG 全流程](docs/04-RAG全流程实现与理解.md)
- [Agent 工具调用](docs/07-Agent工具调用流程与实现理解.md)
