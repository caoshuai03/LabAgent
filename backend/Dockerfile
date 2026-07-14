# @author: caoshuai.cs
# @date: 2026-07-12
# @description: LabAgent 后端镜像，基于 uv 安装依赖，启动前执行 alembic 迁移
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 安装 uv
RUN pip install --no-cache-dir uv

# 先拷贝依赖清单以利用缓存
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 拷贝源码
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

EXPOSE 8989

# 启动前执行迁移，再拉起服务
CMD ["sh", "-c", "uv run --no-dev alembic upgrade head && uv run --no-dev uvicorn app.main:app --host 0.0.0.0 --port 8989"]
