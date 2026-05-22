import json
import logging
import re
import uuid
from typing import Any

from app.integrations import storage
from app.integrations.model_server import request_graph_data_from_model_server
from app.repositories import buildings as buildings_repository
from app.repositories import data_transform as data_transform_repository
from app.schemas.data_transform import UploadRequest


logger = logging.getLogger("app.services.data_transform")


class BuildingNotFoundError(Exception):
    pass


class BuildingAccessDeniedError(Exception):
    pass


class InvalidUploaderJobError(Exception):
    pass


class TaskNotFoundError(Exception):
    pass


class InvalidTaskStatusError(Exception):
    pass


def _safe_filename(filename: str) -> str:
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", basename).lstrip(".")

    if not safe_name:
        return "upload.bin"

    return safe_name[:255]


async def _get_owned_building(
    building_id: uuid.UUID,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    if current_user.get("job") != "FACILITY_MANAGER":
        raise InvalidUploaderJobError

    building = await buildings_repository.get_building_by_id(building_id)
    if building is None:
        raise BuildingNotFoundError

    owned_building = await buildings_repository.get_owned_building_by_id(
        building_id,
        current_user["id"],
    )
    if owned_building is None:
        raise BuildingAccessDeniedError

    return owned_building


async def create_upload_request(
    payload: UploadRequest,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    if payload.building_id is None:
        raise BuildingNotFoundError

    await _get_owned_building(payload.building_id, current_user)

    task_id = uuid.uuid4()
    bucket_name = storage.bucket_name()
    object_key = f"data-transform/{task_id}/{_safe_filename(payload.filename)}"
    scan_file_path = f"s3://{bucket_name}/{object_key}"
    expires_in = storage.presigned_url_expires_in()
    upload_url = storage.generate_presigned_put_url(bucket_name, object_key, expires_in)

    task = await data_transform_repository.create_task(
        task_id,
        payload.building_id,
        scan_file_path,
    )

    if task is None:
        raise RuntimeError("Failed to create data transform task.")

    logger.info(
        "upload_task_created task_id=%s building_id=%s user_id=%s object_key=%s",
        task["id"],
        payload.building_id,
        current_user["id"],
        object_key,
    )

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


def _task_response(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task["id"],
        "building_id": task["building_id"],
        "status": task["status"],
        "progress_percent": task["progress_percent"],
        "error_message": task["error_message"],
    }


async def _update_task_status(
    task_id: uuid.UUID,
    status: str,
    progress_percent: int,
    error_message: str | None,
) -> dict[str, Any] | None:
    return await data_transform_repository.update_task_status(
        task_id,
        status,
        progress_percent,
        error_message,
    )


async def get_task_status(
    task_id: uuid.UUID,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    task = await data_transform_repository.get_task(task_id)
    if task is None:
        raise TaskNotFoundError

    if task["building_id"] is None:
        raise BuildingNotFoundError

    await _get_owned_building(task["building_id"], current_user)
    return _task_response(task)


async def start_upload_processing(
    task_id: uuid.UUID,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    task = await data_transform_repository.get_task(task_id)
    if task is None:
        raise TaskNotFoundError

    if task["building_id"] is None:
        raise BuildingNotFoundError

    await _get_owned_building(task["building_id"], current_user)

    if task["status"] == "PROCESSING":
        raise InvalidTaskStatusError

    if task["status"] == "COMPLETED":
        return _task_response(task)

    updated_task = await _update_task_status(task_id, "PROCESSING", 10, None)
    if updated_task is None:
        raise TaskNotFoundError

    logger.info(
        "upload_processing_queued task_id=%s building_id=%s user_id=%s",
        task["id"],
        task["building_id"],
        current_user["id"],
    )
    return _task_response(updated_task)


async def process_upload_task(task_id: uuid.UUID) -> None:
    task = await data_transform_repository.get_task(task_id)
    if task is None:
        logger.warning("upload_processing_skipped reason=missing_task task_id=%s", task_id)
        return

    if task["building_id"] is None:
        await _update_task_status(task_id, "FAILED", 0, "Building not found.")
        return

    try:
        graph_data = await request_graph_data_from_model_server(task)
        graph_row = await data_transform_repository.insert_graph_data(
            task["building_id"],
            task_id,
            json.dumps(graph_data, ensure_ascii=False),
        )
    except Exception as exc:
        logger.exception(
            "upload_processing_failed task_id=%s building_id=%s",
            task["id"],
            task["building_id"],
        )
        await _update_task_status(task_id, "FAILED", task["progress_percent"], str(exc))
        return

    if graph_row is None:
        await _update_task_status(task_id, "FAILED", 10, "Failed to save graph data.")
        logger.error(
            "upload_processing_failed reason=graph_save_failed task_id=%s building_id=%s",
            task["id"],
            task["building_id"],
        )
        return

    await _update_task_status(task_id, "COMPLETED", 100, None)
    logger.info(
        "upload_processing_completed task_id=%s building_id=%s graph_data_id=%s",
        task["id"],
        task["building_id"],
        graph_row["id"],
    )
