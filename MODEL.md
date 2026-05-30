# Model Server Integration Guide

SuperSafeTwin 백엔드와 모델 서버 사이의 연동 계약입니다. 모델 서버는 스캔 파일을 읽어 scene graph JSON을 생성하고, 백엔드는 해당 JSON을 `graph_data.graph_json`에 저장합니다.

## Base Rules

- 백엔드가 모델 서버를 호출합니다. 모델 서버가 백엔드 API를 먼저 호출하지 않습니다.
- 모델 서버 URL은 백엔드 환경변수 `MODEL_SERVER_URL`로 설정합니다.
- 기본 호출 URL은 `http://localhost:8001/transform`이며, 운영/개발 환경에서는 `.env`의 `MODEL_SERVER_URL` 값을 사용합니다.
- 요청/응답은 JSON입니다.
- 모델 서버 응답은 반드시 유효한 JSON이어야 합니다.
- 모델 서버는 요청에 포함된 `bucket_name`과 `object_key`로 MinIO 객체를 읽을 수 있어야 합니다.
- 백엔드는 모델 서버에 별도 인증 헤더를 보내지 않습니다.

## Environment

백엔드에서 사용하는 모델 서버 관련 환경변수입니다.

```env
MODEL_SERVER_URL=http://example.com/transform
MODEL_SERVER_TIMEOUT_SECONDS=300
```

| Name | Default | Description |
| --- | --- | --- |
| `MODEL_SERVER_URL` | `http://localhost:8001/transform` | 백엔드가 `POST`로 호출할 모델 서버 transform endpoint |
| `MODEL_SERVER_TIMEOUT_SECONDS` | `300` | 모델 서버 호출 timeout. 0보다 큰 숫자여야 함 |

모델 서버가 MinIO를 직접 읽는 경우 백엔드와 같은 bucket/credential 또는 읽기 가능한 별도 credential을 사용해야 합니다. Docker Compose 내부 네트워크에서 접근한다면 MinIO endpoint는 보통 `http://minio:9000`입니다.

## Backend Flow

프론트엔드와 백엔드의 전체 변환 흐름은 아래 순서입니다.

```text
1. 프론트엔드가 POST /data-transforms/upload 호출
2. 백엔드가 data_transform task 생성
3. 백엔드가 MinIO presigned PUT URL 반환
4. 프론트엔드가 presigned URL로 스캔 파일 업로드
5. 프론트엔드가 POST /data-transforms/{task_id}/complete-upload 호출
6. 백엔드가 task 상태를 PROCESSING, progress_percent=10으로 변경
7. 백엔드 background task가 모델 서버를 호출
8. 모델 서버가 스캔 파일을 읽고 scene graph JSON 반환
9. 백엔드가 반환 JSON을 graph_data.graph_json에 저장
10. 백엔드가 task 상태를 COMPLETED, progress_percent=100으로 변경
```

모델 서버 호출 또는 graph 저장에 실패하면 백엔드는 task 상태를 `FAILED`로 변경하고 `error_message`에 실패 메시지를 저장합니다.

## Transform Endpoint

### POST `MODEL_SERVER_URL`

백엔드가 업로드 완료 후 모델 서버에 보내는 요청입니다.

Request body:

```json
{
  "task_id": "task-uuid",
  "building_id": "building-uuid",
  "scan_file_path": "s3://scan-files/data-transform/task-uuid/scan.zip",
  "bucket_name": "scan-files",
  "object_key": "data-transform/task-uuid/scan.zip"
}
```

Fields:

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| `task_id` | string UUID | no | `data_transform.id` |
| `building_id` | string UUID | yes | 변환 대상 건물 ID. 현재 정상 task에서는 값이 있음 |
| `scan_file_path` | string | no | `s3://{bucket_name}/{object_key}` 형식의 스캔 파일 위치 |
| `bucket_name` | string | no | MinIO bucket 이름 |
| `object_key` | string | no | MinIO object key |

현재 백엔드는 `scan_file_path`가 `s3://`로 시작하고 bucket/key를 포함한다고 가정합니다. 스캔 파일 object key는 아래 형식으로 생성됩니다.

```text
data-transform/{task_id}/{safe_filename}
```

## Success Response

모델 서버는 HTTP `2xx`와 유효한 JSON을 반환해야 합니다.

권장 응답:

```json
{
  "graph_data": {
    "version": "1.0",
    "nodes": [],
    "edges": [],
    "assets": {}
  }
}
```

백엔드는 응답 JSON에서 아래 key를 순서대로 찾아 첫 번째 값을 scene graph로 저장합니다.

```text
graph_data
graph_json
data
result
```

위 key가 없으면 응답 JSON 전체를 scene graph로 저장합니다. 따라서 아래 응답도 허용됩니다.

```json
{
  "version": "1.0",
  "nodes": [],
  "edges": [],
  "assets": {}
}
```

`nodes`, `edges`, `assets`의 상세 schema는 아직 백엔드에서 강제 검증하지 않습니다. 다만 프론트엔드 조회 API는 저장된 JSON을 그대로 `scene_graph`로 반환하므로, 모델 서버와 프론트엔드가 같은 scene graph schema를 공유해야 합니다.

## Failure Response

모델 서버가 HTTP `4xx` 또는 `5xx`를 반환하면 백엔드는 변환 실패로 처리합니다.

예시:

```json
{
  "detail": "scan file is not readable"
}
```

백엔드 처리:

```text
data_transform.status = FAILED
data_transform.progress_percent = 기존 progress_percent
data_transform.error_message = "Model server returned {status_code}: {response_text}"
```

모델 서버가 응답 본문을 길게 반환해도 백엔드는 앞 500자까지만 error message에 포함합니다.

네트워크 오류, timeout, invalid JSON 응답도 `FAILED`로 처리됩니다.

## Timeout

백엔드는 `MODEL_SERVER_TIMEOUT_SECONDS` 동안 모델 서버 응답을 기다립니다. 기본값은 300초입니다.

모델 서버 변환 시간이 이 값을 넘길 수 있다면 둘 중 하나를 선택해야 합니다.

- `MODEL_SERVER_TIMEOUT_SECONDS`를 충분히 늘립니다.
- 모델 서버를 즉시 `2xx`로 응답하는 비동기 처리 방식으로 바꾸고, 백엔드 연동 코드도 별도 상태 조회/콜백 방식으로 변경합니다.

현재 구현은 단일 동기 `POST` 응답에서 최종 scene graph JSON을 받는 방식입니다.

## Storage Contract

모델 서버는 요청의 `bucket_name`과 `object_key`를 사용해 업로드된 스캔 파일을 읽습니다.

MinIO object 예시:

```text
bucket_name: scan-files
object_key: data-transform/0f2f5f6a-2cc8-4db6-a6ed-2c092dff4676/scan.zip
scan_file_path: s3://scan-files/data-transform/0f2f5f6a-2cc8-4db6-a6ed-2c092dff4676/scan.zip
```

백엔드는 모델 서버에 presigned GET URL을 전달하지 않습니다. 모델 서버는 자체 MinIO/S3 client 설정으로 객체를 읽어야 합니다.

## Backend Persistence

성공 시 백엔드는 모델 서버에서 추출한 scene graph JSON을 아래 테이블에 저장합니다.

```text
graph_data.building_id = building_id
graph_data.data_transform_id = task_id
graph_data.graph_json = model_server_response_graph_json
```

이후 프론트엔드는 변환 task API가 아니라 건물 scene graph API로 최종 결과를 조회합니다.

```text
GET /buildings/{building_id}/scene-graph
```

## Logging

백엔드는 모델 서버 연동 중 아래 로그 이벤트를 남깁니다.

```text
model_transform_requested
model_transform_completed
model_transform_rejected
model_transform_failed
model_transform_invalid_json
```

모델 서버 로그에도 `task_id`를 함께 남기면 백엔드 task와 모델 서버 job을 추적하기 쉽습니다.

## Minimal Model Server Example

아래는 계약 형태를 보여주는 최소 FastAPI 예시입니다. 실제 변환 로직과 MinIO 읽기 로직은 모델 서버 구현에 맞게 교체합니다.

```python
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


app = FastAPI()


class TransformRequest(BaseModel):
    task_id: str
    building_id: str | None = None
    scan_file_path: str
    bucket_name: str
    object_key: str


@app.post("/transform")
async def transform_scan(payload: TransformRequest) -> dict[str, Any]:
    if not payload.scan_file_path.startswith("s3://"):
        raise HTTPException(status_code=400, detail="scan_file_path must be s3 path")

    graph_data = {
        "version": "1.0",
        "nodes": [],
        "edges": [],
        "assets": {},
    }
    return {"graph_data": graph_data}
```

## Compatibility Notes

- 모델 서버 응답 최상위 key는 `graph_data`를 권장합니다.
- `graph_json`, `data`, `result`도 현재 백엔드와 호환됩니다.
- 응답 JSON 안에 binary 또는 매우 큰 asset 본문을 직접 넣지 않습니다.
- 영상, point cloud, mesh, glb 같은 무거운 asset은 MinIO에 저장하고 scene graph에는 asset id, object key, URL 같은 참조만 넣는 방향을 권장합니다.
- 모델 서버가 실패 사유를 JSON `detail` 또는 짧은 text body로 반환하면 백엔드 task의 `error_message`에서 원인을 확인하기 쉽습니다.
