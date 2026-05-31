from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.schemas.buildings import (
    BuildingSummaryResponse,
    SceneGraphMutationRequest,
    SceneGraphMutationResponse,
    SceneGraphResponse,
)
from app.services.building_access_service import (
    SceneGraphNotFoundError,
    BuildingAccessDeniedError,
    BuildingNotFoundError,
    get_building_scene_graph,
    list_accessible_buildings,
)
from app.services.scene_graph_mutation_service import (
    SceneGraphConflictError,
    SceneGraphMutationError,
    mutate_building_scene_graph,
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


@router.post(
    "/{building_id}/scene-graph/mutations",
    response_model=SceneGraphMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def mutate_scene_graph(
    building_id: UUID,
    payload: SceneGraphMutationRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> SceneGraphMutationResponse:
    try:
        scene_graph = await mutate_building_scene_graph(
            current_user,
            building_id,
            payload,
        )
    except BuildingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Building not found.",
        ) from exc
    except BuildingAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to mutate this scene graph.",
        ) from exc
    except SceneGraphNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scene graph not found for this building.",
        ) from exc
    except SceneGraphConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Scene graph has changed. Refresh and retry with the latest graph_data_id.",
        ) from exc
    except SceneGraphMutationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid scene graph mutation.",
        ) from exc

    return SceneGraphMutationResponse(**scene_graph)
