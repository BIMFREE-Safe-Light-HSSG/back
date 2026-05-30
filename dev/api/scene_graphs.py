import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from dev.repositories import scene_graphs as scene_graphs_repository
from dev.schemas.scene_graphs import (
    DevSceneGraphCreateRequest,
    DevSceneGraphDeleteResponse,
    DevSceneGraphResponse,
)


router = APIRouter(
    prefix="/dev/buildings",
    tags=["dev-scene-graphs"],
)


class BuildingNotFoundError(Exception):
    pass


def _decode_graph_json(graph_json: Any) -> Any:
    if isinstance(graph_json, str):
        return json.loads(graph_json)

    return graph_json


async def _ensure_building_exists(building_id: UUID) -> None:
    if not await scene_graphs_repository.building_exists(building_id):
        raise BuildingNotFoundError


def _scene_graph_response(row: dict[str, Any]) -> DevSceneGraphResponse:
    return DevSceneGraphResponse(
        graph_data_id=row["id"],
        building_id=row["building_id"],
        created_at=row["created_at"],
        scene_graph=_decode_graph_json(row["graph_json"]),
    )


@router.put(
    "/{building_id}/scene-graph",
    response_model=DevSceneGraphResponse,
)
async def replace_building_scene_graph(
    building_id: UUID,
    payload: DevSceneGraphCreateRequest,
) -> DevSceneGraphResponse:
    try:
        await _ensure_building_exists(building_id)
    except BuildingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Building not found.",
        ) from exc

    row = await scene_graphs_repository.replace_scene_graph(
        building_id,
        json.dumps(payload.scene_graph, ensure_ascii=False),
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to replace scene graph.",
        )

    return _scene_graph_response(row)


@router.delete(
    "/{building_id}/scene-graph",
    response_model=DevSceneGraphDeleteResponse,
)
async def delete_building_scene_graph(
    building_id: UUID,
) -> DevSceneGraphDeleteResponse:
    try:
        await _ensure_building_exists(building_id)
    except BuildingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Building not found.",
        ) from exc

    deleted_count = await scene_graphs_repository.delete_scene_graph_by_building(
        building_id
    )
    return DevSceneGraphDeleteResponse(
        building_id=building_id,
        deleted_count=deleted_count,
    )
