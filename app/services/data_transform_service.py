import datetime as dt
import hashlib
import hmac
import json
import os
import re
import uuid
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from app.core.database import db
from app.schemas.data_transform import UploadRequest


AWS_ALGORITHM = "AWS4-HMAC-SHA256"
AWS_SERVICE = "s3"
DEFAULT_REGION = "us-east-1"
MAX_PRESIGNED_URL_EXPIRES_SECONDS = 604_800


class BuildingNotFoundError(Exception):
    pass


class StorageConfigurationError(Exception):
    pass


class TaskNotFoundError(Exception):
    pass


class InvalidTaskStatusError(Exception):
    pass


class ModelServerError(Exception):
    pass


def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise StorageConfigurationError(f"{name} is not configured.")

    value = value.strip()
    if not value:
        if default is not None:
            return default
        raise StorageConfigurationError(f"{name} is not configured.")

    return value


def _bucket_name() -> str:
    return _env("MINIO_BUCKET_NAME", "scan-files")


def _model_server_transform_url() -> str:
    endpoint = os.getenv("MODEL_SERVER_TRANSFORM_ENDPOINT")
    if endpoint and endpoint.strip():
        return endpoint.strip()

    base_url = _env("MODEL_SERVER_URL", "http://localhost:8001").rstrip("/")
    path = _env("MODEL_SERVER_TRANSFORM_PATH", "/transform")
    if not path.startswith("/"):
        path = f"/{path}"

    return f"{base_url}{path}"


def _model_server_timeout() -> float:
    raw_timeout = _env("MODEL_SERVER_TIMEOUT_SECONDS", "300")
    try:
        timeout = float(raw_timeout)
    except ValueError as exc:
        raise StorageConfigurationError(
            "MODEL_SERVER_TIMEOUT_SECONDS must be a number."
        ) from exc

    if timeout <= 0:
        raise StorageConfigurationError(
            "MODEL_SERVER_TIMEOUT_SECONDS must be greater than 0."
        )

    return timeout


def _public_endpoint() -> str:
    endpoint = os.getenv("MINIO_PUBLIC_ENDPOINT")
    if endpoint and endpoint.strip():
        return endpoint.strip().rstrip("/")

    public_domain = _env("MINIO_PUBLIC_DOMAIN", "bimfree-minio.duckdns.org").rstrip("/")
    if public_domain.startswith(("http://", "https://")):
        return public_domain.rstrip("/")

    scheme = _env("MINIO_PUBLIC_SCHEME", "https")
    return f"{scheme}://{public_domain}"


def _expires_in() -> int:
    raw_expires = _env("MINIO_PRESIGNED_URL_EXPIRES_SECONDS", "900")
    try:
        expires = int(raw_expires)
    except ValueError as exc:
        raise StorageConfigurationError(
            "MINIO_PRESIGNED_URL_EXPIRES_SECONDS must be an integer."
        ) from exc

    if expires < 1 or expires > MAX_PRESIGNED_URL_EXPIRES_SECONDS:
        raise StorageConfigurationError(
            "MINIO_PRESIGNED_URL_EXPIRES_SECONDS must be between 1 and 604800."
        )

    return expires


def _safe_filename(filename: str) -> str:
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", basename).lstrip(".")

    if not safe_name:
        return "upload.bin"

    return safe_name[:255]


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret_key: str, date_stamp: str, region: str) -> bytes:
    date_key = _sign(f"AWS4{secret_key}".encode("utf-8"), date_stamp)
    region_key = _sign(date_key, region)
    service_key = _sign(region_key, AWS_SERVICE)
    return _sign(service_key, "aws4_request")


def _canonical_query(params: dict[str, str]) -> str:
    return "&".join(
        f"{quote(key, safe='-_.~')}={quote(value, safe='-_.~')}"
        for key, value in sorted(params.items())
    )


def _generate_presigned_put_url(
    bucket_name: str,
    object_key: str,
    expires_in: int,
) -> str:
    access_key = _env("MINIO_ROOT_USER", "minioadmin")
    secret_key = _env("MINIO_ROOT_PASSWORD", "minioadmin123")
    region = _env("MINIO_REGION", DEFAULT_REGION)
    endpoint = _public_endpoint()
    parsed_endpoint = urlsplit(endpoint)

    if not parsed_endpoint.scheme or not parsed_endpoint.netloc:
        raise StorageConfigurationError(
            "MinIO public endpoint must include scheme and host."
        )

    now = dt.datetime.now(dt.UTC)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    credential_scope = f"{date_stamp}/{region}/{AWS_SERVICE}/aws4_request"
    signed_headers = "host"

    path_prefix = parsed_endpoint.path.rstrip("/")
    canonical_uri = (
        f"{path_prefix}/{quote(bucket_name, safe='')}/{quote(object_key, safe='/-_.~')}"
    )
    credential = f"{access_key}/{credential_scope}"
    query_params = {
        "X-Amz-Algorithm": AWS_ALGORITHM,
        "X-Amz-Credential": credential,
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(expires_in),
        "X-Amz-SignedHeaders": signed_headers,
    }
    canonical_query = _canonical_query(query_params)
    canonical_headers = f"host:{parsed_endpoint.netloc}\n"
    canonical_request = "\n".join(
        [
            "PUT",
            canonical_uri,
            canonical_query,
            canonical_headers,
            signed_headers,
            "UNSIGNED-PAYLOAD",
        ]
    )
    hashed_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = "\n".join(
        [
            AWS_ALGORITHM,
            amz_date,
            credential_scope,
            hashed_request,
        ]
    )
    signature = hmac.new(
        _signing_key(secret_key, date_stamp, region),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    final_query = f"{canonical_query}&X-Amz-Signature={signature}"
    return (
        f"{parsed_endpoint.scheme}://{parsed_endpoint.netloc}"
        f"{canonical_uri}?{final_query}"
    )


async def create_upload_request(payload: UploadRequest) -> dict[str, Any]:
    if payload.building_id is not None:
        building = await db.fetch_one(
            "SELECT id FROM buildings WHERE id = $1",
            payload.building_id,
        )
        if building is None:
            raise BuildingNotFoundError

    task_id = uuid.uuid4()
    bucket_name = _bucket_name()
    object_key = f"data-transform/{task_id}/{_safe_filename(payload.filename)}"
    scan_file_path = f"s3://{bucket_name}/{object_key}"
    expires_in = _expires_in()
    upload_url = _generate_presigned_put_url(bucket_name, object_key, expires_in)

    task = await db.fetch_one(
        """
        INSERT INTO data_transform (id, building_id, status, scan_file_path)
        VALUES ($1, $2, 'PENDING', $3)
        RETURNING id, status, scan_file_path
        """,
        task_id,
        payload.building_id,
        scan_file_path,
    )

    if task is None:
        raise RuntimeError("Failed to create data transform task.")

    return {
        "task_id": task["id"],
        "status": task["status"],
        "bucket_name": bucket_name,
        "object_key": object_key,
        "scan_file_path": task["scan_file_path"],
        "upload_url": upload_url,
        "method": "PUT",
        "expires_in": expires_in,
        "headers": {
            "Content-Type": payload.content_type,
        },
    }


def _scan_file_location(scan_file_path: str) -> tuple[str, str]:
    if not scan_file_path.startswith("s3://"):
        raise StorageConfigurationError("scan_file_path must start with s3://.")

    bucket_and_key = scan_file_path.removeprefix("s3://")
    bucket_name, separator, object_key = bucket_and_key.partition("/")
    if not bucket_name or separator != "/" or not object_key:
        raise StorageConfigurationError(
            "scan_file_path must include bucket and object key."
        )

    return bucket_name, object_key


def _extract_graph_data(response_json: Any) -> Any:
    if not isinstance(response_json, dict):
        return response_json

    for key in ("graph_data", "graph_json", "data", "result"):
        if key in response_json:
            return response_json[key]

    return response_json


def _decode_graph_json(graph_json: Any) -> Any:
    if isinstance(graph_json, str):
        return json.loads(graph_json)

    return graph_json


async def _update_task_status(
    task_id: uuid.UUID,
    status: str,
    error_message: str | None,
) -> None:
    await db.execute(
        """
        UPDATE data_transform
        SET status = $1,
            error_message = $2,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = $3
        """,
        status,
        error_message,
        task_id,
    )


async def _request_graph_data_from_model_server(task: dict[str, Any]) -> Any:
    bucket_name, object_key = _scan_file_location(task["scan_file_path"])
    payload = {
        "task_id": str(task["id"]),
        "building_id": str(task["building_id"]) if task["building_id"] else None,
        "scan_file_path": task["scan_file_path"],
        "bucket_name": bucket_name,
        "object_key": object_key,
    }

    try:
        async with httpx.AsyncClient(timeout=_model_server_timeout()) as client:
            response = await client.post(_model_server_transform_url(), json=payload)
            response.raise_for_status()
            response_json = response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500]
        raise ModelServerError(
            f"Model server returned {exc.response.status_code}: {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ModelServerError(f"Failed to request model server: {exc}") from exc
    except ValueError as exc:
        raise ModelServerError("Model server response must be valid JSON.") from exc

    return _extract_graph_data(response_json)


async def complete_upload(task_id: uuid.UUID) -> dict[str, Any]:
    task = await db.fetch_one(
        """
        SELECT id, building_id, status, scan_file_path
        FROM data_transform
        WHERE id = $1
        """,
        task_id,
    )
    if task is None:
        raise TaskNotFoundError

    if task["status"] == "PROCESSING":
        raise InvalidTaskStatusError

    existing_graph = await db.fetch_one(
        """
        SELECT id, graph_json::text AS graph_json
        FROM graph_data
        WHERE data_transform_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        task_id,
    )
    if task["status"] == "COMPLETED" and existing_graph is not None:
        return {
            "message": "Upload was already completed.",
            "task_id": task["id"],
            "status": task["status"],
            "graph_data_id": existing_graph["id"],
            "graph_data": _decode_graph_json(existing_graph["graph_json"]),
        }

    await _update_task_status(task_id, "PROCESSING", None)

    try:
        graph_data = await _request_graph_data_from_model_server(task)
        graph_row = await db.fetch_one(
            """
            INSERT INTO graph_data (building_id, data_transform_id, graph_json)
            VALUES ($1, $2, $3::jsonb)
            RETURNING id, graph_json::text AS graph_json
            """,
            task["building_id"],
            task_id,
            json.dumps(graph_data),
        )
    except Exception as exc:
        await _update_task_status(task_id, "FAILED", str(exc))
        raise

    if graph_row is None:
        await _update_task_status(task_id, "FAILED", "Failed to save graph data.")
        raise RuntimeError("Failed to save graph data.")

    await _update_task_status(task_id, "COMPLETED", None)

    return {
        "message": "Upload completed and graph data saved successfully.",
        "task_id": task["id"],
        "status": "COMPLETED",
        "graph_data_id": graph_row["id"],
        "graph_data": _decode_graph_json(graph_row["graph_json"]),
    }
