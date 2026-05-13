from pydantic import BaseModel, Field


class ReverseGeocodeResponse(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: str | None
    building_name: str | None
    district_code: str
    district_name: str
    region_1depth_name: str | None
    region_2depth_name: str | None
    region_3depth_name: str | None
    provider: str
