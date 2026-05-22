from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.schemas.buildings import BuildingSummaryResponse, SceneGraphResponse
from app.services.building_access_service import (
    SceneGraphNotFoundError,
    BuildingAccessDeniedError,
    BuildingNotFoundError,
    get_building_scene_graph,
    list_accessible_buildings,
)


router = APIRouter(prefix="/buildings", tags=["buildings"])


@router.get("", response_model=list[BuildingSummaryResponse])
async def read_accessible_buildings(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> list[BuildingSummaryResponse]:
    buildings = await list_accessible_buildings(current_user)
    return [BuildingSummaryResponse(**building) for building in buildings]


@router.get(
    "/{building_id}/scene-graph",
    response_model=SceneGraphResponse,
)
async def read_building_scene_graph(
    building_id: UUID,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> SceneGraphResponse:
    try:
        scene_graph = await get_building_scene_graph(current_user, building_id)
    except BuildingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Building not found.",
        ) from exc
    except BuildingAccessDeniedError as exc:
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
