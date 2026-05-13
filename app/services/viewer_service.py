import json
from typing import Any
from uuid import UUID

from app.core.database import db


class ViewerAccessDeniedError(Exception):
    pass


class ViewerBuildingNotFoundError(Exception):
    pass


class SceneGraphNotFoundError(Exception):
    pass


def _decode_graph_json(graph_json: Any) -> Any:
    if isinstance(graph_json, str):
        return json.loads(graph_json)

    return graph_json


def _jurisdiction_codes(current_user: dict[str, Any]) -> tuple[str | None, str | None]:
    jurisdiction = current_user.get("jurisdiction")
    if not isinstance(jurisdiction, dict):
        return None, None

    code = jurisdiction.get("code")
    name = jurisdiction.get("name")
    return (str(code) if code else None, str(name) if name else None)


async def list_viewer_buildings(current_user: dict[str, Any]) -> list[dict[str, Any]]:
    job = current_user.get("job")

    if job == "FACILITY_MANAGER":
        rows = await db.fetch_all(
            """
            SELECT
                b.id,
                b.name,
                b.address,
                b.latitude,
                b.longitude,
                b.district_code,
                b.district_name,
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
            WHERE b.owner_id = $1
            ORDER BY b.created_at DESC
            """,
            current_user["id"],
        )
    elif job == "FIREFIGHTER":
        jurisdiction_code, jurisdiction_name = _jurisdiction_codes(current_user)
        if not jurisdiction_code and not jurisdiction_name:
            return []

        rows = await db.fetch_all(
            """
            SELECT
                b.id,
                b.name,
                b.address,
                b.latitude,
                b.longitude,
                b.district_code,
                b.district_name,
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
    else:
        rows = []

    return rows


async def _find_accessible_building(
    current_user: dict[str, Any],
    building_id: UUID,
) -> dict[str, Any]:
    job = current_user.get("job")

    building = await db.fetch_one(
        """
        SELECT id, owner_id, name, address, latitude, longitude, district_code, district_name
        FROM buildings
        WHERE id = $1
        """,
        building_id,
    )
    if building is None:
        raise ViewerBuildingNotFoundError

    if job == "FACILITY_MANAGER" and building["owner_id"] == current_user["id"]:
        return building

    if (
        job == "FIREFIGHTER"
        and (
            building["district_code"] in _jurisdiction_codes(current_user)
            or building["district_name"] in _jurisdiction_codes(current_user)
        )
    ):
        return building

    raise ViewerAccessDeniedError


async def get_scene_graph(
    current_user: dict[str, Any],
    building_id: UUID,
) -> dict[str, Any]:
    building = await _find_accessible_building(current_user, building_id)
    graph = await db.fetch_one(
        """
        SELECT id, graph_json::text AS graph_json, created_at
        FROM graph_data
        WHERE building_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        building_id,
    )
    if graph is None:
        raise SceneGraphNotFoundError

    return {
        "building_id": building["id"],
        "building_name": building["name"],
        "graph_data_id": graph["id"],
        "created_at": graph["created_at"],
        "scene_graph": _decode_graph_json(graph["graph_json"]),
    }


async def get_viewer_bootstrap(current_user: dict[str, Any]) -> dict[str, Any]:
    buildings = await list_viewer_buildings(current_user)
    default_building = next(
        (building for building in buildings if building["has_scene_graph"]),
        buildings[0] if buildings else None,
    )

    default_scene_graph = None
    if default_building is not None and default_building["has_scene_graph"]:
        default_scene_graph = await get_scene_graph(current_user, default_building["id"])

    return {
        "buildings": buildings,
        "default_building_id": default_building["id"] if default_building else None,
        "default_scene_graph": default_scene_graph,
    }
