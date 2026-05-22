import logging
from typing import Any

from app.repositories import buildings as buildings_repository
from app.schemas.facility import CreateBuildingRequest

logger = logging.getLogger("app.services.facility")


class FacilityManagerRequiredError(Exception):
    pass


async def resolve_building_location(
    location_payload: CreateBuildingRequest,
) -> dict[str, Any]:
    return {
        "latitude": location_payload.latitude,
        "longitude": location_payload.longitude,
        "address": location_payload.address,
        "building_name": location_payload.place_name,
        "provider": location_payload.provider,
        "provider_place_id": location_payload.provider_place_id,
        "district_code": location_payload.district_code,
        "district_name": location_payload.district_name,
        "region_1depth_name": location_payload.region_1depth_name,
        "region_2depth_name": location_payload.region_2depth_name,
        "region_3depth_name": location_payload.region_3depth_name,
    }


def _building_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "address": row["address"],
        "provider": row["provider"],
        "provider_place_id": row["provider_place_id"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "district_code": row["district_code"],
        "district_name": row["district_name"],
        "region_1depth_name": row["region_1depth_name"],
        "region_2depth_name": row["region_2depth_name"],
        "region_3depth_name": row["region_3depth_name"],
    }


async def create_managed_building(
    current_user: dict[str, Any],
    payload: CreateBuildingRequest,
) -> dict[str, Any]:
    if current_user.get("job") != "FACILITY_MANAGER":
        raise FacilityManagerRequiredError

    location = await resolve_building_location(payload)
    building = await buildings_repository.create_managed_building(
        current_user["id"],
        location,
    )
    if building is None:
        raise RuntimeError("Failed to create building.")

    logger.info(
        "building_created user_id=%s building_id=%s district_code=%s",
        current_user["id"],
        building["id"],
        building["district_code"],
    )
    return _building_from_row(building)
