#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/bytedance/learnAgent/LabAgent"
SERVER="cs@172.29.7.233"
REMOTE_DIR="/home/cs/labagent"
REMOTE_DEPLOY_DIR="${REMOTE_DIR}/labagent-offline"
TAR="/tmp/labagent-update.tar"

# 默认更新后端和前端，也可传入 backend 或 frontend。
SERVICES=("$@")
if [ ${#SERVICES[@]} -eq 0 ]; then
  SERVICES=(backend frontend)
fi

for service in "${SERVICES[@]}"; do
  if [ "$service" != "backend" ] && [ "$service" != "frontend" ]; then
    echo "不支持的服务: $service，仅支持 backend、frontend"
    exit 1
  fi
done

cd "$PROJECT_DIR"

echo "==> 校验 Compose 配置"
docker compose config >/dev/null

echo "==> 构建 amd64 镜像: ${SERVICES[*]}"
for service in "${SERVICES[@]}"; do
  docker buildx build --platform linux/amd64 --load \
    -t "labagent-${service}:latest" "./${service}"
done

# kb-worker 和 tool-runner 与 backend 使用同一个镜像内容。
if [[ " ${SERVICES[*]} " == *" backend "* ]]; then
  docker tag labagent-backend:latest labagent-kb-worker:latest
  docker tag labagent-backend:latest labagent-tool-runner:latest
fi

echo "==> 检查镜像架构"
IMAGES=()
for service in "${SERVICES[@]}"; do
  IMAGES+=("labagent-${service}:latest")
  if [ "$service" = "backend" ]; then
    IMAGES+=("labagent-kb-worker:latest" "labagent-tool-runner:latest")
  fi
done

for image in "${IMAGES[@]}"; do
  architecture=$(docker image inspect "$image" --format '{{.Architecture}}/{{.Os}}')
  if [ "$architecture" != "amd64/linux" ]; then
    echo "镜像架构错误: $image $architecture"
    exit 1
  fi
done

echo "==> 打包镜像"
rm -f "$TAR"
docker save "${IMAGES[@]}" -o "$TAR"
ls -lh "$TAR"

echo "==> 上传镜像和配置"
scp "$TAR" "${SERVER}:${REMOTE_DIR}/"
scp docker-compose.yml .env "${SERVER}:${REMOTE_DEPLOY_DIR}/"

echo "==> 远端更新"
ssh "$SERVER" "cd '${REMOTE_DEPLOY_DIR}' && bash update.sh ${SERVICES[*]}"

echo "==> 部署完成"
