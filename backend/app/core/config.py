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
    openai_api_key: str = ""
    openai_base_url: str = "https://aistudio.baidu.com/llm/lmapi/v3"
    openai_chat_model: str = "ernie-4.5-turbo-128k-preview"

    # 对话记忆窗口（用于 trim_messages 的最大消息条数）
    memory_max_messages: int = 20

    # 文件上传校验
    upload_max_size_mb: int = 100
    upload_allowed_extensions: str = "pdf,md,markdown,txt"

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
    def allowed_extension_set(self) -> set[str]:
        """允许上传的扩展名集合（小写，不含点）。"""
        return {ext.strip().lower() for ext in self.upload_allowed_extensions.split(",") if ext.strip()}


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例。"""
    return Settings()


settings = get_settings()
