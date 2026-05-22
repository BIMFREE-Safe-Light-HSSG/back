from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.schemas.data_transform import (
    DataTransformTaskResponse,
    UploadRequest,
    UploadResponse,
)
from app.integrations.storage import StorageConfigurationError
from app.services.data_transform_service import (
    BuildingAccessDeniedError,
    BuildingNotFoundError,
    InvalidTaskStatusError,
    InvalidUploaderJobError,
    TaskNotFoundError,
    create_upload_request,
    get_task_status,
    process_upload_task,
    start_upload_processing,
)


router = APIRouter(
    prefix="/data-transforms",
    tags=["data-transforms"],
)


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_upload(
    payload: UploadRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> UploadResponse:
    try:
        upload = await create_upload_request(payload, current_user)
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
    except StorageConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return UploadResponse(**upload)


@router.get(
    "/{task_id}",
    response_model=DataTransformTaskResponse,
)
async def read_data_transform_task(
    task_id: UUID,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> DataTransformTaskResponse:
    try:
        task = await get_task_status(task_id, current_user)
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data transform task not found.",
        ) from exc
    except BuildingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Building not found.",
        ) from exc
    except (BuildingAccessDeniedError, InvalidUploaderJobError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this data transform task.",
        ) from exc

    return DataTransformTaskResponse(**task)


@router.post(
    "/{task_id}/complete-upload",
    response_model=DataTransformTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def complete_data_upload(
    task_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> DataTransformTaskResponse:
    try:
        task = await start_upload_processing(task_id, current_user)
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data transform task not found.",
        ) from exc
    except BuildingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Building not found.",
        ) from exc
    except (BuildingAccessDeniedError, InvalidUploaderJobError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to complete this upload.",
        ) from exc
    except InvalidTaskStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Data transform task is already processing.",
        ) from exc

    if task["status"] == "PROCESSING":
        background_tasks.add_task(process_upload_task, task_id)

    return DataTransformTaskResponse(**task)
