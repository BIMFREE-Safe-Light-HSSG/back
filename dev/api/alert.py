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
    SceneGraphOverlayTargetNotFoundError,
    add_random_node_overlay,
)


router = APIRouter(
    prefix="/dev/alert",
    tags=["dev-alert"],
)


FLOOR_5F_ALERT_BUILDING_ID = UUID("e2cb1bb0-fdb8-49a6-ad09-bdf2dcd7a49a")
FLOOR_5F_ALERT_SCOPE_NODE_ID = "FLOOR_5F"


class DevAlertResponse(BaseModel):
    status: str


def _alert_scope_node_id(building_id: UUID) -> str | None:
    if building_id == FLOOR_5F_ALERT_BUILDING_ID:
        return FLOOR_5F_ALERT_SCOPE_NODE_ID

    return None


@router.post(
    "/{building_id}",
    response_model=DevAlertResponse,
)
async def create_random_building_alert(
    building_id: UUID,
) -> DevAlertResponse:
    if not await scene_graphs_repository.building_exists(building_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Building not found.",
        )

    try:
        await add_random_node_overlay(
            building_id,
            "incidents",
            {
                "type": "FIRE",
                "status": "ACTIVE",
                "severity": "HIGH",
                "metadata": {
                    "source": "dev_alert",
                },
            },
            exclude_overlay_types={"occupant"},
            target_scope_node_id=_alert_scope_node_id(building_id),
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
            detail="Scene graph has changed. Retry the dev alert request.",
        ) from exc
    except SceneGraphOverlayTargetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No available alert target in the configured area.",
        ) from exc
    except SceneGraphMutationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create alert overlay.",
        ) from exc

    return DevAlertResponse(status="OK")
