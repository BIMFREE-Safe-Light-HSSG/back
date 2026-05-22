import json
from typing import Any
from uuid import UUID

from app.repositories import building_access as building_access_repository


class BuildingAccessDeniedError(Exception):
    pass


class BuildingNotFoundError(Exception):
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


async def list_accessible_buildings(
    current_user: dict[str, Any],
) -> list[dict[str, Any]]:
    job = current_user.get("job")

    if job == "FACILITY_MANAGER":
        return await building_access_repository.list_owned_buildings(current_user["id"])

    if job == "FIREFIGHTER":
        jurisdiction_code, jurisdiction_name = _jurisdiction_codes(current_user)
        if not jurisdiction_code and not jurisdiction_name:
            return []

        return await building_access_repository.list_jurisdiction_buildings(
            jurisdiction_code,
            jurisdiction_name,
        )

    return []


async def _get_accessible_building(
    current_user: dict[str, Any],
    building_id: UUID,
) -> dict[str, Any]:
    job = current_user.get("job")

    building = await building_access_repository.get_building_for_access_check(
        building_id
    )
    if building is None:
        raise BuildingNotFoundError

    if job == "FACILITY_MANAGER":
        if await building_access_repository.user_can_manage_building(
            building_id,
            current_user["id"],
        ):
            return building
        raise BuildingAccessDeniedError

    if job == "FIREFIGHTER":
        jurisdiction_code, jurisdiction_name = _jurisdiction_codes(current_user)
        if (
            building["district_code"] in (jurisdiction_code, jurisdiction_name)
            or building["district_name"] in (jurisdiction_code, jurisdiction_name)
        ):
            return building

    raise BuildingAccessDeniedError


async def get_building_scene_graph(
    current_user: dict[str, Any],
    building_id: UUID,
) -> dict[str, Any]:
    building = await _get_accessible_building(current_user, building_id)
    graph = await building_access_repository.get_latest_scene_graph(building_id)
    if graph is None:
        raise SceneGraphNotFoundError

    return {
        "building_id": building["id"],
        "building_name": building["name"],
        "graph_data_id": graph["id"],
        "created_at": graph["created_at"],
        "scene_graph": _decode_graph_json(graph["graph_json"]),
    }
