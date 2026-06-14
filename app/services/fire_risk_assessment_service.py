import copy
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.integrations.gemini import assess_scene_graph_fire_risk
from app.schemas.buildings import SceneGraphMutationRequest
from app.schemas.fire_risk_assessments import (
    FireRiskFinding,
    GeminiFireRiskAssessment,
)
from app.services.building_access_service import get_building_scene_graph
from app.services.scene_graph_mutation_service import mutate_building_scene_graph


FIRE_RISK_OVERLAY_TYPE = "fire_risks"
FIRE_RISK_OVERLAY_SOURCE = "GEMINI_FIRE_RISK_ASSESSMENT"
NODE_REFERENCE_FIELDS = ("id", "node_id", "name", "label")
logger = logging.getLogger("app.services.fire_risk_assessment")


class FireRiskSceneGraphError(Exception):
    pass


class FireRiskAssessmentResponseError(Exception):
    pass


def _scene_graph_for_assessment(scene_graph: Any) -> dict[str, Any]:
    if not isinstance(scene_graph, dict):
        raise FireRiskSceneGraphError

    assessment_graph = copy.deepcopy(scene_graph)
    nodes = assessment_graph.get("nodes")
    if not isinstance(nodes, list):
        raise FireRiskSceneGraphError

    overlays = assessment_graph.get("overlays")
    if overlays is None:
        assessment_graph["overlays"] = {}
    elif not isinstance(overlays, dict):
        raise FireRiskSceneGraphError
    else:
        overlays.pop(FIRE_RISK_OVERLAY_TYPE, None)

    return assessment_graph


def _normalized_node_reference(value: Any) -> str:
    return str(value).strip().casefold()


def _node_reference_map(scene_graph: dict[str, Any]) -> dict[str, str]:
    references: dict[str, set[str]] = {}

    for node in scene_graph["nodes"]:
        if not isinstance(node, dict) or node.get("id") is None:
            continue

        node_id = str(node["id"]).strip()
        if not node_id:
            continue

        values = [node.get(field) for field in NODE_REFERENCE_FIELDS]
        metadata = node.get("metadata")
        if isinstance(metadata, dict):
            values.extend(metadata.get(field) for field in NODE_REFERENCE_FIELDS)

        for value in values:
            if value is None:
                continue

            reference = _normalized_node_reference(value)
            if reference:
                references.setdefault(reference, set()).add(node_id)

    node_reference_map = {
        reference: next(iter(node_ids))
        for reference, node_ids in references.items()
        if len(node_ids) == 1
    }
    if not node_reference_map:
        raise FireRiskSceneGraphError
    return node_reference_map


def _resolve_findings(
    assessment: GeminiFireRiskAssessment,
    node_reference_map: dict[str, str],
) -> GeminiFireRiskAssessment:
    resolved_findings: list[FireRiskFinding] = []
    invalid_references: list[str] = []

    for finding in assessment.risks:
        target_node_id = node_reference_map.get(
            _normalized_node_reference(finding.target_node_id)
        )
        if target_node_id is None:
            invalid_references.append(finding.target_node_id)
            continue

        resolved_findings.append(
            finding.model_copy(update={"target_node_id": target_node_id})
        )

    if invalid_references:
        logger.warning(
            "fire_risk_unknown_node_references invalid_references=%s",
            invalid_references,
        )
        raise FireRiskAssessmentResponseError

    return assessment.model_copy(update={"risks": resolved_findings})


def _generated_overlay_ids(scene_graph: dict[str, Any]) -> list[str]:
    overlays = scene_graph.get("overlays")
    if not isinstance(overlays, dict):
        return []

    collection = overlays.get(FIRE_RISK_OVERLAY_TYPE)
    if not isinstance(collection, list):
        return []

    return [
        str(overlay["id"])
        for overlay in collection
        if isinstance(overlay, dict)
        and overlay.get("id") is not None
        and overlay.get("source") == FIRE_RISK_OVERLAY_SOURCE
    ]


def _overlay_from_finding(
    finding: FireRiskFinding,
    assessment_id: UUID,
    model: str,
    assessed_at: datetime,
) -> dict[str, Any]:
    return {
        "type": "FIRE_RISK",
        "source": FIRE_RISK_OVERLAY_SOURCE,
        "assessment_id": str(assessment_id),
        "assessment_model": model,
        "assessed_at": assessed_at.isoformat(),
        "target_node_id": finding.target_node_id,
        "severity": finding.severity,
        "category": finding.category,
        "reason": finding.reason,
        "recommendation": finding.recommendation,
        "confidence": finding.confidence,
        "status": "ACTIVE",
    }


def _mutation_request(
    base_graph_data_id: UUID,
    scene_graph: dict[str, Any],
    assessment: GeminiFireRiskAssessment,
    assessment_id: UUID,
    model: str,
    assessed_at: datetime,
) -> SceneGraphMutationRequest | None:
    mutations = [
        {
            "type": "REMOVE_OVERLAY",
            "payload": {
                "overlay_type": FIRE_RISK_OVERLAY_TYPE,
                "overlay_id": overlay_id,
            },
        }
        for overlay_id in _generated_overlay_ids(scene_graph)
    ]
    mutations.extend(
        {
            "type": "ADD_OVERLAY",
            "payload": {
                "overlay_type": FIRE_RISK_OVERLAY_TYPE,
                "overlay": _overlay_from_finding(
                    finding,
                    assessment_id,
                    model,
                    assessed_at,
                ),
            },
        }
        for finding in assessment.risks
    )

    if not mutations:
        return None

    return SceneGraphMutationRequest(
        base_graph_data_id=base_graph_data_id,
        mutations=mutations,
    )


async def assess_building_fire_risk(
    current_user: dict[str, Any],
    building_id: UUID,
) -> dict[str, Any]:
    current_graph = await get_building_scene_graph(current_user, building_id)
    scene_graph = _scene_graph_for_assessment(current_graph["scene_graph"])
    node_reference_map = _node_reference_map(scene_graph)
    model, assessment = await assess_scene_graph_fire_risk(scene_graph)
    assessment = _resolve_findings(assessment, node_reference_map)

    assessment_id = uuid4()
    assessed_at = datetime.now(UTC)
    mutation_request = _mutation_request(
        current_graph["graph_data_id"],
        current_graph["scene_graph"],
        assessment,
        assessment_id,
        model,
        assessed_at,
    )

    if mutation_request is None:
        updated_graph = {
            **current_graph,
            "previous_graph_data_id": None,
        }
        scene_graph_updated = False
    else:
        updated_graph = await mutate_building_scene_graph(
            current_user,
            building_id,
            mutation_request,
        )
        scene_graph_updated = True

    logger.info(
        "fire_risk_assessment_completed assessment_id=%s building_id=%s "
        "graph_data_id=%s model=%s risk_count=%s scene_graph_updated=%s",
        assessment_id,
        building_id,
        updated_graph["graph_data_id"],
        model,
        len(assessment.risks),
        scene_graph_updated,
    )
    return {
        "assessment_id": assessment_id,
        "building_id": updated_graph["building_id"],
        "building_name": updated_graph["building_name"],
        "model": model,
        "summary": assessment.summary,
        "risk_count": len(assessment.risks),
        "findings": assessment.risks,
        "scene_graph_updated": scene_graph_updated,
        "graph_data_id": updated_graph["graph_data_id"],
        "previous_graph_data_id": updated_graph["previous_graph_data_id"],
        "created_at": updated_graph["created_at"],
        "scene_graph": updated_graph["scene_graph"],
    }
