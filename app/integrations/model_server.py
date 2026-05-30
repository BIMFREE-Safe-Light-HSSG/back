import logging
from typing import Any

import httpx

from app.integrations.storage import StorageConfigurationError, _env


logger = logging.getLogger("app.integrations.model_server")


class ModelServerError(Exception):
    pass


def model_server_transform_url() -> str:
    return _env("MODEL_SERVER_URL", "http://localhost:8001/transform")


def model_server_callback_url() -> str:
    return _env(
        "MODEL_CALLBACK_URL",
        "http://localhost:8000/internal/model/data-transform-status",
    )


def model_callback_secret() -> str:
    return _env("MODEL_CALLBACK_SECRET")


def model_server_timeout() -> float:
    raw_timeout = _env("MODEL_SERVER_TIMEOUT_SECONDS", "30")
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


def scan_file_location(scan_file_path: str) -> tuple[str, str]:
    if not scan_file_path.startswith("s3://"):
        raise StorageConfigurationError("scan_file_path must start with s3://.")

    bucket_and_key = scan_file_path.removeprefix("s3://")
    bucket_name, separator, object_key = bucket_and_key.partition("/")
    if not bucket_name or separator != "/" or not object_key:
        raise StorageConfigurationError(
            "scan_file_path must include bucket and object key."
        )

    return bucket_name, object_key


async def submit_transform_task_to_model_server(task: dict[str, Any]) -> None:
    model_callback_secret()
    bucket_name, object_key = scan_file_location(task["scan_file_path"])
    payload = {
        "task_id": str(task["id"]),
        "building_id": str(task["building_id"]) if task["building_id"] else None,
        "scan_file_path": task["scan_file_path"],
        "bucket_name": bucket_name,
        "object_key": object_key,
        "callback_url": model_server_callback_url(),
    }

    logger.info(
        "model_transform_submit_requested task_id=%s building_id=%s bucket=%s object_key=%s",
        payload["task_id"],
        payload["building_id"],
        bucket_name,
        object_key,
    )

    try:
        async with httpx.AsyncClient(timeout=model_server_timeout()) as client:
            response = await client.post(model_server_transform_url(), json=payload)
            response.raise_for_status()
            logger.info(
                "model_transform_submit_accepted task_id=%s status_code=%s",
                payload["task_id"],
                response.status_code,
            )
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "model_transform_submit_rejected task_id=%s status_code=%s",
            payload["task_id"],
            exc.response.status_code,
        )
        detail = exc.response.text[:500]
        raise ModelServerError(
            f"Model server returned {exc.response.status_code}: {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning(
            "model_transform_submit_failed task_id=%s error=%s",
            payload["task_id"],
            exc,
        )
        raise ModelServerError(f"Failed to request model server: {exc}") from exc
