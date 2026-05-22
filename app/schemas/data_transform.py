from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class UploadRequest(BaseModel):
    building_id: UUID
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(
        default="application/octet-stream",
        min_length=1,
        max_length=255,
    )

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        filename = value.strip()
        if not filename:
            raise ValueError("filename is required")
        if "\x00" in filename:
            raise ValueError("filename cannot contain null bytes")

        return filename

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, value: str) -> str:
        content_type = value.strip()
        if not content_type:
            raise ValueError("content_type is required")
        if "\r" in content_type or "\n" in content_type:
            raise ValueError("content_type cannot contain line breaks")

        return content_type


class UploadResponse(BaseModel):
    task_id: UUID
    status: str
    bucket_name: str
    object_key: str
    scan_file_path: str
    upload_url: str
    method: Literal["PUT"]
    expires_in: int
    headers: dict[str, str]


class DataTransformTaskResponse(BaseModel):
    task_id: UUID
    building_id: UUID
    status: str
    progress_percent: int
    error_message: str | None
