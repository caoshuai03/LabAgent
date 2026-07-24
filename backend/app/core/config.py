"""
@author: caoshuai.cs
@date: 2026-07-12
@description: 应用配置，统一从环境变量读取，禁止硬编码密钥/地址
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置项，全部来自环境变量或 .env 文件。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 应用
    app_name: str = "LabAgent"
    api_version: str = "/api/v1"
    server_port: int = 8989

    # 数据库（异步 SQLAlchemy 使用 asyncpg 驱动）
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "admin"
    postgres_db: str = "postgres"

    # JWT
    jwt_secret_key: str = "change-me-in-env"
    jwt_ttl_seconds: int = 86400
    jwt_algorithm: str = "HS256"

    # MinIO 对象存储
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_bucket: str = "labagent"
    minio_secure: bool = False

    # 模型服务
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen3:8b"
    ollama_embedding_model: str = "turingdance/gte-large-zh:latest"
    # 嵌入模型请求超时（秒）：Ollama 不可达时快速失败以触发检索降级，避免拖死整个对话
    ollama_embedding_timeout: int = 120
    # 评测裁判模型请求超时（秒）：RAGAS 结构化判断比普通聊天更慢，需单独放宽
    ollama_judge_timeout: int = 120
    openai_api_key: str = ""
    openai_base_url: str = "https://aistudio.baidu.com/llm/lmapi/v3"
    openai_chat_model: str = "ernie-4.5-turbo-128k-preview"

    # Azure OpenAI 网关（字节 aidp modelhub）
    azure_api_key: str = ""
    azure_api_version: str = "2024-03-01-preview"
    azure_endpoint: str = "https://aidp.bytedance.net/api/modelhub/online/v2/crawl"
    azure_chat_model: str = "gpt-5.5-2026-04-24"
    # 链路追踪 logid（X-TT-LOGID）；留空则每次构造时自动生成
    azure_logid: str = ""

    # 对话记忆窗口（用于 trim_messages 的最大消息条数）
    memory_max_messages: int = 20
    # 新会话标题生成：失败或超时时自动保留首条消息截断标题
    conversation_title_enabled: bool = True
    conversation_title_model: str = ""
    conversation_title_timeout_seconds: int = 8
    conversation_title_max_chars: int = 30
    conversation_title_assistant_context_chars: int = 500

    # 文件上传校验
    upload_max_size_mb: int = 100
    upload_allowed_extensions: str = "pdf,md,markdown,txt"

    # RAG 检索增强
    rag_collection_name: str = "lab_agent_rag"
    rag_embedding_dim: int = 1024
    rag_chunk_size: int = 512
    rag_chunk_overlap: int = 100
    rag_top_k: int = 20
    rag_similarity_threshold: float = 0.5
    rag_query_rewrite_model: str = ""
    rag_rerank_enabled: bool = True
    rag_rerank_top_n: int = 5
    rag_rerank_model: str = ""
    # rerank 只需输出文档 ID 排序，限制本地模型输出长度以避免无意义长思考
    rag_rerank_num_predict: int = 64
    # rerank 单次调用总超时（秒），避免模型持续生成导致工具长期无结果
    rag_rerank_timeout_seconds: int = 30
    # 混合检索：BM25 关键词召回条数（与向量召回一同进入 RRF 融合）
    rag_bm25_top_k: int = 20

    # Agent 工具
    agent_tools_enabled: bool = True
    file_tools_enabled: bool = True
    shell_tool_enabled: bool = False
    shell_delete_require_approval: bool = True
    file_write_require_approval: bool = False
    tool_workspace_root: str = "./data/tool-workspaces"
    tool_max_write_chars: int = 24000
    tool_max_output_chars: int = 12000
    tool_timeout_seconds: int = 60
    shell_timeout_seconds: int = 20
    agent_timeout_seconds: int = 180
    agent_max_tool_rounds: int = 50
    # 同一工具+同参数在单次 Agent 运行内的最大重复调用次数，超过即拒绝该调用
    agent_duplicate_tool_call_limit: int = 3
    tool_runner_base_url: str = "http://tool-runner:8990"
    tool_runner_token: str = ""

    @property
    def database_url(self) -> str:
        """异步数据库连接串。"""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        """同步数据库连接串（用于 LangGraph PostgresSaver 的 psycopg 连接池）。"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def alembic_database_url(self) -> str:
        """Alembic 迁移使用的同步连接串（显式指定 psycopg v3 驱动）。"""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def vector_database_url(self) -> str:
        """PGVector/SQLRecordManager 使用的同步连接串。

        走 SQLAlchemy create_engine，须显式指定 psycopg v3 方言，
        否则会回退到未安装的 psycopg2 默认驱动。
        """
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def allowed_extension_set(self) -> set[str]:
        """允许上传的扩展名集合（小写，不含点）。"""
        return {ext.strip().lower() for ext in self.upload_allowed_extensions.split(",") if ext.strip()}


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例。"""
    return Settings()


settings = get_settings()
