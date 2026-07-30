# @author: caoshuai.cs
# @date: 2026-07-12
# @description: LabAgent 后端镜像，基于 uv 安装依赖，启动前执行 alembic 迁移
FROM python:3.12-slim

ARG PYPI_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_INDEX_URL=${PYPI_INDEX_URL} \
    UV_DEFAULT_INDEX=${PYPI_INDEX_URL} \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken_cache

WORKDIR /app

# 安装 uv
RUN pip install --no-cache-dir uv

# 先拷贝依赖清单以利用缓存
COPY pyproject.toml uv.lock ./
RUN uv venv && uv export --no-dev --no-emit-project --no-hashes --format requirements-txt | uv pip install -r -
RUN mkdir -p "${TIKTOKEN_CACHE_DIR}" \
    && .venv/bin/python -c "import tiktoken; tiktoken.get_encoding('o200k_base')"

# 拷贝源码
COPY app ./app
COPY skills ./skills
COPY tool_runner ./tool_runner
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

EXPOSE 8989

# 启动前执行迁移，再拉起服务
CMD ["sh", "-c", "uv run --no-sync --no-dev alembic upgrade head && uv run --no-sync --no-dev uvicorn app.main:app --host 0.0.0.0 --port 8989"]
