from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.data_transform import (
    CompleteUploadResponse,
    UploadRequest,
    UploadResponse,
)
from app.services.data_transform_service import (
    BuildingNotFoundError,
    InvalidTaskStatusError,
    ModelServerError,
    StorageConfigurationError,
    TaskNotFoundError,
    complete_upload,
    create_upload_request,
)


router = APIRouter(prefix="/data_transform", tags=["data_transform"])


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_upload(payload: UploadRequest) -> UploadResponse:
    try:
        upload = await create_upload_request(payload)
    except BuildingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Building not found.",
        ) from exc
    except StorageConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return UploadResponse(**upload)


@router.post(
    "/{task_id}/complete_upload",
    response_model=CompleteUploadResponse,
)
async def complete_data_upload(task_id: UUID) -> CompleteUploadResponse:
    try:
        result = await complete_upload(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data transform task not found.",
        ) from exc
    except InvalidTaskStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Data transform task is already processing.",
        ) from exc
    except StorageConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except ModelServerError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return CompleteUploadResponse(**result)
