from typing import Any
from uuid import UUID

from app.core.database import db


async def list_owned_buildings(user_id: UUID) -> list[dict[str, Any]]:
    return await db.fetch_all(
        """
        SELECT
            b.id,
            b.name,
            b.address,
            b.latitude,
            b.longitude,
            b.district_code,
            b.district_name,
            b.region_1depth_name,
            b.region_2depth_name,
            b.region_3depth_name,
            gd.id IS NOT NULL AS has_scene_graph,
            gd.created_at AS latest_graph_created_at
        FROM buildings b
        JOIN user_buildings ub ON ub.building_id = b.id
        LEFT JOIN LATERAL (
            SELECT id, created_at
            FROM graph_data
            WHERE building_id = b.id
            ORDER BY created_at DESC
            LIMIT 1
        ) gd ON TRUE
        WHERE ub.user_id = $1
        ORDER BY ub.created_at DESC
        """,
        user_id,
    )


async def list_jurisdiction_buildings(
    jurisdiction_code: str | None,
    jurisdiction_name: str | None,
) -> list[dict[str, Any]]:
    return await db.fetch_all(
        """
        SELECT
            b.id,
            b.name,
            b.address,
            b.latitude,
            b.longitude,
            b.district_code,
            b.district_name,
            b.region_1depth_name,
            b.region_2depth_name,
            b.region_3depth_name,
            gd.id IS NOT NULL AS has_scene_graph,
            gd.created_at AS latest_graph_created_at
        FROM buildings b
        LEFT JOIN LATERAL (
            SELECT id, created_at
            FROM graph_data
            WHERE building_id = b.id
            ORDER BY created_at DESC
            LIMIT 1
        ) gd ON TRUE
        WHERE b.district_code = $1
           OR b.district_code = $2
           OR b.district_name = $2
        ORDER BY b.created_at DESC
        """,
        jurisdiction_code,
        jurisdiction_name,
    )


async def get_building_for_access_check(building_id: UUID) -> dict[str, Any] | None:
    return await db.fetch_one(
        """
        SELECT id, name, address, latitude, longitude, district_code, district_name
        FROM buildings
        WHERE id = $1
        """,
        building_id,
    )


async def user_can_manage_building(building_id: UUID, user_id: UUID) -> bool:
    row = await db.fetch_one(
        """
        SELECT 1
        FROM user_buildings
        WHERE building_id = $1 AND user_id = $2
        """,
        building_id,
        user_id,
    )
    return row is not None


async def get_latest_scene_graph(building_id: UUID) -> dict[str, Any] | None:
    return await db.fetch_one(
        """
        SELECT id, graph_json::text AS graph_json, created_at
        FROM graph_data
        WHERE building_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        building_id,
    )
