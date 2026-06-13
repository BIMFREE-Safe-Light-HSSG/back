from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.integrations.gemini import (
    GeminiAPIError,
    GeminiConfigurationError,
    GeminiResponseError,
)
from app.schemas.fire_risk_assessments import FireRiskAssessmentResponse
from app.services.building_access_service import (
    BuildingAccessDeniedError,
    BuildingNotFoundError,
    SceneGraphNotFoundError,
)
from app.services.fire_risk_assessment_service import (
    FireRiskAssessmentResponseError,
    FireRiskSceneGraphError,
    assess_building_fire_risk,
)
from app.services.scene_graph_mutation_service import (
    SceneGraphConflictError,
    SceneGraphMutationError,
)


router = APIRouter(prefix="/buildings", tags=["fire-risk-assessments"])


@router.post(
    "/{building_id}/fire-risk-assessments",
    response_model=FireRiskAssessmentResponse,
)
async def create_fire_risk_assessment(
    building_id: UUID,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> FireRiskAssessmentResponse:
    try:
        assessment = await assess_building_fire_risk(current_user, building_id)
    except BuildingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Building not found.",
        ) from exc
    except BuildingAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to assess this building.",
        ) from exc
    except SceneGraphNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scene graph not found for this building.",
        ) from exc
    except SceneGraphConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Scene graph changed during assessment. Retry with the latest graph.",
        ) from exc
    except GeminiConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except (GeminiAPIError, GeminiResponseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except FireRiskAssessmentResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini returned a risk for an unknown scene-graph node.",
        ) from exc
    except (FireRiskSceneGraphError, SceneGraphMutationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Scene graph cannot be assessed or updated.",
        ) from exc

    return FireRiskAssessmentResponse(**assessment)
