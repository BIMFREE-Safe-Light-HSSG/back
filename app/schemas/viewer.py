from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ViewerBuildingResponse(BaseModel):
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


class ViewerBootstrapResponse(BaseModel):
    buildings: list[ViewerBuildingResponse]
    default_building_id: UUID | None
    default_scene_graph: SceneGraphResponse | None
