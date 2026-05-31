import copy
import json
from typing import Any
from uuid import UUID, uuid4

from app.repositories import building_access as building_access_repository
from app.schemas.buildings import SceneGraphMutation, SceneGraphMutationRequest
from app.services.building_access_service import (
    BuildingAccessDeniedError,
    SceneGraphNotFoundError,
    _decode_graph_json,
    get_accessible_building_for_user,
)


class SceneGraphConflictError(Exception):
    pass


class SceneGraphMutationError(Exception):
    pass


NODE_MUTATION_TYPES = {"ADD_NODE", "UPDATE_NODE", "REMOVE_NODE"}
OVERLAY_MUTATION_TYPES = {"ADD_OVERLAY", "UPDATE_OVERLAY", "REMOVE_OVERLAY"}
DEFAULT_OVERLAY_COLLECTION = "items"


async def mutate_building_scene_graph(
    current_user: dict[str, Any],
    building_id: UUID,
    payload: SceneGraphMutationRequest,
) -> dict[str, Any]:
    building = await get_accessible_building_for_user(current_user, building_id)
    _ensure_mutation_permission(current_user, payload.mutations)

    latest_graph = await building_access_repository.get_latest_scene_graph(building_id)
    if latest_graph is None:
        raise SceneGraphNotFoundError

    if latest_graph["id"] != payload.base_graph_data_id:
        raise SceneGraphConflictError

    scene_graph = _normalize_scene_graph(_decode_graph_json(latest_graph["graph_json"]))
    next_scene_graph = copy.deepcopy(scene_graph)

    for mutation in payload.mutations:
        _apply_mutation(next_scene_graph, mutation)

    graph_row = await building_access_repository.insert_scene_graph_snapshot(
        building_id,
        json.dumps(next_scene_graph, ensure_ascii=False),
    )
    if graph_row is None:
        raise SceneGraphMutationError

    return {
        "building_id": building["id"],
        "building_name": building["name"],
        "graph_data_id": graph_row["id"],
        "previous_graph_data_id": latest_graph["id"],
        "created_at": graph_row["created_at"],
        "scene_graph": _decode_graph_json(graph_row["graph_json"]),
    }


def _ensure_mutation_permission(
    current_user: dict[str, Any],
    mutations: list[SceneGraphMutation],
) -> None:
    job = current_user.get("job")
    mutation_types = {mutation.type for mutation in mutations}

    if mutation_types & NODE_MUTATION_TYPES and job != "FACILITY_MANAGER":
        raise BuildingAccessDeniedError

    if mutation_types <= OVERLAY_MUTATION_TYPES and job in {
        "FACILITY_MANAGER",
        "FIREFIGHTER",
    }:
        return

    if mutation_types & OVERLAY_MUTATION_TYPES and job not in {
        "FACILITY_MANAGER",
        "FIREFIGHTER",
    }:
        raise BuildingAccessDeniedError


def _normalize_scene_graph(scene_graph: Any) -> dict[str, Any]:
    if not isinstance(scene_graph, dict):
        raise SceneGraphMutationError

    scene_graph.setdefault("version", "1.0")
    scene_graph.setdefault("nodes", [])
    scene_graph.setdefault("edges", [])
    scene_graph.setdefault("assets", {})
    scene_graph.setdefault("overlays", {})

    if not isinstance(scene_graph["nodes"], list):
        raise SceneGraphMutationError
    if not isinstance(scene_graph["edges"], list):
        raise SceneGraphMutationError
    if not isinstance(scene_graph["overlays"], dict):
        raise SceneGraphMutationError

    return scene_graph


def _apply_mutation(scene_graph: dict[str, Any], mutation: SceneGraphMutation) -> None:
    if mutation.type == "ADD_NODE":
        _add_node(scene_graph, mutation.payload["node"])
    elif mutation.type == "UPDATE_NODE":
        _update_node(scene_graph, mutation.payload["node"])
    elif mutation.type == "REMOVE_NODE":
        _remove_node(scene_graph, str(mutation.payload["node_id"]))
    elif mutation.type == "ADD_OVERLAY":
        _add_overlay(scene_graph, mutation.payload)
    elif mutation.type == "UPDATE_OVERLAY":
        _update_overlay(scene_graph, mutation.payload)
    elif mutation.type == "REMOVE_OVERLAY":
        _remove_overlay(scene_graph, mutation.payload)
    else:
        raise SceneGraphMutationError


def _add_node(scene_graph: dict[str, Any], node: dict[str, Any]) -> None:
    node.setdefault("id", str(uuid4()))
    node_id = str(node["id"])
    if _find_by_id(scene_graph["nodes"], node_id) is not None:
        raise SceneGraphMutationError

    scene_graph["nodes"].append(node)


def _update_node(scene_graph: dict[str, Any], node_patch: dict[str, Any]) -> None:
    node_id = str(node_patch["id"])
    node = _find_by_id(scene_graph["nodes"], node_id)
    if node is None:
        raise SceneGraphMutationError

    node.update(node_patch)
    node["id"] = node_id


def _remove_node(scene_graph: dict[str, Any], node_id: str) -> None:
    original_length = len(scene_graph["nodes"])
    scene_graph["nodes"] = [
        node for node in scene_graph["nodes"] if str(node.get("id")) != node_id
    ]
    if len(scene_graph["nodes"]) == original_length:
        raise SceneGraphMutationError

    scene_graph["edges"] = [
        edge
        for edge in scene_graph["edges"]
        if str(edge.get("source")) != node_id and str(edge.get("target")) != node_id
    ]


def _add_overlay(scene_graph: dict[str, Any], payload: dict[str, Any]) -> None:
    collection = _overlay_collection(scene_graph, payload)
    overlay = payload["overlay"]
    overlay.setdefault("id", str(uuid4()))
    overlay_id = str(overlay["id"])
    if _find_by_id(collection, overlay_id) is not None:
        raise SceneGraphMutationError

    collection.append(overlay)


def _update_overlay(scene_graph: dict[str, Any], payload: dict[str, Any]) -> None:
    collection = _overlay_collection(scene_graph, payload)
    overlay_patch = payload["overlay"]
    overlay_id = str(overlay_patch["id"])
    overlay = _find_by_id(collection, overlay_id)
    if overlay is None:
        raise SceneGraphMutationError

    overlay.update(overlay_patch)
    overlay["id"] = overlay_id


def _remove_overlay(scene_graph: dict[str, Any], payload: dict[str, Any]) -> None:
    collection_name = _overlay_collection_name(payload)
    overlays = scene_graph["overlays"]
    collection = overlays.setdefault(collection_name, [])
    if not isinstance(collection, list):
        raise SceneGraphMutationError

    overlay_id = str(payload["overlay_id"])
    original_length = len(collection)
    overlays[collection_name] = [
        overlay for overlay in collection if str(overlay.get("id")) != overlay_id
    ]

    if len(overlays[collection_name]) == original_length:
        raise SceneGraphMutationError


def _overlay_collection(
    scene_graph: dict[str, Any],
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    collection_name = _overlay_collection_name(payload)
    collection = scene_graph["overlays"].setdefault(collection_name, [])
    if not isinstance(collection, list):
        raise SceneGraphMutationError

    return collection


def _overlay_collection_name(payload: dict[str, Any]) -> str:
    return str(payload.get("overlay_type") or DEFAULT_OVERLAY_COLLECTION)


def _find_by_id(items: list[dict[str, Any]], item_id: str) -> dict[str, Any] | None:
    for item in items:
        if str(item.get("id")) == item_id:
            return item

    return None
