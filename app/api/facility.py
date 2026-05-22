from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.schemas.facility import CreateBuildingRequest, CreateBuildingResponse
from app.services.facility_service import (
    FacilityManagerRequiredError,
    create_managed_building,
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
