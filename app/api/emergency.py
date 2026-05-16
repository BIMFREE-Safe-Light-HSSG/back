from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.schemas.viewer import (
    SceneGraphResponse,
    ViewerBootstrapResponse,
    ViewerBuildingResponse,
)
from app.services.viewer_service import (
    SceneGraphNotFoundError,
    ViewerAccessDeniedError,
    ViewerBuildingNotFoundError,
    get_scene_graph,
    get_viewer_bootstrap,
    list_viewer_buildings,
)


router = APIRouter(prefix="/emergency", tags=["emergency"])


@router.get("/buildings", response_model=list[ViewerBuildingResponse])
async def read_jurisdiction_buildings(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> list[ViewerBuildingResponse]:
    buildings = await list_viewer_buildings(current_user)
    return [ViewerBuildingResponse(**building) for building in buildings]


@router.get("/workspace", response_model=ViewerBootstrapResponse)
async def read_emergency_workspace(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> ViewerBootstrapResponse:
    workspace = await get_viewer_bootstrap(current_user)
    return ViewerBootstrapResponse(**workspace)


@router.get(
    "/buildings/{building_id}/scene-graph",
    response_model=SceneGraphResponse,
)
async def read_emergency_scene_graph(
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
