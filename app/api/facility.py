from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.dependencies import get_current_user
from app.schemas.facility import CreateBuildingRequest, CreateBuildingResponse
from app.services.facility_service import (
    FacilityManagerRequiredError,
    ManagedBuildingAccessDeniedError,
    ManagedBuildingNotFoundError,
    create_managed_building,
    delete_managed_building,
)

router = APIRouter(prefix="/facility", tags=["facility"])


@router.post(
    "/buildings",
    response_model=CreateBuildingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_building(
    payload: CreateBuildingRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> CreateBuildingResponse:
    try:
        building = await create_managed_building(current_user, payload)
    except FacilityManagerRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only facility managers can create managed buildings.",
        ) from exc
    return CreateBuildingResponse(**building)


@router.delete(
    "/buildings/{building_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_building(
    building_id: UUID,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> Response:
    try:
        await delete_managed_building(current_user, building_id)
    except FacilityManagerRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only facility managers can delete managed buildings.",
        ) from exc
    except ManagedBuildingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Building not found.",
        ) from exc
    except ManagedBuildingAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this building.",
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
