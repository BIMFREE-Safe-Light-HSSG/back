from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BuildingBase(BaseModel):
    name: str = Field(..., examples=["공학관 1호관"])
    address: str | None = Field(default=None, examples=["대전광역시 유성구 대학로 99"])
    description: str | None = Field(
        default=None,
        examples=["졸업프로젝트 테스트용 건물 데이터"],
    )


class BuildingCreate(BuildingBase):
    owner_id: UUID | None = Field(
        default=None,
        description="건물 소유자 또는 관리자 user id",
    )


class BuildingUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    description: str | None = None


class BuildingResponse(BuildingBase):
    id: UUID
    owner_id: UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)