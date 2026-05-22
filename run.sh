#!/usr/bin/env bash

set -euo pipefail

# =========================
# SuperSafeTwin Backend Runner
# =========================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

load_env_file() {
  local env_file="$1"
  local line key value

  if [ ! -f "$env_file" ]; then
    return 0
  fi

  while IFS= read -r line || [ -n "$line" ]; do
    line="${line#${line%%[![:space:]]*}}"
    line="${line%${line##*[![:space:]]}}"

    if [ -z "$line" ] || [[ "$line" == \#* ]] || [[ "$line" != *=* ]]; then
      continue
    fi

    key="${line%%=*}"
    value="${line#*=}"
    key="${key#${key%%[![:space:]]*}}"
    key="${key%${key##*[![:space:]]}}"
    value="${value#${value%%[![:space:]]*}}"
    value="${value%${value##*[![:space:]]}}"

    if [[ ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
      echo "[WARN] .env의 잘못된 키를 건너뜁니다: $key"
      continue
    fi

    if [ -n "${!key+x}" ]; then
      continue
    fi


    export "$key=$value"
  done < "$env_file"
}

ENV_FILE="${PROJECT_DIR}/.env"
load_env_file "$ENV_FILE"

# docker-compose.yml 기준으로 계속 떠 있어야 하는 서비스들
# minio-init 같은 1회성 컨테이너는 여기에 넣지 않는 것을 권장
REQUIRED_SERVICES="${REQUIRED_SERVICES:-postgres minio caddy}"

# 실행은 하되, 종료되어도 정상일 수 있는 초기화용 서비스
INIT_SERVICES="${INIT_SERVICES:-minio-init}"

BACKEND_APP="${BACKEND_APP:-app.main:app}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
BACKEND_RELOAD="${BACKEND_RELOAD:-true}"
BACKEND_HEALTH_URL="${BACKEND_HEALTH_URL:-http://127.0.0.1:${BACKEND_PORT}/health}"

LOG_ROOT="${LOG_ROOT:-${PROJECT_DIR}/logs}"
RUNTIME_LOG_DIR="${LOG_ROOT}/backend/runtime"
APP_LOG_DIR="${LOG_ROOT}/backend/app"
ERROR_LOG_DIR="${LOG_ROOT}/backend/error"
MIGRATION_LOG_DIR="${LOG_ROOT}/migrations"
INFRA_LOG_DIR="${LOG_ROOT}/infrastructure"
PID_FILE="${PROJECT_DIR}/.backend.pid"

mkdir -p "$RUNTIME_LOG_DIR" "$APP_LOG_DIR" "$ERROR_LOG_DIR" "$MIGRATION_LOG_DIR" "$INFRA_LOG_DIR"

echo "========================================"
echo " SuperSafeTwin Backend Run Script"
echo " Project: $PROJECT_DIR"
echo "========================================"

# -------------------------
# command check
# -------------------------

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "[ERROR] docker compose 또는 docker-compose 명령어를 찾을 수 없습니다."
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "[ERROR] uv 명령어를 찾을 수 없습니다."
  echo "uv 설치 후 다시 실행하세요."
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "[ERROR] curl 명령어를 찾을 수 없습니다."
  echo "curl 설치 후 다시 실행하세요."
  exit 1
fi

# -------------------------
# docker compose service check
# -------------------------

service_exists() {
  local service="$1"
  "${COMPOSE_CMD[@]}" config --services | grep -Fxq "$service"
}

service_running() {
  local service="$1"
  "${COMPOSE_CMD[@]}" ps --status running --services | grep -Fxq "$service"
}

echo
echo "[1/3] Docker 컨테이너 상태 확인"

NEED_COMPOSE_UP=false

for service in $REQUIRED_SERVICES; do
  if ! service_exists "$service"; then
    echo "[WARN] docker-compose.yml에 '$service' 서비스가 없습니다. 건너뜁니다."
    continue
  fi

  if service_running "$service"; then
    echo "[OK] $service 실행 중"
  else
    echo "[WARN] $service 실행 중 아님"
    NEED_COMPOSE_UP=true
  fi
done

echo
if [ "$NEED_COMPOSE_UP" = true ]; then
  echo "[ACTION] 필요한 컨테이너를 실행합니다."
else
  echo "[ACTION] 필수 컨테이너가 실행 중입니다. compose 설정 변경 여부를 반영합니다."
fi
"${COMPOSE_CMD[@]}" up -d $REQUIRED_SERVICES

# minio-init 같은 초기화 컨테이너 실행
for service in $INIT_SERVICES; do
  if service_exists "$service"; then
    echo
    echo "[ACTION] 초기화 서비스 실행: $service"
    "${COMPOSE_CMD[@]}" up -d "$service" || true
  fi
done

# -------------------------
# backend check
# -------------------------

echo
echo "[2/3] FastAPI 백엔드 상태 확인"

backend_running_by_health() {
  curl -fsS --max-time 3 "$BACKEND_HEALTH_URL" >/dev/null 2>&1
}

backend_running_by_pid() {
  if [ -f "$PID_FILE" ]; then
    local pid
    pid="$(cat "$PID_FILE")"

    if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
      return 0
    fi
  fi

  return 1
}

if backend_running_by_health; then
  echo "[OK] 백엔드가 이미 실행 중입니다."
  echo "[INFO] Health URL: $BACKEND_HEALTH_URL"
  exit 0
fi

if backend_running_by_pid; then
  echo "[WARN] 백엔드 PID는 존재하지만 /health 응답이 없습니다."
  echo "[WARN] 기존 프로세스를 그대로 두고 새로 실행하지 않습니다."
  echo "[INFO] PID: $(cat "$PID_FILE")"
  echo "[INFO] 실행 로그 확인: tail -f ${RUNTIME_LOG_DIR}/backend-$(date +%F).log"
  echo "[INFO] 앱 로그 확인: tail -f ${APP_LOG_DIR}/app-$(date +%F).log"
  exit 1
fi

# stale pid 제거
if [ -f "$PID_FILE" ]; then
  rm -f "$PID_FILE"
fi

# -------------------------
# start backend
# -------------------------

echo
echo "[ACTION] 백엔드를 백그라운드로 실행합니다."

export PROJECT_DIR
export BACKEND_APP
export BACKEND_HOST
export BACKEND_PORT
export BACKEND_RELOAD
export LOG_ROOT

LOG_FILE="${RUNTIME_LOG_DIR}/backend-$(date +%F).log"
UVICORN_ARGS=(
  "$BACKEND_APP"
  --host "$BACKEND_HOST"
  --port "$BACKEND_PORT"
)

if [[ "$BACKEND_RELOAD" =~ ^(1|true|yes|on)$ ]]; then
  UVICORN_ARGS+=(--reload)
fi

setsid uv run uvicorn "${UVICORN_ARGS[@]}" \
  >> "$LOG_FILE" 2>&1 </dev/null &

BACKEND_PID=$!
echo "$BACKEND_PID" > "$PID_FILE"

echo "[INFO] Backend PID: $BACKEND_PID"
echo "[INFO] Runtime log file: ${LOG_FILE}"
echo "[INFO] App log file: ${APP_LOG_DIR}/app-$(date +%F).log"
echo "[INFO] Error log file: ${ERROR_LOG_DIR}/error-$(date +%F).log"

# -------------------------
# health retry
# -------------------------

echo
echo "[3/3] 백엔드 health check"

for i in {1..15}; do
  if backend_running_by_health; then
    echo "[OK] 백엔드 실행 완료"
    echo "[INFO] Health URL: $BACKEND_HEALTH_URL"
    echo "[INFO] 로그 확인:"
    echo "       tail -f ${RUNTIME_LOG_DIR}/backend-$(date +%F).log"
    echo "       tail -f ${APP_LOG_DIR}/app-$(date +%F).log"
    echo "       tail -f ${ERROR_LOG_DIR}/error-$(date +%F).log"
    exit 0
  fi

  sleep 1
done

echo "[ERROR] 백엔드가 정상적으로 응답하지 않습니다."
echo "[INFO] 로그를 확인하세요:"
echo "       tail -n 100 ${RUNTIME_LOG_DIR}/backend-$(date +%F).log"
echo "       tail -n 100 ${ERROR_LOG_DIR}/error-$(date +%F).log"

exit 1