from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class BuildingSummaryResponse(BaseModel):
    id: UUID
    name: str
    address: str | None
    latitude: float | None
    longitude: float | None
    district_code: str | None
    district_name: str | None
    region_1depth_name: str | None
    region_2depth_name: str | None
    region_3depth_name: str | None
    has_scene_graph: bool
    latest_graph_created_at: datetime | None


class SceneGraphResponse(BaseModel):
    building_id: UUID
    building_name: str
    graph_data_id: UUID
    created_at: datetime
    scene_graph: Any


SceneGraphMutationType = Literal[
    "ADD_NODE",
    "UPDATE_NODE",
    "REMOVE_NODE",
    "ADD_OVERLAY",
    "UPDATE_OVERLAY",
    "REMOVE_OVERLAY",
]


class SceneGraphMutation(BaseModel):
    type: SceneGraphMutationType
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_payload(self) -> "SceneGraphMutation":
        if self.type in {"ADD_NODE", "UPDATE_NODE"}:
            node = self.payload.get("node")
            if not isinstance(node, dict):
                raise ValueError("node is required.")
            if self.type == "UPDATE_NODE" and not node.get("id"):
                raise ValueError("node.id is required.")

        if self.type == "REMOVE_NODE" and not self.payload.get("node_id"):
            raise ValueError("node_id is required.")

        if self.type in {"ADD_OVERLAY", "UPDATE_OVERLAY"}:
            overlay = self.payload.get("overlay")
            if not isinstance(overlay, dict):
                raise ValueError("overlay is required.")
            if self.type == "UPDATE_OVERLAY" and not overlay.get("id"):
                raise ValueError("overlay.id is required.")

        if self.type == "REMOVE_OVERLAY" and not self.payload.get("overlay_id"):
            raise ValueError("overlay_id is required.")

        return self


class SceneGraphMutationRequest(BaseModel):
    base_graph_data_id: UUID
    mutations: list[SceneGraphMutation] = Field(min_length=1)


class SceneGraphMutationResponse(BaseModel):
    building_id: UUID
    building_name: str
    graph_data_id: UUID
    previous_graph_data_id: UUID
    created_at: datetime
    scene_graph: Any
