# Frontend Integration Guide

SuperSafeTwin 백엔드와 프론트엔드 연동 계약입니다. 현재 API는 JWT 인증을 사용하고, 건물 조회는 역할별 API가 아니라 공통 `/buildings` API에서 권한에 따라 필터링합니다.

## Base Rules
- Backend base URL : `https://supersafetwin-backend.duckdns.org`
- 인증이 필요한 API는 `Authorization: Bearer <access_token>` 헤더를 보냅니다.
- 요청/응답은 JSON입니다. 단, MinIO 업로드는 presigned URL로 직접 `PUT` 합니다.
- 프론트는 Kakao Maps JS SDK 등으로 확정한 행정구역 값을 백엔드에 전달합니다. 백엔드는 Kakao/geo 보정 API를 제공하지 않습니다.
- 시설관리자 건물 등록과 소방대원 관할 매칭은 `district_code`/`district_name` 기준입니다.

## Current Routes

```text
POST /auth/signup
POST /auth/login
GET  /auth/me

GET  /buildings
GET  /buildings/{building_id}/scene-graph

POST /facility/buildings

POST /data-transforms/upload
GET  /data-transforms/{task_id}
POST /data-transforms/{task_id}/complete-upload

GET  /health
```

## Auth

### POST /auth/signup

회원가입입니다.

시설관리자는 계정 정보만 보냅니다. 건물은 회원가입 후 `POST /facility/buildings`에서 따로 등록합니다.

```json
{
  "email": "sisul@aaa.com",
  "password": "qwe123",
  "name": "김시설",
  "job": "FACILITY_MANAGER"
}
```

소방대원은 관할 정보를 함께 보냅니다.

```json
{
  "email": "sobang@aaa.com",
  "password": "qwe123",
  "name": "김소방",
  "job": "FIREFIGHTER",
  "jurisdiction": {
    "code": "3020012200",
    "name": "유성구"
  }
}
```

`jurisdiction.code`와 `jurisdiction.name`은 프론트에서 Kakao Maps JS SDK의 행정구역 결과를 기준으로 채웁니다. 건물 등록의 `district_code`, `district_name`과 같은 규칙을 사용해야 소방대원 건물 조회가 맞게 동작합니다.

응답:

```json
{
  "message": "Signup completed successfully.",
  "user": {
    "id": "uuid",
    "email": "sisul@aaa.com",
    "name": "김시설",
    "job": "FACILITY_MANAGER",
    "jurisdiction": null,
    "created_at": "2026-05-22T00:00:00"
  }
}
```

### POST /auth/login

```json
{
  "email": "sisul@aaa.com",
  "password": "qwe123"
}
```

응답:

```json
{
  "message": "Login completed successfully.",
  "access_token": "jwt-token",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "sisul@aaa.com",
    "name": "김시설",
    "job": "FACILITY_MANAGER",
    "jurisdiction": null,
    "created_at": "2026-05-22T00:00:00"
  }
}
```

프론트는 `access_token`을 저장하고 이후 보호 API 호출에 사용합니다.

```http
Authorization: Bearer <access_token>
```

### GET /auth/me

현재 로그인 사용자를 조회합니다.

응답:

```json
{
  "id": "uuid",
  "email": "sisul@aaa.com",
  "name": "김시설",
  "job": "FACILITY_MANAGER",
  "jurisdiction": null,
  "created_at": "2026-05-22T00:00:00"
}
```

건물 정보는 `/auth/me`에 포함되지 않습니다. 건물 목록은 `GET /buildings`로 가져옵니다.

## Buildings

### POST /facility/buildings

시설관리자 전용 건물 등록 API입니다.

```http
Authorization: Bearer <facility_manager_access_token>
```

필수 필드:

```text
latitude
longitude
district_code
district_name
```

요청 예시:

```json
{
  "latitude": 36.3665878795959,
  "longitude": 127.344385744499,
  "address": "대전 유성구 대학로 99",
  "place_name": "충남대학교 공과대학5호관",
  "provider": "KAKAO",
  "provider_place_id": "17561301",
  "district_code": "3020012200",
  "district_name": "유성구",
  "region_1depth_name": "대전광역시",
  "region_2depth_name": "유성구",
  "region_3depth_name": "궁동"
}
```

응답:

```json
{
  "id": "building-uuid",
  "name": "충남대학교 공과대학5호관",
  "address": "대전 유성구 대학로 99",
  "provider": "KAKAO",
  "provider_place_id": "17561301",
  "latitude": 36.3665878795959,
  "longitude": 127.344385744499,
  "district_code": "3020012200",
  "district_name": "유성구",
  "region_1depth_name": "대전광역시",
  "region_2depth_name": "유성구",
  "region_3depth_name": "궁동"
}
```

백엔드는 건물 생성 후 `user_buildings`에 시설관리자와 건물 관계를 저장합니다.

### GET /buildings

현재 로그인 사용자가 접근 가능한 건물 목록을 반환합니다.

시설관리자:

```text
user_buildings 기준으로 본인이 관리하는 건물만 반환
```

소방대원:

```text
users.jurisdiction_code/name과 buildings.district_code/name이 매칭되는 건물 반환
```

응답:

```json
[
  {
    "id": "building-uuid",
    "name": "충남대학교 공과대학5호관",
    "address": "대전 유성구 대학로 99",
    "latitude": 36.3665878795959,
    "longitude": 127.344385744499,
    "district_code": "3020012200",
    "district_name": "유성구",
    "region_1depth_name": "대전광역시",
    "region_2depth_name": "유성구",
    "region_3depth_name": "궁동",
    "has_scene_graph": false,
    "latest_graph_created_at": null
  }
]
```

### GET /buildings/{building_id}/scene-graph

선택한 건물의 최신 scene graph를 조회합니다. 백엔드는 요청자의 권한을 다시 확인합니다.

응답:

```json
{
  "building_id": "building-uuid",
  "building_name": "충남대학교 공과대학5호관",
  "graph_data_id": "graph-data-uuid",
  "created_at": "2026-05-22T00:00:00",
  "scene_graph": {
    "version": "1.0",
    "nodes": [],
    "edges": [],
    "assets": {}
  }
}
```

scene graph JSON에는 의미 정보만 둡니다. 영상, point cloud, mesh, glb 같은 무거운 asset은 MinIO에 두고 scene graph에는 asset id 또는 URL만 포함하는 방향입니다.

## Data Transform

현재 변환은 `data-transforms` task를 통해 진행합니다. 업로드 진행률과 변환 진행률은 분리해서 관리합니다.

### POST /data-transforms/upload

시설관리자가 스캔 파일 업로드 URL을 요청합니다.

요청:

```json
{
  "building_id": "building-uuid",
  "filename": "scan.zip",
  "content_type": "application/zip"
}
```

응답:

```json
{
  "task_id": "task-uuid",
  "status": "PENDING",
  "bucket_name": "scan-files",
  "object_key": "data-transform/task-uuid/scan.zip",
  "scan_file_path": "s3://scan-files/data-transform/task-uuid/scan.zip",
  "upload_url": "https://...",
  "method": "PUT",
  "expires_in": 900,
  "headers": {
    "Content-Type": "application/zip"
  }
}
```

프론트는 `upload_url`로 파일을 직접 PUT 업로드합니다. 이때 업로드 진행률은 프론트의 upload progress event로 표시합니다.

### PUT upload_url

백엔드 API가 아니라 MinIO presigned URL 호출입니다.

```http
PUT <upload_url>
Content-Type: application/zip
```

업로드 성공 후 다음 API를 호출합니다.

### POST /data-transforms/{task_id}/complete-upload

업로드 완료를 백엔드에 알리고 변환을 시작합니다.

응답 상태 코드는 `202 Accepted`입니다.

응답:

```json
{
  "task_id": "task-uuid",
  "building_id": "building-uuid",
  "status": "PROCESSING",
  "progress_percent": 10,
  "error_message": null
}
```

백엔드는 응답을 먼저 반환하고, 모델 서버 변환과 graph 저장은 백그라운드에서 수행합니다.

### GET /data-transforms/{task_id}

변환 상태를 polling합니다.

응답:

```json
{
  "task_id": "task-uuid",
  "building_id": "building-uuid",
  "status": "PROCESSING",
  "progress_percent": 10,
  "error_message": null
}
```

완료 시:

```json
{
  "task_id": "task-uuid",
  "building_id": "building-uuid",
  "status": "COMPLETED",
  "progress_percent": 100,
  "error_message": null
}
```

실패 시:

```json
{
  "task_id": "task-uuid",
  "building_id": "building-uuid",
  "status": "FAILED",
  "progress_percent": 10,
  "error_message": "Failed to request model server: ..."
}
```

`status == COMPLETED`가 되면 프론트는 최종 scene graph를 아래 API로 다시 조회합니다.

```text
GET /buildings/{building_id}/scene-graph
```

## Recommended Frontend Flows

### 시설관리자 회원가입 후 건물 등록

```text
1. POST /auth/signup
2. POST /auth/login
3. POST /facility/buildings
4. GET /buildings
```

### 소방대원 건물 정보 조회

```text
1. POST /auth/login
2. GET /buildings
3. 사용자가 건물 선택
4. GET /buildings/{building_id}/scene-graph
```

### 시설관리자 파일 업로드 및 변환

```text
1. GET /buildings
2. 사용자가 건물 선택
3. POST /data-transforms/upload
4. PUT upload_url to MinIO
5. POST /data-transforms/{task_id}/complete-upload
6. GET /data-transforms/{task_id} polling
7. status == COMPLETED
8. GET /buildings/{building_id}/scene-graph
```

## Error Status

주요 에러는 아래 기준으로 처리합니다.

```text
400 Bad Request        잘못된 요청
401 Unauthorized       토큰 없음 또는 만료/잘못된 토큰
403 Forbidden          권한 없음
404 Not Found          리소스 없음
409 Conflict           중복 이메일, 이미 처리 중인 task 등
422 Unprocessable      request body validation 실패
500 Internal Error     서버 내부 설정/처리 오류
502 Bad Gateway        모델 서버 호출 실패
```

## Notes

- `/geo` API는 없습니다. 프론트가 Kakao 결과를 확정해서 백엔드에 보냅니다.
- `/viewer`, `/emergency/workspace`, `/facility/workspace` API는 없습니다.
- `GET /buildings`는 시설관리자와 소방대원이 공통으로 사용합니다.
- `GET /data-transforms/{task_id}`는 task 상태만 반환합니다. graph JSON은 반환하지 않습니다.
- 최종 scene graph는 항상 `GET /buildings/{building_id}/scene-graph`에서 가져옵니다.
