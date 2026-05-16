# BIMFree Backend

FastAPI 기반 BIMFree 백엔드입니다. 현재 범위는 사용자 인증, Kakao 지도 좌표 검증, 건물별 scene graph 조회, 스캔 파일 업로드 및 모델 서버 변환 요청입니다.

## 핵심 기능

- 회원가입/로그인/JWT 인증
- Kakao Local API 기반 좌표 -> 주소/행정구역 변환
- 시설관리자: 본인 소유 건물 조회, 스캔 업로드, scene graph 조회
- 소방대원: 본인 관할 지구 건물 조회, scene graph 조회
- MinIO presigned URL 기반 스캔 파일 직접 업로드
- 모델 서버 변환 요청 후 `graph_data` 저장

## 기술 스택

- Python 3.12
- FastAPI
- asyncpg
- PostgreSQL 16
- MinIO
- Kakao Local API
- Caddy
- Docker Compose
- uv

## 프로젝트 구조

```txt
app/
  api/
    auth.py              # 회원가입/로그인/현재 사용자
    data_transform.py    # 스캔 업로드 URL 발급, 변환 완료 처리
    geo.py               # Kakao reverse geocoding
    viewer.py            # 뷰어용 건물/scene graph 조회
    dependencies.py      # JWT 인증 dependency
    dev/                 # 개발 편의용 엔드포인트
  core/
    database.py          # asyncpg pool, 개발용 DDL
  schemas/
    auth.py
    data_transform.py
    geo.py
    viewer.py
  services/
    auth_service.py
    data_transform_service.py
    geo_service.py
    viewer_service.py
infra/
  caddy/Caddyfile
docker-compose.yml
run.sh
stop.sh
FRONT.md
```

프론트엔드 연동 계약은 [FRONT.md](FRONT.md)를 기준으로 봅니다.

## 실행 준비

`.env.example`을 복사해서 `.env`를 만듭니다.

```bash
cp .env.example .env
```

필수로 확인할 값:

```env
APP_NAME=BIMFree
ENABLE_DEV_ROUTES=true

DATABASE_URL=postgresql://username:password@localhost:5432/BIMFree_db

JWT_SECRET_KEY=replace-with-a-long-random-secret
ACCESS_TOKEN_EXPIRE_MINUTES=60

KAKAO_REST_API_KEY=replace-with-kakao-rest-api-key
KAKAO_LOCAL_API_TIMEOUT_SECONDS=5

MODEL_SERVER_URL=http://localhost:8001
MODEL_SERVER_TRANSFORM_PATH=/transform
MODEL_SERVER_TIMEOUT_SECONDS=300

MINIO_ROOT_USER=username
MINIO_ROOT_PASSWORD=password
MINIO_BUCKET_NAME=scan-files
MINIO_PUBLIC_DOMAIN=storage.example.com
MINIO_PUBLIC_SCHEME=https
MINIO_REGION=us-east-1
MINIO_PRESIGNED_URL_EXPIRES_SECONDS=900

FRONTEND_ORIGIN=https://app.example.com
```

Kakao REST API 키는 Kakao Developers의 앱 키 화면에서 발급합니다. 프론트에서 쓰는 JavaScript 키와 백엔드에서 쓰는 REST API 키는 서로 다릅니다.

## 실행

인프라 컨테이너 실행:

```bash
docker compose up -d
```

백엔드 실행:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

또는 스크립트 사용:

```bash
./run.sh
./stop.sh
```

헬스 체크:

```bash
curl http://127.0.0.1:8000/health
```

## 인증과 사용자 역할

회원가입 시 `job`은 아래 둘 중 하나입니다.

```txt
FACILITY_MANAGER
FIREFIGHTER
```

한글 입력도 서버에서 정규화합니다.

```txt
시설관리자 -> FACILITY_MANAGER
소방대원 -> FIREFIGHTER
```

시설관리자는 Kakao 장소 검색 결과를 `building_location`으로 보냅니다. `district_code/district_name`이 포함되어 있으면 서버는 Kakao API를 다시 호출하지 않고 해당 값을 저장합니다. 행정구역 값이 없고 좌표만 있는 경우에만 Kakao Local API를 fallback으로 호출합니다.

소방대원은 Kakao 주소/지역 검색 결과를 `jurisdiction`으로 보냅니다. 뷰어 권한 매칭에는 `jurisdiction.code`와 건물의 `district_code`가 사용됩니다.

## 주요 API

### Health

```http
GET /health
```

### 회원가입

```http
POST /auth/signup
Content-Type: application/json
```

시설관리자:

```json
{
  "name": "홍길동",
  "job": "FACILITY_MANAGER",
  "building_location": {
    "latitude": 36.3651,
    "longitude": 127.3456,
    "place_name": "충남대학교 공과대학 5호관",
    "address": "대전광역시 유성구 대학로 99",
    "provider": "KAKAO",
    "provider_place_id": "1234567890",
    "district_code": "30200",
    "district_name": "유성구",
    "region_1depth_name": "대전광역시",
    "region_2depth_name": "유성구",
    "region_3depth_name": "궁동"
  },
  "email": "manager@example.com",
  "password": "password123"
}
```

소방대원:

```json
{
  "name": "김소방",
  "job": "FIREFIGHTER",
  "jurisdiction": {
    "code": "30200",
    "name": "유성구",
    "address": "대전광역시 유성구",
    "latitude": 36.3622,
    "longitude": 127.3563,
    "provider": "KAKAO",
    "region_1depth_name": "대전광역시",
    "region_2depth_name": "유성구"
  },
  "email": "firefighter@example.com",
  "password": "password123"
}
```

### 로그인

```http
POST /auth/login
Content-Type: application/json
```

```json
{
  "email": "manager@example.com",
  "password": "password123"
}
```

응답의 `access_token`을 보호 API 호출에 사용합니다.

```http
Authorization: Bearer <access_token>
```

### 현재 사용자

```http
GET /auth/me
Authorization: Bearer <access_token>
```

### 좌표 기반 행정구역 변환

```http
GET /geo/reverse-geocode?latitude=37.5665&longitude=126.978
```

프론트가 Kakao 검색 결과에서 행정구역 정보를 얻지 못했거나, 사용자가 지도에서 좌표만 찍은 경우에 사용하는 보조 API입니다.

응답 예:

```json
{
  "latitude": 37.5665,
  "longitude": 126.978,
  "address": "서울특별시 중구 세종대로 110",
  "building_name": null,
  "district_code": "11140",
  "district_name": "중구",
  "region_1depth_name": "서울특별시",
  "region_2depth_name": "중구",
  "region_3depth_name": "명동",
  "provider": "KAKAO"
}
```

### 뷰어 초기 데이터

```http
GET /facility/workspace 또는 GET /emergency/workspace
Authorization: Bearer <access_token>
```

응답에는 접근 가능한 건물 목록, 기본 건물 ID, 기본 scene graph가 포함됩니다. 시설관리 페이지는 본인 소유 건물들을, 소방대원 건물 정보 조회 페이지는 본인 관할 지구 건물들을 응답받습니다.

### 시설관리자 건물 추가

```http
POST /facility/buildings
Content-Type: application/json
Authorization: Bearer <access_token>
```

시설관리자가 다수의 건물을 관리할 때 사용합니다. 요청 body는 회원가입의 `building_location`과 같은 Kakao 장소 검색 결과입니다.

### 뷰어 건물 목록

```http
GET /facility/buildings 또는 GET /emergency/buildings
Authorization: Bearer <access_token>
```

### 건물 Scene Graph 조회

```http
GET /facility/buildings/{building_id}/scene-graph 또는 GET /emergency/buildings/{building_id}/scene-graph
Authorization: Bearer <access_token>
```

접근 권한:

- 시설관리자: 본인 소유 건물만 가능
- 소방대원: 본인 관할 지구 건물만 가능

### 스캔 업로드 URL 발급

```http
POST /data_transform/upload
Content-Type: application/json
Authorization: Bearer <access_token>
```

시설관리자 본인 소유 건물만 업로드할 수 있습니다.

```json
{
  "filename": "scan.zip",
  "content_type": "application/zip",
  "building_id": "11111111-1111-1111-1111-111111111111"
}
```

응답의 `upload_url`로 프론트가 파일을 직접 `PUT` 업로드합니다.

### 업로드 완료 및 변환 요청

```http
POST /data_transform/{task_id}/complete_upload
Authorization: Bearer <access_token>
```

서버는 모델 서버에 변환 요청을 보내고, 응답의 graph JSON을 `graph_data`에 저장합니다.

## 데이터 흐름

시설관리자 scene graph 생성:

```txt
1. 회원가입 시 Kakao 장소 검색 결과로 건물 등록
2. /data_transform/upload 로 presigned URL 발급
3. MinIO upload_url 로 파일 PUT
4. /data_transform/{task_id}/complete_upload 호출
5. 모델 서버 변환 응답을 graph_data에 저장
6. /facility/workspace 또는 /facility/buildings/{id}/scene-graph 로 조회
```

소방대원 뷰어 조회:

```txt
1. 회원가입 시 Kakao 주소/지역 검색 결과로 관할 지구 등록
2. /emergency/workspace 호출
3. 서버가 jurisdiction_code와 building.district_code를 비교
4. 관할 지구 건물 목록과 scene graph 반환
```

## 데이터베이스

현재는 앱 시작 시 [app/core/database.py](app/core/database.py)의 `init_schema()`가 개발용 DDL을 실행합니다.

생성/관리 테이블:

- `users`
- `buildings`
- `data_transform`
- `graph_data`

운영 단계에서는 Alembic migration으로 전환하는 것을 권장합니다.

## 개발용 엔드포인트

`ENABLE_DEV_ROUTES=true`일 때만 등록됩니다.

```http
GET /dev/users
GET /dev/upload-test
```

## 운영 메모

- `JWT_SECRET_KEY`는 운영에서 반드시 긴 랜덤 문자열로 교체합니다.
- `KAKAO_REST_API_KEY`는 백엔드 `.env`에만 둡니다.
- Kakao JavaScript 키는 프론트에서 사용하고, Kakao Developers에서 웹 도메인을 등록해야 합니다.
- `stop.sh`는 `.backend.pid` 기준 프로세스 트리와 `BACKEND_PORT`에 해당하는 uvicorn만 종료합니다.
- `MODEL_SERVER_URL` 기본 개발값은 `http://localhost:8001` 사용을 권장합니다.
