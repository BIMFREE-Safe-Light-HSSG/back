from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TransformTaskStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TransformTaskCreate(BaseModel):
    building_id: UUID
    input_data_path: str | None = Field(
        default=None,
        examples=["uploads/buildings/001/raw_scan.zip"],
    )


class TransformTaskUpdateStatus(BaseModel):
    status: TransformTaskStatus
    error_message: str | None = None


class TransformTaskResponse(BaseModel):
    id: UUID
    building_id: UUID
    status: TransformTaskStatus
    input_data_path: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransformRequestResponse(BaseModel):
    message: str = "Data transform request created successfully"
    task: TransformTaskResponse