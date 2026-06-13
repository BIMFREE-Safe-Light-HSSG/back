import json
import random
from typing import Any
from uuid import UUID

from app.repositories import building_access as building_access_repository
from app.schemas.buildings import SceneGraphMutationRequest
from app.services.building_access_service import SceneGraphNotFoundError
from app.services.scene_graph_mutation_service import mutate_building_scene_graph_as_system


class SceneGraphOverlayTargetNotFoundError(Exception):
    pass


async def add_random_node_overlay(
    building_id: UUID,
    overlay_type: str,
    overlay: dict[str, Any],
    exclude_overlay_types: set[str] | None = None,
) -> None:
    latest_graph = await building_access_repository.get_latest_scene_graph(building_id)
    if latest_graph is None:
        raise SceneGraphNotFoundError

    scene_graph = _decode_graph_json(latest_graph["graph_json"])
    position, target_node_id = _random_node_asset_target(
        scene_graph,
        exclude_overlay_types or set(),
    )
    next_overlay = {
        **overlay,
        "target_node_id": target_node_id,
        "position": position,
    }
    payload = SceneGraphMutationRequest(
        base_graph_data_id=latest_graph["id"],
        mutations=[
            {
                "type": "ADD_OVERLAY",
                "payload": {
                    "overlay_type": overlay_type,
                    "overlay": next_overlay,
                },
            }
        ],
    )
    await mutate_building_scene_graph_as_system(building_id, payload)


def _decode_graph_json(graph_json: Any) -> Any:
    if isinstance(graph_json, str):
        return json.loads(graph_json)

    return graph_json


def _random_node_asset_target(
    scene_graph: Any,
    exclude_overlay_types: set[str],
) -> tuple[dict[str, float], str | None]:
    excluded_node_ids = _overlay_target_node_ids(scene_graph, exclude_overlay_types)
    candidates = [
        (node, asset_position)
        for node in _nodes(scene_graph)
        if str(node.get("id")) not in excluded_node_ids
        for asset_position in _asset_positions(node)
    ]
    if not candidates:
        raise SceneGraphOverlayTargetNotFoundError

    target_node, position = random.choice(candidates)
    return (position, str(target_node.get("id")) if target_node.get("id") else None)


def _nodes(scene_graph: Any) -> list[dict[str, Any]]:
    if not isinstance(scene_graph, dict):
        return []

    nodes = scene_graph.get("nodes")
    if not isinstance(nodes, list):
        return []

    return [node for node in nodes if isinstance(node, dict)]


def _overlay_target_node_ids(
    scene_graph: Any,
    overlay_types: set[str],
) -> set[str]:
    if not isinstance(scene_graph, dict) or not overlay_types:
        return set()

    overlays = scene_graph.get("overlays")
    if not isinstance(overlays, dict):
        return set()

    target_node_ids: set[str] = set()
    for overlay_type in overlay_types:
        collection = overlays.get(overlay_type)
        if not isinstance(collection, list):
            continue

        for overlay in collection:
            if not isinstance(overlay, dict):
                continue

            target_node_id = overlay.get("target_node_id")
            if target_node_id:
                target_node_ids.add(str(target_node_id))

    return target_node_ids


def _asset_positions(node: dict[str, Any]) -> list[dict[str, float]]:
    positions = [
        position
        for asset in _node_assets(node)
        for position in [_position_from_asset(asset)]
        if position is not None
    ]
    return positions


def _node_assets(node: dict[str, Any]) -> list[dict[str, Any]]:
    assets = node.get("assets") or node.get("asset")
    if isinstance(assets, list):
        return [asset for asset in assets if isinstance(asset, dict)]

    if isinstance(assets, dict):
        if _looks_like_asset(assets):
            return [assets]
        return [asset for asset in assets.values() if isinstance(asset, dict)]

    return []


def _looks_like_asset(value: dict[str, Any]) -> bool:
    return any(
        key in value
        for key in (
            "position",
            "xyz",
            "coordinates",
            "coordinate",
            "center",
            "centroid",
            "location",
            "translation",
            "pos",
            "x",
            "y",
            "z",
        )
    )


def _position_from_asset(asset: dict[str, Any]) -> dict[str, float] | None:
    for key in (
        "position",
        "xyz",
        "coordinates",
        "coordinate",
        "center",
        "centroid",
        "location",
        "translation",
        "pos",
    ):
        position = _position_from_value(asset.get(key))
        if position is not None:
            return position

    return _position_from_mapping(asset)


def _position_from_value(value: Any) -> dict[str, float] | None:
    if isinstance(value, dict):
        return _position_from_mapping(value)

    if isinstance(value, list | tuple) and len(value) >= 3:
        return _position_from_sequence(value)

    return None


def _position_from_mapping(source: dict[str, Any]) -> dict[str, float] | None:
    coordinates = {}
    for axis in ("x", "y", "z"):
        value = _axis_value(source, axis)
        if value is None:
            return None
        coordinates[axis] = value

    return coordinates


def _position_from_sequence(values: list[Any] | tuple[Any, ...]) -> dict[str, float] | None:
    coordinates = []
    for value in values[:3]:
        if not _is_number(value):
            return None
        coordinates.append(float(value))

    return {
        "x": coordinates[0],
        "y": coordinates[1],
        "z": coordinates[2],
    }


def _axis_value(source: dict[str, Any], axis: str) -> float | None:
    for key in (axis, axis.upper()):
        value = source.get(key)
        if _is_number(value):
            return float(value)

    return None


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)
