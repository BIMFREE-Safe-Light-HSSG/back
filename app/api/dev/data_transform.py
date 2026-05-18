import json
import os
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.core.database import db
from app.schemas.data_transform import CompleteUploadResponse, UploadRequest
from app.services.data_transform_service import (
    BuildingAccessDeniedError,
    BuildingNotFoundError,
    InvalidUploaderJobError,
    _get_owned_building,
    _safe_filename,
)


DEMO_SAMPLE_UPLOAD_USER_ID = UUID("ce25f278-cdb4-4ccb-94a7-73d7396ce65c")
DEFAULT_SAMPLE_SCENE_GRAPH_PATH = "tmp/scene_graph_skeleton.json"
PROJECT_ROOT = Path(__file__).resolve().parents[3]

router = APIRouter(
    prefix="/dev/data_transform",
    tags=["dev"],
)


class DevUploadUserDeniedError(Exception):
    pass


class DevSampleGraphNotFoundError(Exception):
    pass


def _configured_demo_user_id() -> UUID:
    raw_user_id = os.getenv("DEV_SAMPLE_UPLOAD_USER_ID")
    if raw_user_id and raw_user_id.strip():
        return UUID(raw_user_id.strip())

    return DEMO_SAMPLE_UPLOAD_USER_ID


def _sample_scene_graph_path() -> Path:
    raw_path = Path(
        os.getenv("DEV_SAMPLE_SCENE_GRAPH_PATH", DEFAULT_SAMPLE_SCENE_GRAPH_PATH)
    )
    if raw_path.is_absolute():
        return raw_path

    return PROJECT_ROOT / raw_path


def _load_sample_scene_graph() -> Any:
    sample_path = _sample_scene_graph_path()
    if not sample_path.is_file():
        raise DevSampleGraphNotFoundError

    raw_graph = json.loads(sample_path.read_text(encoding="utf-8"))
    if isinstance(raw_graph, dict) and "scene_graph" in raw_graph:
        return raw_graph["scene_graph"]

    return raw_graph


async def _save_sample_scene_graph(
    payload: UploadRequest,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    if current_user["id"] != _configured_demo_user_id():
        raise DevUploadUserDeniedError

    if payload.building_id is None:
        raise BuildingNotFoundError

    await _get_owned_building(payload.building_id, current_user)

    task_id = uuid4()
    scan_file_path = f"dev://sample-upload/{task_id}/{_safe_filename(payload.filename)}"
    graph_data = _load_sample_scene_graph()

    task = await db.fetch_one(
        """
        INSERT INTO data_transform (id, building_id, status, scan_file_path)
        VALUES ($1, $2, 'COMPLETED', $3)
        RETURNING id, status
        """,
        task_id,
        payload.building_id,
        scan_file_path,
    )
    if task is None:
        raise RuntimeError("Failed to create demo data transform task.")

    graph_row = await db.fetch_one(
        """
        INSERT INTO graph_data (building_id, data_transform_id, graph_json)
        VALUES ($1, $2, $3::jsonb)
        RETURNING id, graph_json::text AS graph_json
        """,
        payload.building_id,
        task_id,
        json.dumps(graph_data, ensure_ascii=False),
    )
    if graph_row is None:
        raise RuntimeError("Failed to save demo sample scene graph.")

    return {
        "message": "Demo upload completed and sample scene graph saved successfully.",
        "task_id": task["id"],
        "status": task["status"],
        "graph_data_id": graph_row["id"],
        "graph_data": json.loads(graph_row["graph_json"]),
    }


@router.post(
    "/sample_upload",
    response_model=CompleteUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def sample_upload(
    payload: UploadRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> CompleteUploadResponse:
    try:
        result = await _save_sample_scene_graph(payload, current_user)
    except DevUploadUserDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This dev upload endpoint is only available to the demo user.",
        ) from exc
    except BuildingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Building not found.",
        ) from exc
    except (BuildingAccessDeniedError, InvalidUploaderJobError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to upload scans for this building.",
        ) from exc
    except DevSampleGraphNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sample scene graph file was not found.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sample scene graph file must be valid JSON.",
        ) from exc

    return CompleteUploadResponse(**result)
