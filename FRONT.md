# BIMFree Frontend API Guide

이 문서는 프론트엔드에서 회원가입, 로그인, 업무 페이지 진입 화면을 만들기 위해 필요한 API 계약만 정리한다.

## 공통

API Base URL:

```txt
https://bimfree-backend.duckdns.org
```

로컬 개발:

```txt
http://127.0.0.1:8000
```

로그인 이후 보호 API는 항상 아래 헤더를 붙인다.

```http
Authorization: Bearer <access_token>
```

## Kakao Map 사용

회원가입의 건물 선택/관할 지구 선택 지도는 Kakao Maps JavaScript SDK 사용을 권장한다.

프론트에는 Kakao JavaScript 키를 사용한다. 이 키는 브라우저에 노출될 수 있으므로 Kakao Developers에서 웹 플랫폼 도메인 제한을 반드시 설정한다.

백엔드는 Kakao REST API 키를 `.env`의 `KAKAO_REST_API_KEY`로 사용한다. REST API 키는 프론트에 노출하지 않는다.

Kakao Maps API는 무료 제공 쿼터가 있다. 공식 문서 기준으로 Map JavaScript SDK는 일 300,000건, Local API의 좌표->행정구역/주소 변환은 각각 일 100,000건 무료 제공 쿼터가 있으며, 유료 API를 적용하면 초과 사용분 과금이 가능하다. 따라서 "무조건 완전 무료"라기보다는 "무료 쿼터 안에서는 무료"로 이해하면 된다.

## 직업 값

서버 표준 값:

```txt
FACILITY_MANAGER
FIREFIGHTER
```

프론트에서 한글 값을 보내도 서버가 정규화한다.

```txt
시설관리자 -> FACILITY_MANAGER
소방대원 -> FIREFIGHTER
```

## 회원가입

```http
POST /auth/signup
Content-Type: application/json
```

### 시설관리자 회원가입

시설관리자는 Kakao 장소 검색 결과에서 자신의 건물을 선택한다. 프론트는 검색 결과의 좌표, 장소명, 주소, 행정구역 정보를 백엔드에 보낸다. `district_code/district_name`이 있으면 백엔드는 Kakao API를 다시 호출하지 않고 그대로 저장한다.

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

### 소방대원 회원가입

소방대원은 Kakao 주소/지역 검색으로 자신의 관할 지구를 선택한다. 프론트는 관할 지구의 `code/name`을 백엔드에 보내고, 뷰어에서는 같은 관할 지구의 건물들이 조회된다.

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

소방대원은 `building_location`을 보내지 않는다. `code/name`이 없고 좌표만 있는 경우에만 백엔드가 Kakao reverse geocoding을 fallback으로 수행한다.

### 회원가입 응답

```json
{
  "message": "Signup completed successfully.",
  "user": {
    "id": "00000000-0000-0000-0000-000000000000",
    "email": "manager@example.com",
    "name": "홍길동",
    "job": "FACILITY_MANAGER",
    "jurisdiction": null,
    "created_at": "2026-05-13T00:00:00",
    "building": {
      "id": "11111111-1111-1111-1111-111111111111",
      "name": "서울특별시 중구 세종대로 110",
      "address": "서울특별시 중구 세종대로 110",
      "latitude": 37.5665,
      "longitude": 126.978,
      "district_code": "11140",
      "district_name": "중구",
      "region_1depth_name": "서울특별시",
      "region_2depth_name": "중구",
      "region_3depth_name": "태평로1가"
    }
  }
}
```

소방대원 응답은 `building`이 `null`이고 `jurisdiction`이 채워진다.

## 로그인

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

응답:

```json
{
  "message": "Login completed successfully.",
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "00000000-0000-0000-0000-000000000000",
    "email": "manager@example.com",
    "name": "홍길동",
    "job": "FACILITY_MANAGER",
    "jurisdiction": null,
    "created_at": "2026-05-13T00:00:00",
    "building": {
      "id": "11111111-1111-1111-1111-111111111111",
      "name": "서울특별시 중구 세종대로 110",
      "address": "서울특별시 중구 세종대로 110",
      "latitude": 37.5665,
      "longitude": 126.978,
      "district_code": "11140",
      "district_name": "중구",
      "region_1depth_name": "서울특별시",
      "region_2depth_name": "중구",
      "region_3depth_name": "태평로1가"
    }
  }
}
```

프론트는 `access_token`을 저장하고, 이후 뷰어 API 호출에 사용한다.

## 현재 사용자 조회

새로고침 후 로그인 상태 복원에 사용한다.

```http
GET /auth/me
Authorization: Bearer <access_token>
```

응답 형태는 로그인 응답 안의 `user` 객체와 같다.

## 지도 좌표 검증

프론트가 Kakao 검색 결과에서 행정구역 정보를 얻지 못했거나, 좌표만 선택된 경우 보조로 사용할 수 있는 API다. 회원가입 submit에는 가능하면 프론트 검색 결과의 `district_code/district_name`을 포함해서 보낸다.

```http
GET /geo/reverse-geocode?latitude=37.5665&longitude=126.978
```

응답:

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
  "region_3depth_name": "태평로1가",
  "provider": "KAKAO"
}
```

프론트 사용 방식:

```txt
시설관리자: 선택한 좌표를 건물 위치로 확인하고, 응답의 address/district_name을 화면에 표시
소방대원: 선택한 좌표를 관할 지구로 확인하고, 응답의 district_name을 화면에 표시
```

회원가입 submit 시 `district_code/district_name`이 포함되어 있으면 백엔드는 Kakao API를 다시 호출하지 않는다. 이 값이 없고 좌표만 있으면 백엔드가 fallback으로 Kakao Local API를 호출한다.

## 업무 페이지 진입

viewer component를 포함한 업무 페이지 진입 시 아래 API 하나만 호출하면 된다.

```http
GET /facility/workspace 또는 GET /emergency/workspace
Authorization: Bearer <access_token>
```

응답:

```json
{
  "buildings": [
    {
      "id": "11111111-1111-1111-1111-111111111111",
      "name": "서울특별시 중구 세종대로 110",
      "address": "서울특별시 중구 세종대로 110",
      "latitude": 37.5665,
      "longitude": 126.978,
      "district_code": "11140",
      "district_name": "중구",
      "region_1depth_name": "서울특별시",
      "region_2depth_name": "중구",
      "region_3depth_name": "태평로1가",
      "has_scene_graph": true,
      "latest_graph_created_at": "2026-05-13T00:00:00"
    }
  ],
  "default_building_id": "11111111-1111-1111-1111-111111111111",
  "default_scene_graph": {
    "building_id": "11111111-1111-1111-1111-111111111111",
    "building_name": "서울특별시 중구 세종대로 110",
    "graph_data_id": "22222222-2222-2222-2222-222222222222",
    "created_at": "2026-05-13T00:00:00",
    "scene_graph": {
      "nodes": [],
      "edges": []
    }
  }
}
```

`default_scene_graph`는 기본 선택 건물에 scene graph가 있을 때만 내려온다. 없으면 `null`이다.


## 시설관리자 건물 추가

시설관리 페이지에서 관리 건물을 추가할 때 사용한다. `FACILITY_MANAGER`만 호출할 수 있다.

```http
POST /facility/buildings
Content-Type: application/json
Authorization: Bearer <access_token>
```

요청은 회원가입의 `building_location`과 같은 형태다.

```json
{
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
}
```

응답은 생성된 건물 정보다. 생성 후 `/facility/workspace` 또는 `/facility/buildings`를 다시 호출해 목록을 갱신한다.

## 건물 목록만 조회

건물 선택 UI를 따로 갱신할 때 사용한다.

```http
GET /facility/buildings 또는 GET /emergency/buildings
Authorization: Bearer <access_token>
```

시설관리자는 본인 소유 건물만 받는다. 소방대원은 본인 관할 지구 건물만 받는다.

응답:

```json
[
  {
    "id": "11111111-1111-1111-1111-111111111111",
    "name": "서울특별시 중구 세종대로 110",
    "address": "서울특별시 중구 세종대로 110",
    "latitude": 37.5665,
    "longitude": 126.978,
    "district_code": "11140",
    "district_name": "중구",
    "region_1depth_name": "서울특별시",
    "region_2depth_name": "중구",
    "region_3depth_name": "태평로1가",
    "has_scene_graph": true,
    "latest_graph_created_at": "2026-05-13T00:00:00"
  }
]
```

## 특정 건물 Scene Graph 조회

건물 목록에서 선택한 건물을 뷰어에 띄울 때 사용한다.

```http
GET /facility/buildings/{building_id}/scene-graph 또는 GET /emergency/buildings/{building_id}/scene-graph
Authorization: Bearer <access_token>
```

응답:

```json
{
  "building_id": "11111111-1111-1111-1111-111111111111",
  "building_name": "서울특별시 중구 세종대로 110",
  "graph_data_id": "22222222-2222-2222-2222-222222222222",
  "created_at": "2026-05-13T00:00:00",
  "scene_graph": {
    "nodes": [],
    "edges": []
  }
}
```

에러:

```txt
401: 로그인 필요 또는 토큰 만료
403: 해당 건물 접근 권한 없음
404: 건물이 없거나 scene graph가 없음
```

## 스캔 파일 업로드 및 변환

시설관리자가 자신의 건물 scene graph를 만들거나 갱신할 때 사용한다. 서버도 `FACILITY_MANAGER`가 본인 소유 건물에 업로드하는 경우만 허용한다.

전체 흐름:

```txt
1. POST /data_transform/upload
2. 응답의 upload_url로 파일 PUT
3. POST /data_transform/{task_id}/complete_upload
4. GET /facility/buildings/{building_id}/scene-graph 또는 GET /emergency/buildings/{building_id}/scene-graph 또는 GET /facility/workspace 또는 GET /emergency/workspace 재호출
```

### 1. 업로드 URL 요청

```http
POST /data_transform/upload
Content-Type: application/json
Authorization: Bearer <access_token>
```

요청:

```json
{
  "filename": "scan.zip",
  "content_type": "application/zip",
  "building_id": "11111111-1111-1111-1111-111111111111"
}
```

`building_id`는 필수다. 로그인 응답의 `user.building.id` 또는 `/facility/buildings`에서 받은 본인 소유 건물 `id`를 사용한다. 시설관리자는 `/facility/buildings`로 추가 건물을 등록할 수 있다.

응답:

```json
{
  "task_id": "33333333-3333-3333-3333-333333333333",
  "status": "PENDING",
  "bucket_name": "scan-files",
  "object_key": "data-transform/33333333-3333-3333-3333-333333333333/scan.zip",
  "scan_file_path": "s3://scan-files/data-transform/33333333-3333-3333-3333-333333333333/scan.zip",
  "upload_url": "https://bimfree-minio.duckdns.org/scan-files/data-transform/33333333-3333-3333-3333-333333333333/scan.zip?...",
  "method": "PUT",
  "expires_in": 900,
  "headers": {
    "Content-Type": "application/zip"
  }
}
```

프론트는 `task_id`, `upload_url`, `headers`를 저장한다.

### 2. MinIO에 파일 직접 업로드

백엔드가 내려준 `upload_url`로 파일을 직접 `PUT`한다. 이 요청은 백엔드 API가 아니라 MinIO presigned URL 요청이다.

```http
PUT <upload_url>
Content-Type: application/zip
```

요청 body:

```txt
업로드할 원본 파일 binary
```

예시:

```ts
await fetch(uploadUrl, {
  method: "PUT",
  headers: {
    "Content-Type": file.type || "application/octet-stream"
  },
  body: file
});
```

성공 기준은 HTTP 200 계열 응답이다. 업로드가 성공한 뒤에만 완료 API를 호출한다.

### 3. 업로드 완료 및 모델 서버 변환 요청

```http
POST /data_transform/{task_id}/complete_upload
Authorization: Bearer <access_token>
```

요청 body는 없다.

응답:

```json
{
  "message": "Upload completed and graph data saved successfully.",
  "task_id": "33333333-3333-3333-3333-333333333333",
  "status": "COMPLETED",
  "graph_data_id": "22222222-2222-2222-2222-222222222222",
  "graph_data": {
    "nodes": [],
    "edges": []
  }
}
```

`graph_data`는 바로 viewer component에 반영해도 되고, 변환 완료 후 `/facility/buildings/{building_id}/scene-graph`를 다시 호출해서 서버의 최신 scene graph를 가져와도 된다.

에러:

```txt
401: 로그인 필요 또는 토큰 만료
404: task 또는 building 없음
409: 이미 처리 중인 task
500: MinIO 또는 서버 설정 문제
502: 모델 서버 요청 실패
```

### 데모용 샘플 scene graph 업로드

모델 서버가 준비되지 않은 시연 환경에서는 `ENABLE_DEV_ROUTES=true`일 때 아래 dev API를 사용할 수 있다. 이 API는 MinIO 업로드와 모델 서버 호출을 건너뛰고, 서버의 `tmp/scene_graph_skeleton.json`을 해당 건물의 최신 scene graph로 저장한다.

```http
POST /dev/data_transform/sample_upload
Content-Type: application/json
Authorization: Bearer <access_token>
```

요청 body는 기존 `/data_transform/upload`와 동일하다.

```json
{
  "filename": "demo-scan.zip",
  "content_type": "application/zip",
  "building_id": "11111111-1111-1111-1111-111111111111"
}
```

응답은 `/data_transform/{task_id}/complete_upload`와 같은 형태다.

```json
{
  "message": "Demo upload completed and sample scene graph saved successfully.",
  "task_id": "33333333-3333-3333-3333-333333333333",
  "status": "COMPLETED",
  "graph_data_id": "22222222-2222-2222-2222-222222222222",
  "graph_data": {
    "nodes": [],
    "edges": []
  }
}
```

현재 기본 허용 유저는 `ce25f278-cdb4-4ccb-94a7-73d7396ce65c`다. 로그인한 사용자가 이 UUID이고, `building_id`가 해당 사용자의 소유 건물일 때만 성공한다. 운영 빌드에서는 이 API를 사용하지 않는다.

에러:

```txt
401: 로그인 필요 또는 토큰 만료
403: 데모 허용 유저가 아니거나 해당 건물 접근 권한 없음
404: building 없음
500: 샘플 scene graph 파일 없음 또는 JSON 파싱 실패
```

### 업로드 화면에서 관리할 상태

```txt
idle: 파일 선택 전
requestingUploadUrl: /data_transform/upload 요청 중
uploadingFile: MinIO PUT 업로드 중
completingUpload: /complete_upload 요청 중
completed: graph_data 저장 완료
failed: 업로드 또는 변환 실패
```

## 추천 화면 플로우

1. 회원가입 페이지
   - 공통 입력: 이름, 직업, 이메일, 패스워드
   - 시설관리자: Kakao 지도에서 건물 위치 선택
   - 소방대원: Kakao 지도에서 관할 지구 선택
   - Kakao 검색 결과의 좌표, 주소, 행정구역 정보를 회원가입 payload에 포함
2. 로그인 페이지
   - 로그인 성공 시 `access_token` 저장
3. viewer component를 포함한 업무 페이지
   - 진입 시 `GET /facility/workspace 또는 GET /emergency/workspace`
   - `buildings`로 건물 목록/선택 UI 렌더링
   - `default_scene_graph`가 있으면 즉시 뷰어에 렌더링
   - 사용자가 다른 건물을 선택하면 `GET /facility/buildings/{building_id}/scene-graph 또는 GET /emergency/buildings/{building_id}/scene-graph`
4. 시설관리자 업로드/변환
   - 건물 선택 후 파일 선택
   - `/data_transform/upload`로 `upload_url` 발급
   - MinIO에 파일 `PUT`
   - `/data_transform/{task_id}/complete_upload` 호출
   - 완료 후 scene graph를 뷰어에 반영

## 이번 스프린트에서 프론트가 신경 쓸 상태

```txt
loading: bootstrap 또는 scene graph 요청 중
emptyBuildings: 접근 가능한 건물이 없음
emptyGraph: 건물은 있으나 scene graph가 없음
forbidden: 선택한 건물 접근 권한 없음
expiredSession: 401 응답
uploadingScan: 스캔 파일 업로드 중
transformingScan: 모델 서버 변환 중
```
