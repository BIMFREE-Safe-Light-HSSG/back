# SuperSafeTwin Backend

FastAPI 기반 SuperSafeTwin 백엔드입니다. 사용자 인증, Kakao 좌표 검증, 건물별 scene graph 조회, 스캔 파일 업로드, 모델 서버 변환 요청을 담당합니다.

## Tech Stack

- Python 3.12
- FastAPI
- PostgreSQL 16
- asyncpg
- Alembic
- MinIO
- - Caddy
- Docker Compose
- uv

## Project Structure

```txt
app/
  api/              # FastAPI router layer
  core/             # DB pool, logging 등 공통 기반 layer
  schemas/          # Pydantic Request/Response model layer
  services/         # business flow, 권한 판단, orchestration
  repositories/     # DB query, 저장/조회 layer
  integrations/     # Kakao, MinIO, model server 외부 연동 layer
  main.py           # FastAPI 진입점
dev/
  api/              # 개발용 API router 등록 위치
  assets/           # 개발용 페이지/정적 파일
infra/
  caddy/            # Caddy 설정
migrations/
  versions/         # Alembic migration files
```

프론트엔드 연동 계약은 `FRONT.md`를 기준으로 봅니다.

## Setup

`.env.example`을 복사해서 `.env`를 만들고 실제 값을 채웁니다.

```bash
cp .env.example .env
```

## Main Commands

### Infrastructure

```bash
docker compose up -d
```

```bash
docker compose down
```

### Database Migration

현재 DB에 migration 적용:

```bash
uv run alembic upgrade head
```

현재 적용된 revision 확인:

```bash
uv run alembic current
```

최신 migration head 확인:

```bash
uv run alembic heads
```

새 migration 파일 생성:

```bash
uv run alembic revision -m "describe change"
```

생성된 migration 파일에 DDL을 작성한 뒤 다시 적용합니다.

```bash
uv run alembic upgrade head
```

### Backend

개발 서버 실행:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

스크립트로 실행:

```bash
./run.sh
```

`run.sh`는 기본적으로 `BACKEND_RELOAD=true`로 실행되어 코드 변경을 자동 반영합니다. 필요하면 `.env`에서 `BACKEND_RELOAD=false`로 끌 수 있습니다.

스크립트로 종료:

```bash
./stop.sh
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

### Optional Checks

문법 수준 확인이 필요할 때만 실행합니다.

```bash
uv run python -m compileall app dev migrations
```

## Development Notes

- 패키지 관리는 `uv`를 사용합니다.
- 실제 환경변수 값은 `.env`에만 작성합니다.
- 새 환경변수가 필요하면 `.env.example`에 샘플 키를 추가합니다.
- 앱 시작 시 DB schema를 자동 생성하지 않습니다. DB 변경은 Alembic migration으로 관리합니다.
- `dev/`는 개발용 코드를 두는 위치입니다. 기본값은 비활성화이며, 필요한 경우 `.env`에 `ENABLE_DEV_ROUTES=true`를 직접 추가합니다.
- 개발용 라우터는 `dev/api/__init__.py`의 `routers` 목록에 추가하면 앱 시작 시 조건부 등록됩니다.
- 운영 전에는 `JWT_SECRET_KEY`와 MinIO 관련 값을 반드시 실제 값으로 교체합니다.
