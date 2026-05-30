from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import verify_model_callback_secret
from app.schemas.data_transform import (
    ModelTransformUpdateRequest,
    ModelTransformUpdateResponse,
)
from app.services.data_transform_service import (
    BuildingNotFoundError,
    InvalidModelUpdateError,
    InvalidTaskStatusError,
    TaskNotFoundError,
    apply_model_transform_update,
)


router = APIRouter(
    prefix="/internal/model",
    tags=["internal-model"],
)


@router.post(
    "/data-transform-status",
    response_model=ModelTransformUpdateResponse,
)
async def update_data_transform_status(
    payload: ModelTransformUpdateRequest,
    _: Annotated[None, Depends(verify_model_callback_secret)],
) -> ModelTransformUpdateResponse:
    try:
        task = await apply_model_transform_update(payload)
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
    except InvalidTaskStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Data transform task is already in a terminal status.",
        ) from exc
    except InvalidModelUpdateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid model transform update.",
        ) from exc

    return ModelTransformUpdateResponse(**task)
