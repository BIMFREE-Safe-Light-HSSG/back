from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


FireRiskSeverity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class FireRiskFinding(BaseModel):
    target_node_id: str = Field(..., min_length=1)
    severity: FireRiskSeverity
    category: str = Field(..., min_length=1, max_length=100)
    reason: str = Field(..., min_length=1, max_length=1000)
    recommendation: str = Field(..., min_length=1, max_length=1000)
    confidence: float = Field(..., ge=0, le=1)

    @field_validator(
        "target_node_id",
        "category",
        "reason",
        "recommendation",
    )
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("value is required")
        return text


class GeminiFireRiskAssessment(BaseModel):
    summary: str = Field(..., min_length=1, max_length=2000)
    risks: list[FireRiskFinding] = Field(default_factory=list, max_length=100)

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str) -> str:
        summary = value.strip()
        if not summary:
            raise ValueError("summary is required")
        return summary


class FireRiskAssessmentResponse(BaseModel):
    assessment_id: UUID
    building_id: UUID
    building_name: str
    model: str
    summary: str
    risk_count: int
    findings: list[FireRiskFinding]
    scene_graph_updated: bool
    graph_data_id: UUID
    previous_graph_data_id: UUID | None
    created_at: datetime
    scene_graph: Any
