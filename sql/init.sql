-- @author: caoshuai.cs
-- @date: 2026-07-12
-- @description: PostgreSQL 初始化脚本，仅创建扩展；表结构由 Alembic 迁移管理
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS hstore;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
