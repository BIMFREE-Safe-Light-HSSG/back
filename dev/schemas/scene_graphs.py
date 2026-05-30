from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class DevSceneGraphCreateRequest(BaseModel):
    scene_graph: Any


class DevSceneGraphResponse(BaseModel):
    graph_data_id: UUID
    building_id: UUID
    created_at: datetime
    scene_graph: Any


class DevSceneGraphDeleteResponse(BaseModel):
    building_id: UUID
    deleted_count: int
