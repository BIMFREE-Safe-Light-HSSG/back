# BIMFree Backend

FastAPI 기반 BIMFree Backend. 현재 구현 범위는 사용자 회원가입/로그인, MinIO presigned URL 기반 스캔 파일 업로드 요청, 업로드 완료 후 모델 서버 변환 요청 및 graph data 저장이다.

## 현재 API

- `POST /auth/signup`: 사용자 회원가입
- `POST /auth/login`: 이메일/비밀번호 로그인
- `POST /data_transform/upload`: 변환 task 생성 및 MinIO presigned PUT URL 발급
- `POST /data_transform/{task_id}/complete_upload`: 업로드 완료 처리, 모델 서버 변환 요청, `graph_data` 저장
- `GET /dev/users`: 개발 편의용 가입 유저 조회
- `GET /health`: 서버 상태 확인

## Tech Stack

- Python 3.12
- FastAPI - backend framework
- asyncpg - postgresql connection pool 라이브러리
- PostgreSQL 16 - 서버단 DB
- MinIO - 스캔 데이터가 업로드될 object storage
- Caddy - 리버스 프록시를 위한 웹 서버
- Docker Compose - postgresql, minio, caddy를 docker container로 실행
- uv - 파이썬 가상환경 및 패키지 매니저(pip같은 용도)

## Structure

```txt
app/
  api/
    auth.py
    data_transform.py
    dev/users.py
  core/
    database.py
  schemas/
    auth.py
    data_transform.py
  services/
    auth_service.py
    data_transform_service.py
infra/
  caddy/Caddyfile
docker-compose.yml
.env.example
```

## Getting Started

1. PostgreSQL, MinIO, Caddy 실행(docker compose 실행)

```bash
docker compose up -d
```

현재 Caddy 라우팅

```txt
https://bimfree-backend.duckdns.org -> FastAPI host:8000
https://bimfree-minio.duckdns.org   -> MinIO container:9000
```

2. FastAPI 실행

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

로컬 확인:

```bash
http://127.0.0.1:8000/health
```

외부 도메인 확인:

```bash
https://bimfree-backend.duckdns.org/health
https://bimfree-minio.duckdns.org/minio/health/live
```

## 주요 API

### 회원가입

```http
POST /auth/signup
Content-Type: application/json
```

```json
{
  "email": "user@example.com",
  "password": "password123",
  "name": "User"
}
```

성공 시 `201 Created`와 사용자 정보를 반환한다. 비밀번호는 `pbkdf2_sha256` 해시로 저장됨.

### 로그인

```http
POST /auth/login
Content-Type: application/json
```

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

성공 시 사용자 정보를 반환한다.

### 업로드 요청

```http
POST /data_transform/upload
Content-Type: application/json
```

```json
{
  "filename": "scan.zip",
  "content_type": "application/zip",
  "building_id": null
}
```

응답 예시:

```json
{
  "task_id": "...",
  "status": "PENDING",
  "bucket_name": "scan-files",
  "object_key": "data-transform/.../scan.zip",
  "scan_file_path": "s3://scan-files/data-transform/.../scan.zip",
  "upload_url": "https://bimfree-minio.duckdns.org/scan-files/...",
  "method": "PUT",
  "expires_in": 900,
  "headers": {
    "Content-Type": "application/zip"
  }
}
```

프론트엔드는 `upload_url`로 파일을 직접 `PUT` 업로드함.

### 업로드 완료 처리

```http
POST /data_transform/{task_id}/complete_upload
```

처리 순서:

1. task 상태를 `PROCESSING`으로 변경
2. 모델 서버에 변환 요청
3. 모델 서버 응답에서 graph data 추출
4. `graph_data` 테이블에 JSONB로 저장
5. task 상태를 `COMPLETED`로 변경

모델 서버 요청 payload:

```json
{
  "task_id": "...",
  "building_id": null,
  "scan_file_path": "s3://scan-files/data-transform/.../scan.zip",
  "bucket_name": "scan-files",
  "object_key": "data-transform/.../scan.zip"
}
```

모델 서버 응답은 아래 key 중 하나를 graph data로 사용함.

```txt
graph_data
graph_json
data
result
```

해당 key가 없으면 응답 JSON 전체를 graph data로 저장함.

### 개발용 유저 조회

```http
GET /dev/users?limit=100&offset=0
```

## Database

앱 시작 시 개발용 DDL을 실행.

- `users`
- `buildings`
- `data_transform`
- `graph_data`

마이그레이션 도구는 아직 본격 적용하지 않았고, 현재는 [app/core/database.py](app/core/database.py)의 `init_schema()`를 사용한다.

## .env 변경 시 container 재시작
```
docker compose up -d --force-recreate minio caddy minio-init
```

## 클론 후 재현 절차

새 환경에서 프로젝트를 재현하려면 Git에 포함된 파일과 별도로 `.env`, 도메인, 포트포워딩, 모델 서버를 준비해야 한다.

```bash
git clone <repository-url>
cd back
cp .env.example .env
```

`.env`에서 최소한 아래 값을 자신의 환경에 맞게 수정한다.

```env
DATABASE_URL=postgresql://username:password@localhost:5432/BIMFree_db
POSTGRES_USER=username
POSTGRES_PASSWORD=password
POSTGRES_DB=BIMFree_db

API_PUBLIC_DOMAIN=api.example.com
MINIO_PUBLIC_DOMAIN=storage.example.com
FRONTEND_ORIGIN=https://app.example.com

MINIO_ROOT_USER=username
MINIO_ROOT_PASSWORD=password

MODEL_SERVER_URL=http://localhost:8001
MODEL_SERVER_TRANSFORM_PATH=/transform
```

인프라 컨테이너를 실행한다.

```bash
docker compose up -d
```

FastAPI 서버를 실행한다.

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

정상 동작을 확인한다.

```bash
curl http://127.0.0.1:8000/health
curl https://$API_PUBLIC_DOMAIN/health
curl https://$MINIO_PUBLIC_DOMAIN/minio/health/live
```

재현되는 것:

- Python 의존성: `pyproject.toml`, `uv.lock`
- PostgreSQL, MinIO, Caddy 컨테이너 구성
- Caddy reverse proxy 설정
- 앱 시작 시 개발용 DB schema 생성
- MinIO `scan-files` bucket 자동 생성

수동으로 준비해야 하는 것:

- 실제 `.env` 값
- DuckDNS/DNS 레코드
- 공유기 포트포워딩 또는 서버 방화벽
- 모델 서버
- 기존 DB 데이터와 MinIO 업로드 파일

외부에 열 때는 `80`, `443`만 공개하고, `5432`, `8000`, `9000`, `9001`은 직접 공개하지 않는 구성을 권장한다.
