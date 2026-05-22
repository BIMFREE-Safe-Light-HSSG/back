from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class JobType(StrEnum):
    FACILITY_MANAGER = "FACILITY_MANAGER"
    FIREFIGHTER = "FIREFIGHTER"


class JurisdictionRequest(BaseModel):
    code: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)

    @field_validator("code", "name")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("jurisdiction code and name are required")
        return text


class JurisdictionResponse(BaseModel):
    code: str | None
    name: str | None


class SignupRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    name: str | None = Field(default=None, max_length=100)
    job: JobType
    jurisdiction: JurisdictionRequest | None = None

    @model_validator(mode="after")
    def validate_job_fields(self) -> "SignupRequest":
        if self.job == JobType.FIREFIGHTER and self.jurisdiction is None:
            raise ValueError("jurisdiction is required for firefighters")

        return self

    @field_validator("job", mode="before")
    @classmethod
    def normalize_job(cls, value: object) -> JobType:
        if isinstance(value, JobType):
            return value

        raw_value = str(value).strip()
        normalized_value = raw_value.upper().replace("-", "_").replace(" ", "_")
        job_map = {
            "FACILITY_MANAGER": JobType.FACILITY_MANAGER,
            "시설관리자": JobType.FACILITY_MANAGER,
            "FIREFIGHTER": JobType.FIREFIGHTER,
            "소방대원": JobType.FIREFIGHTER,
        }

        if normalized_value in job_map:
            return job_map[normalized_value]
        if raw_value in job_map:
            return job_map[raw_value]

        raise ValueError("job must be FACILITY_MANAGER or FIREFIGHTER")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        local_part, separator, domain = email.partition("@")

        if not local_part or separator != "@" or "." not in domain:
            raise ValueError("valid email is required")

        return email

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None

        name = value.strip()
        return name or None


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        local_part, separator, domain = email.partition("@")

        if not local_part or separator != "@" or "." not in domain:
            raise ValueError("valid email is required")

        return email


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str | None
    job: JobType | None = None
    jurisdiction: JurisdictionResponse | None = None
    created_at: datetime


class SignupResponse(BaseModel):
    message: str
    user: UserResponse


class LoginResponse(BaseModel):
    message: str
    access_token: str
    token_type: str
    user: UserResponse
