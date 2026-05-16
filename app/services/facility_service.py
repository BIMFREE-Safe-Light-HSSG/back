from typing import Any

from app.core.database import db
from app.schemas.auth import BuildingLocationRequest
from app.services.auth_service import resolve_building_location


class FacilityManagerRequiredError(Exception):
    pass


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
    payload: BuildingLocationRequest,
) -> dict[str, Any]:
    if current_user.get("job") != "FACILITY_MANAGER":
        raise FacilityManagerRequiredError

    location = await resolve_building_location(payload)
    building_name = (
        location["building_name"]
        or location["address"]
        or "Registered building"
    )

    building = await db.fetch_one(
        """
        INSERT INTO buildings (
            owner_id,
            name,
            address,
            provider,
            provider_place_id,
            latitude,
            longitude,
            district_code,
            district_name,
            region_1depth_name,
            region_2depth_name,
            region_3depth_name
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        RETURNING
            id,
            name,
            address,
            provider,
            provider_place_id,
            latitude,
            longitude,
            district_code,
            district_name,
            region_1depth_name,
            region_2depth_name,
            region_3depth_name
        """,
        current_user["id"],
        building_name,
        location["address"],
        location["provider"],
        location["provider_place_id"],
        location["latitude"],
        location["longitude"],
        location["district_code"],
        location["district_name"],
        location["region_1depth_name"],
        location["region_2depth_name"],
        location["region_3depth_name"],
    )
    if building is None:
        raise RuntimeError("Failed to create building.")

    return _building_from_row(building)
