from typing import Any
from uuid import UUID

from app.core.database import db


async def building_exists(building_id: UUID) -> bool:
    row = await db.fetch_one(
        """
        SELECT id
        FROM buildings
        WHERE id = $1
        """,
        building_id,
    )
    return row is not None


async def replace_scene_graph(
    building_id: UUID,
    graph_json: str,
) -> dict[str, Any] | None:
    async with db.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                DELETE FROM graph_data
                WHERE building_id = $1
                """,
                building_id,
            )
            row = await conn.fetchrow(
                """
                INSERT INTO graph_data (building_id, graph_json)
                VALUES ($1, $2::jsonb)
                RETURNING id, building_id, graph_json::text AS graph_json, created_at
                """,
                building_id,
                graph_json,
            )

    return dict(row) if row else None


async def delete_scene_graph_by_building(building_id: UUID) -> int:
    result = await db.execute(
        """
        DELETE FROM graph_data
        WHERE building_id = $1
        """,
        building_id,
    )
    _, _, count = result.partition(" ")
    return int(count) if count.isdecimal() else 0
