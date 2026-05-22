#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="${PROJECT_DIR}/.backend.pid"

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

BACKEND_PORT="${BACKEND_PORT:-8000}"
BACKEND_APP="${BACKEND_APP:-app.main:app}"

echo "========================================"
echo " SuperSafeTwin Backend Stop Script"
echo "========================================"

terminate_pid_tree() {
  local pid="$1"
  local child

  for child in $(pgrep -P "$pid" 2>/dev/null || true); do
    terminate_pid_tree "$child"
  done

  if kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid" >/dev/null 2>&1 || true
  fi
}

force_kill_pid_tree() {
  local pid="$1"
  local child

  for child in $(pgrep -P "$pid" 2>/dev/null || true); do
    force_kill_pid_tree "$child"
  done

  if kill -0 "$pid" >/dev/null 2>&1; then
    kill -KILL "$pid" >/dev/null 2>&1 || true
  fi
}

# 1. PID 파일 기준 종료
if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE" || true)"

  if [ -n "${PID:-}" ] && kill -0 "$PID" >/dev/null 2>&1; then
    echo "[ACTION] PID 파일 기준 백엔드 종료 시도: PID=$PID"

    terminate_pid_tree "$PID"

    for _ in {1..10}; do
      if ! kill -0 "$PID" >/dev/null 2>&1; then
        break
      fi

      sleep 0.2
    done

    if kill -0 "$PID" >/dev/null 2>&1; then
      echo "[WARN] 정상 종료가 지연되어 PID 트리만 강제 종료합니다."
      force_kill_pid_tree "$PID"
    fi

    sleep 2
  else
    echo "[INFO] PID 파일의 프로세스가 이미 없습니다."
  fi

  rm -f "$PID_FILE"
else
  echo "[INFO] .backend.pid 파일이 없습니다."
fi

# 2. run.sh가 띄운 앱/포트 조합만 보조 종료
MATCHED_PIDS="$(pgrep -f "uvicorn ${BACKEND_APP} .*--port ${BACKEND_PORT}" || true)"
if [ -n "$MATCHED_PIDS" ]; then
  echo "[ACTION] ${BACKEND_APP}:${BACKEND_PORT} uvicorn 프로세스 종료"
  for pid in $MATCHED_PIDS; do
    terminate_pid_tree "$pid"
  done
  sleep 2
fi

# 3. 그래도 8000 포트를 잡고 있는 프로세스가 있으면 안내
if ss -ltnp 2>/dev/null | grep -q ":${BACKEND_PORT}"; then
  echo "[WARN] 아직 ${BACKEND_PORT} 포트를 사용하는 프로세스가 있습니다."
  echo
  ss -ltnp | grep ":${BACKEND_PORT}" || true
  echo
  echo "강제로 종료하려면 아래 명령을 사용하세요:"
  echo "  fuser -k ${BACKEND_PORT}/tcp"
  exit 1
fi

echo "[OK] 백엔드가 종료되었습니다."
