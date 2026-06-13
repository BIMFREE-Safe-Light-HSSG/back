from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.services.building_access_service import BuildingNotFoundError
from app.services.scene_graph_mutation_service import (
    SceneGraphConflictError,
    SceneGraphMutationError,
)
from dev.repositories import scene_graphs as scene_graphs_repository
from dev.services.scene_graph_overlay_service import (
    SceneGraphNotFoundError,
    add_random_node_overlay,
)


router = APIRouter(
    prefix="/dev/rfid-tag",
    tags=["dev-rfid-tag"],
)


class DevRfidTagResponse(BaseModel):
    status: str


@router.post(
    "/{building_id}",
    response_model=DevRfidTagResponse,
)
async def create_random_building_rfid_tag(
    building_id: UUID,
) -> DevRfidTagResponse:
    if not await scene_graphs_repository.building_exists(building_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Building not found.",
        )

    try:
        await add_random_node_overlay(
            building_id,
            "occupant",
            {
                "type": "occupant",
                "status": "ACTIVE",
                "severity": "HIGH",
            },
        )
    except BuildingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Building not found.",
        ) from exc
    except SceneGraphNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scene graph not found for this building.",
        ) from exc
    except SceneGraphConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Scene graph has changed. Retry the dev RFID tag request.",
        ) from exc
    except SceneGraphMutationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create RFID tag overlay.",
        ) from exc

    return DevRfidTagResponse(status="OK")
