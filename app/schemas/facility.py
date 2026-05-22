from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CreateBuildingRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: str | None = Field(default=None, max_length=500)
    place_name: str | None = Field(default=None, max_length=255)
    provider: str | None = Field(default=None, max_length=50)
    provider_place_id: str | None = Field(default=None, max_length=255)
    district_code: str = Field(..., max_length=100)
    district_name: str = Field(..., max_length=255)
    region_1depth_name: str | None = Field(default=None, max_length=255)
    region_2depth_name: str | None = Field(default=None, max_length=255)
    region_3depth_name: str | None = Field(default=None, max_length=255)

    @field_validator("district_code", "district_name")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("district_code and district_name are required")
        return text

    @field_validator(
        "address",
        "place_name",
        "provider",
        "provider_place_id",
        "region_1depth_name",
        "region_2depth_name",
        "region_3depth_name",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None

        text = value.strip()
        return text or None


class CreateBuildingResponse(BaseModel):
    id: UUID
    name: str
    address: str | None
    provider: str | None = None
    provider_place_id: str | None = None
    latitude: float
    longitude: float
    district_code: str | None = None
    district_name: str | None = None
    region_1depth_name: str | None = None
    region_2depth_name: str | None = None
    region_3depth_name: str | None = None
