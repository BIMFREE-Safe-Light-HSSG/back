from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.schemas.facility import CreateBuildingRequest, CreateBuildingResponse
from app.schemas.viewer import (
    SceneGraphResponse,
    ViewerBootstrapResponse,
    ViewerBuildingResponse,
)
from app.services.facility_service import (
    FacilityManagerRequiredError,
    create_managed_building,
)
from app.services.geo_service import (
    GeoConfigurationError,
    GeoNoResultError,
    GeoProviderError,
)
from app.services.viewer_service import (
    SceneGraphNotFoundError,
    ViewerAccessDeniedError,
    ViewerBuildingNotFoundError,
    get_scene_graph,
    get_viewer_bootstrap,
    list_viewer_buildings,
)


router = APIRouter(prefix="/facility", tags=["facility"])


@router.get("/buildings", response_model=list[ViewerBuildingResponse])
async def read_managed_buildings(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> list[ViewerBuildingResponse]:
    buildings = await list_viewer_buildings(current_user)
    return [ViewerBuildingResponse(**building) for building in buildings]


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
    except GeoConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except GeoProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except GeoNoResultError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return CreateBuildingResponse(**building)


@router.get("/workspace", response_model=ViewerBootstrapResponse)
async def read_facility_workspace(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> ViewerBootstrapResponse:
    workspace = await get_viewer_bootstrap(current_user)
    return ViewerBootstrapResponse(**workspace)


@router.get(
    "/buildings/{building_id}/scene-graph",
    response_model=SceneGraphResponse,
)
async def read_facility_scene_graph(
    building_id: UUID,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> SceneGraphResponse:
    try:
        scene_graph = await get_scene_graph(current_user, building_id)
    except ViewerBuildingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Building not found.",
        ) from exc
    except ViewerAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this building.",
        ) from exc
    except SceneGraphNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scene graph not found for this building.",
        ) from exc

    return SceneGraphResponse(**scene_graph)
