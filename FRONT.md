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
POST /buildings/{building_id}/scene-graph/mutations
POST /buildings/{building_id}/fire-risk-assessments

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
    "assets": {},
    "overlays": {}
  }
}
```

scene graph JSON에는 의미 정보만 둡니다. 영상, point cloud, mesh, glb 같은 무거운 asset은 MinIO에 두고 scene graph에는 asset id 또는 URL만 포함하는 방향입니다.

### POST /buildings/{building_id}/scene-graph/mutations

선택한 건물의 최신 scene graph에 변경사항을 적용합니다. 프론트는 `GET /buildings/{building_id}/scene-graph`에서 받은 `graph_data_id`를 `base_graph_data_id`로 보내야 합니다.

백엔드는 기존 `graph_data`를 덮어쓰지 않고 변경이 적용된 새 scene graph snapshot을 저장한 뒤 반환합니다. `base_graph_data_id`가 최신 graph가 아니면 `409 Conflict`를 반환하므로, 프론트는 최신 scene graph를 다시 조회한 뒤 재시도해야 합니다.

지원 mutation type:

```text
ADD_NODE
UPDATE_NODE
REMOVE_NODE
ADD_OVERLAY
UPDATE_OVERLAY
REMOVE_OVERLAY
```

권한:

```text
FACILITY_MANAGER  node mutation, overlay mutation 가능
FIREFIGHTER       overlay mutation 가능
```

#### ADD_NODE

시설물처럼 scene graph에 새 node를 추가합니다. `node.id`는 생략할 수 있고, 생략하면 백엔드가 UUID를 생성합니다.

요청:

```json
{
  "base_graph_data_id": "current-graph-data-uuid",
  "mutations": [
    {
      "type": "ADD_NODE",
      "payload": {
        "node": {
          "type": "facility",
          "label": "소화기",
          "position": {
            "x": 12.4,
            "y": 0,
            "z": 8.2
          },
          "metadata": {
            "facility_type": "fire_extinguisher"
          }
        }
      }
    }
  ]
}
```

#### UPDATE_NODE

기존 node를 수정합니다. `node.id`는 필수입니다. payload의 node 필드는 기존 node에 merge됩니다.

```json
{
  "base_graph_data_id": "current-graph-data-uuid",
  "mutations": [
    {
      "type": "UPDATE_NODE",
      "payload": {
        "node": {
          "id": "facility-extinguisher-001",
          "label": "1층 복도 소화기",
          "metadata": {
            "facility_type": "fire_extinguisher",
            "inspection_status": "OK"
          }
        }
      }
    }
  ]
}
```

#### REMOVE_NODE

기존 node를 삭제합니다. 백엔드는 삭제되는 node와 연결된 edge도 함께 제거합니다.

```json
{
  "base_graph_data_id": "current-graph-data-uuid",
  "mutations": [
    {
      "type": "REMOVE_NODE",
      "payload": {
        "node_id": "facility-extinguisher-001"
      }
    }
  ]
}
```

#### ADD_OVERLAY

화재, 위험지역, 하이라이트처럼 scene graph 위에 표시할 overlay를 추가합니다. `overlay.id`는 생략할 수 있고, 생략하면 백엔드가 UUID를 생성합니다. `overlay_type`을 생략하면 `overlays.items`에 저장됩니다.

```json
{
  "base_graph_data_id": "current-graph-data-uuid",
  "mutations": [
    {
      "type": "ADD_OVERLAY",
      "payload": {
        "overlay_type": "incidents",
        "overlay": {
          "type": "FIRE",
          "target_node_id": "room-101",
          "position": {
            "x": 10.2,
            "y": 0,
            "z": 4.8
          },
          "severity": "HIGH",
          "status": "ACTIVE"
        }
      }
    }
  ]
}
```

#### UPDATE_OVERLAY

기존 overlay를 수정합니다. `overlay.id`는 필수입니다. `overlay_type`은 대상 overlay가 들어있는 collection 이름입니다.

```json
{
  "base_graph_data_id": "current-graph-data-uuid",
  "mutations": [
    {
      "type": "UPDATE_OVERLAY",
      "payload": {
        "overlay_type": "incidents",
        "overlay": {
          "id": "incident-uuid",
          "severity": "MEDIUM",
          "status": "ACTIVE"
        }
      }
    }
  ]
}
```

#### REMOVE_OVERLAY

기존 overlay를 삭제합니다.

```json
{
  "base_graph_data_id": "current-graph-data-uuid",
  "mutations": [
    {
      "type": "REMOVE_OVERLAY",
      "payload": {
        "overlay_type": "incidents",
        "overlay_id": "incident-uuid"
      }
    }
  ]
}
```

응답:

```json
{
  "building_id": "building-uuid",
  "building_name": "충남대학교 공과대학5호관",
  "graph_data_id": "new-graph-data-uuid",
  "previous_graph_data_id": "current-graph-data-uuid",
  "created_at": "2026-05-31T00:00:00",
  "scene_graph": {
    "version": "1.0",
    "nodes": [],
    "edges": [],
    "assets": {},
    "overlays": {}
  }
}
```

프론트는 응답의 `scene_graph` 또는 이후 `GET /buildings/{building_id}/scene-graph` 결과를 기준으로 뷰어를 다시 렌더링합니다.

### POST /buildings/{building_id}/fire-risk-assessments

선택한 건물의 최신 scene graph를 Gemini로 분석하고 화재 취약 지역을 `overlays.fire_risks`에 반영합니다. 시설관리자와 소방대원 모두 자신에게 접근 권한이 있는 건물에 요청할 수 있습니다.

이 API는 동기 방식이며 request body는 없습니다. Gemini 분석이 끝날 때까지 응답을 기다리므로 프론트는 요청 중 로딩 상태를 표시하고 중복 요청을 막아야 합니다.

백엔드 처리 순서:

```text
1. 요청자의 건물 접근 권한 확인
2. 최신 scene graph 조회
3. Gemini로 화재 취약 지역 분석
4. Gemini가 반환한 target_node_id가 실제 node인지 검증
5. 기존 Gemini 화재 위험 overlay 제거
6. 신규 분석 결과를 overlays.fire_risks에 추가
7. 변경된 scene graph를 새 snapshot으로 저장
```

응답:

```json
{
  "assessment_id": "assessment-uuid",
  "building_id": "building-uuid",
  "building_name": "충남대학교 공과대학5호관",
  "model": "gemini-3.5-flash",
  "summary": "비상구 접근성과 소화 설비 정보가 부족한 구역이 확인되었습니다.",
  "risk_count": 1,
  "findings": [
    {
      "target_node_id": "room-101",
      "severity": "HIGH",
      "category": "EVACUATION",
      "reason": "확인 가능한 피난 경로가 하나뿐입니다.",
      "recommendation": "대체 피난 경로와 비상구 접근성을 점검하세요.",
      "confidence": 0.84
    }
  ],
  "scene_graph_updated": true,
  "graph_data_id": "new-graph-data-uuid",
  "previous_graph_data_id": "analyzed-graph-data-uuid",
  "created_at": "2026-06-13T00:00:00Z",
  "scene_graph": {
    "version": "1.0",
    "nodes": [],
    "edges": [],
    "assets": {},
    "overlays": {
      "fire_risks": [
        {
          "id": "overlay-uuid",
          "type": "FIRE_RISK",
          "source": "GEMINI_FIRE_RISK_ASSESSMENT",
          "assessment_id": "assessment-uuid",
          "assessment_model": "gemini-3.5-flash",
          "assessed_at": "2026-06-13T00:00:00Z",
          "target_node_id": "room-101",
          "severity": "HIGH",
          "category": "EVACUATION",
          "reason": "확인 가능한 피난 경로가 하나뿐입니다.",
          "recommendation": "대체 피난 경로와 비상구 접근성을 점검하세요.",
          "confidence": 0.84,
          "status": "ACTIVE"
        }
      ]
    }
  }
}
```

`severity` 값:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

`scene_graph_updated == true`이면 응답의 `scene_graph`와 `graph_data_id`로 뷰어 상태를 갱신합니다. 분석 결과가 없고 제거할 이전 Gemini overlay도 없으면 새 snapshot을 만들지 않으며 아래처럼 반환합니다.

```text
scene_graph_updated     false
previous_graph_data_id  null
graph_data_id           현재 graph_data_id
```

재분석 시 `source == "GEMINI_FIRE_RISK_ASSESSMENT"`인 기존 `fire_risks` overlay만 교체합니다. 프론트나 사용자가 직접 만든 다른 overlay는 삭제하지 않습니다.

Gemini 분석 중 scene graph가 변경되면 `409 Conflict`가 반환됩니다. 프론트는 최신 scene graph를 다시 조회한 후 사용자에게 재시도를 안내합니다. Gemini 호출 또는 응답 검증이 실패하면 `502 Bad Gateway`가 반환되며 scene graph는 변경되지 않습니다.

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

### Scene graph 수정

```text
1. GET /buildings
2. 사용자가 건물 선택
3. GET /buildings/{building_id}/scene-graph
4. Three.js 뷰어에서 node 또는 overlay 편집
5. POST /buildings/{building_id}/scene-graph/mutations
6. 201 응답의 scene_graph로 렌더링 갱신
7. 409 Conflict이면 최신 scene graph 재조회 후 재시도
```

### 화재 취약 지역 분석

```text
1. GET /buildings
2. 사용자가 건물 선택
3. GET /buildings/{building_id}/scene-graph
4. 분석 버튼 클릭 중복 방지 및 로딩 표시
5. POST /buildings/{building_id}/fire-risk-assessments
6. scene_graph_updated == true이면 응답의 scene_graph로 렌더링 갱신
7. overlays.fire_risks를 severity에 따라 뷰어에 표시
8. 409 Conflict이면 최신 scene graph 조회 후 재시도 안내
9. 502 Bad Gateway이면 분석 실패 메시지 표시
```

## Error Status

주요 에러는 아래 기준으로 처리합니다.

```text
400 Bad Request        잘못된 요청
401 Unauthorized       토큰 없음 또는 만료/잘못된 토큰
403 Forbidden          권한 없음
404 Not Found          리소스 없음
409 Conflict           중복 이메일, 이미 처리 중인 task, 최신 scene graph 충돌 등
422 Unprocessable      request body validation 실패
500 Internal Error     서버 내부 설정/처리 오류
502 Bad Gateway        모델 서버 또는 Gemini 호출/응답 검증 실패
```

## Notes

- `/geo` API는 없습니다. 프론트가 Kakao 결과를 확정해서 백엔드에 보냅니다.
- `/viewer`, `/emergency/workspace`, `/facility/workspace` API는 없습니다.
- `GET /buildings`는 시설관리자와 소방대원이 공통으로 사용합니다.
- `GET /data-transforms/{task_id}`는 task 상태만 반환합니다. graph JSON은 반환하지 않습니다.
- 최종 scene graph는 항상 `GET /buildings/{building_id}/scene-graph`에서 가져옵니다.
- scene graph 수정은 `POST /buildings/{building_id}/scene-graph/mutations`를 사용합니다. 프론트는 현재 `graph_data_id`를 `base_graph_data_id`로 보내야 합니다.
- 화재 취약 지역 분석은 `POST /buildings/{building_id}/fire-risk-assessments`를 사용하며 request body는 없습니다.
- 화재 위험 표시는 `scene_graph.overlays.fire_risks`를 사용합니다.
