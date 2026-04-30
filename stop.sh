#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="${PROJECT_DIR}/.backend.pid"
BACKEND_PORT="${BACKEND_PORT:-8000}"
BACKEND_APP="${BACKEND_APP:-app.main:app}"

cd "$PROJECT_DIR"

echo "========================================"
echo " BIMFree Backend Stop Script"
echo "========================================"

# 1. PID 파일 기준 종료
if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE" || true)"

  if [ -n "${PID:-}" ] && kill -0 "$PID" >/dev/null 2>&1; then
    echo "[ACTION] PID 파일 기준 백엔드 종료 시도: PID=$PID"

    # 해당 PID의 프로세스 그룹까지 종료 시도
    PGID="$(ps -o pgid= "$PID" | tr -d ' ' || true)"

    if [ -n "${PGID:-}" ]; then
      kill -- "-$PGID" >/dev/null 2>&1 || true
    else
      kill "$PID" >/dev/null 2>&1 || true
    fi

    sleep 2
  else
    echo "[INFO] PID 파일의 프로세스가 이미 없습니다."
  fi

  rm -f "$PID_FILE"
else
  echo "[INFO] .backend.pid 파일이 없습니다."
fi

# 2. uvicorn 프로세스 직접 종료
if pgrep -f "uvicorn ${BACKEND_APP}" >/dev/null 2>&1; then
  echo "[ACTION] 남아있는 uvicorn 프로세스 종료"
  pkill -f "uvicorn ${BACKEND_APP}" || true
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