# LabAgent

面向高校实验教学场景的智能学习与教学辅助 Agent。参考项目 JavaLabAgent（Spring Boot + Spring AI + Vue3）迁移到 Python 技术栈实现。

## 技术栈

- 后端：FastAPI + Uvicorn、SQLAlchemy 2.0 (async) + asyncpg、Alembic、LangGraph（StateGraph / ToolNode）、LangChain Tools、Pydantic v2
- 前端：Vue 3 + Vue Router + Pinia + Vite + axios
- 中间件：PostgreSQL (pgvector)、MinIO
- 模型：Ollama（本地）/ OpenAI 兼容接口

## 目录结构

```
LabAgent/
├── backend/            # FastAPI 后端
│   ├── app/            # 应用代码（api / core / db / graph / models / repositories / schemas / services）
│   ├── alembic/        # 数据库迁移
│   ├── tool_runner/     # Shell 工具内部沙箱执行服务
│   └── pyproject.toml
├── frontend/           # Vue3 前端
├── sql/init.sql        # PostgreSQL 扩展初始化（表结构由 Alembic 管理）
├── docs/               # 产品与设计文档
├── docker-compose.yml  # 中间件 + 后端 + 前端 + 内部 Tool Runner 编排
└── AGENTS.md           # 开发规范
```

## 环境要求

- Python 3.12
- Node.js >= 20.19（或 >= 22.12）
- Docker（用于启动 PostgreSQL 与 MinIO）
- [uv](https://github.com/astral-sh/uv)（Python 包与虚拟环境管理）

## 快速开始（本地开发模式）

推荐姿势：**中间件用 Docker，前后端在本地直接跑**，便于热更新与调试。

### 1. 启动依赖中间件（PostgreSQL + MinIO）

只启动这两个中间件服务：

```bash
cd LabAgent
docker compose up -d postgres minio
```

- PostgreSQL：`localhost:5432`（首次启动自动执行 `sql/init.sql` 创建 pgvector 等扩展）
- MinIO：API `localhost:9000`，控制台 `localhost:9001`

### 2. 启动后端

```bash
cd LabAgent/backend

# 安装依赖（首次）
uv sync

# 执行数据库迁移（首次或有新迁移时）
uv run alembic upgrade head

# 启动服务（默认 8989 端口）
uv run uvicorn app.main:app --host 0.0.0.0 --port 8989 --reload
```

后端配置读取 `backend/.env`（可参考根目录 `.env.example`）。接口前缀为 `/api/v1`，如登录接口为 `POST /api/v1/user/login`。

### 3. 启动前端

```bash
cd LabAgent/frontend

# 安装依赖（首次）
npm install

# 启动开发服务器（Vite）
npm run dev
```

前端通过 Vite proxy 将 `/api` 请求转发到 `http://localhost:8989`，无需额外配置跨域。启动后按终端提示的地址访问即可。

## 一键容器化部署（可选）

若需将后端、前端也一起容器化运行：

```bash
cd LabAgent
docker compose up -d --build
```

- 前端：`http://localhost:8080`
- 后端：`http://localhost:8989`
- Tool Runner：仅连接 Docker 内部网络，不暴露宿主机端口
- 使用 Ollama 时，容器内通过 `http://host.docker.internal:11434` 访问宿主机模型服务

## 配置说明

环境变量参考根目录 [.env.example](.env.example)，主要包含：数据库连接、JWT 密钥、MinIO 连接、模型服务（Ollama / OpenAI 兼容）、对话记忆窗口、文件上传限制、Agent 工具开关、工作区限制、执行超时和 Tool Runner 认证等。生产环境务必替换 `JWT_SECRET_KEY`、`TOOL_RUNNER_TOKEN` 等敏感项。

文件工具通过会话独立工作区运行。Shell 工具已完成链路集成但默认关闭；启用时必须配置 `SHELL_TOOL_ENABLED=true` 和非默认的 `TOOL_RUNNER_TOKEN`，并保留独立 Tool Runner 沙箱与角色权限。普通命令直接执行，文件删除和 Shell 删除类命令在助手消息内请求用户确认。

## 约定

- 前后端 API 契约统一使用蛇形命名（snake_case），前后端零命名转换。
- 所有接口统一用 `BaseResponse[T]` 包装返回（`{code, data, message}`，成功 code=0），SSE 流式接口除外。
- 详细开发规范见 [AGENTS.md](AGENTS.md)。

> 本 README 为初版，后续会持续完善。
