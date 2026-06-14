from typing import Any
from uuid import UUID

from app.core.database import db


async def get_building_by_id(building_id: UUID) -> dict[str, Any] | None:
    return await db.fetch_one(
        """
        SELECT id
        FROM buildings
        WHERE id = $1
        """,
        building_id,
    )


async def get_owned_building_by_id(
    building_id: UUID,
    user_id: UUID,
) -> dict[str, Any] | None:
    return await db.fetch_one(
        """
        SELECT b.id
        FROM buildings b
        JOIN user_buildings ub ON ub.building_id = b.id
        WHERE b.id = $1 AND ub.user_id = $2
        """,
        building_id,
        user_id,
    )


async def delete_owned_building(
    building_id: UUID,
    user_id: UUID,
) -> bool:
    deleted_building = await db.fetch_one(
        """
        DELETE FROM buildings b
        WHERE b.id = $1
          AND EXISTS (
              SELECT 1
              FROM user_buildings ub
              WHERE ub.building_id = b.id
                AND ub.user_id = $2
                AND ub.role = 'OWNER'
          )
        RETURNING b.id
        """,
        building_id,
        user_id,
    )
    return deleted_building is not None


async def create_managed_building(
    user_id: UUID,
    location: dict[str, Any],
) -> dict[str, Any] | None:
    building_name = (
        location["building_name"]
        or location["address"]
        or "Registered building"
    )

    async with db.acquire() as conn:
        async with conn.transaction():
            building = await conn.fetchrow(
                """
                INSERT INTO buildings (
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
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
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
                return None

            await conn.execute(
                """
                INSERT INTO user_buildings (user_id, building_id, role)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, building_id) DO NOTHING
                """,
                user_id,
                building["id"],
                "OWNER",
            )

    return dict(building)
