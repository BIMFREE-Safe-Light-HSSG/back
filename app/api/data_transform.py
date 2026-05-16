from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.schemas.data_transform import (
    CompleteUploadResponse,
    UploadRequest,
    UploadResponse,
)
from app.services.data_transform_service import (
    BuildingAccessDeniedError,
    BuildingNotFoundError,
    InvalidTaskStatusError,
    InvalidUploaderJobError,
    ModelServerError,
    StorageConfigurationError,
    TaskNotFoundError,
    complete_upload,
    create_upload_request,
)


router = APIRouter(
    prefix="/data_transform",
    tags=["data_transform"],
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


@router.post(
    "/{task_id}/complete_upload",
    response_model=CompleteUploadResponse,
)
async def complete_data_upload(
    task_id: UUID,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> CompleteUploadResponse:
    try:
        result = await complete_upload(task_id, current_user)
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
