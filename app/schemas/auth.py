from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class JobType(StrEnum):
    FACILITY_MANAGER = "FACILITY_MANAGER"
    FIREFIGHTER = "FIREFIGHTER"


class BuildingLocationRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("address")
    @classmethod
    def normalize_address(cls, value: str | None) -> str | None:
        if value is None:
            return None

        address = value.strip()
        return address or None


class JurisdictionRequest(BaseModel):
    code: str | None = Field(default=None, max_length=100)
    name: str | None = Field(default=None, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_jurisdiction_source(self) -> "JurisdictionRequest":
        has_coordinates = self.latitude is not None and self.longitude is not None
        has_text = self.code is not None or self.name is not None

        if not has_coordinates and not has_text:
            raise ValueError("jurisdiction requires coordinates or code/name")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("jurisdiction latitude and longitude must be sent together")

        return self

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return None

        text = value.strip()
        return text or None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None

        name = value.strip()
        return name or None


class JurisdictionResponse(BaseModel):
    code: str | None
    name: str | None
    latitude: float | None = None
    longitude: float | None = None


class BuildingLocationResponse(BaseModel):
    id: UUID
    name: str
    address: str | None
    latitude: float
    longitude: float
    district_code: str | None = None
    district_name: str | None = None
    region_1depth_name: str | None = None
    region_2depth_name: str | None = None
    region_3depth_name: str | None = None


class SignupRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    name: str | None = Field(default=None, max_length=100)
    job: JobType
    building_location: BuildingLocationRequest | None = None
    jurisdiction: JurisdictionRequest | None = None

    @model_validator(mode="after")
    def validate_job_fields(self) -> "SignupRequest":
        if self.job == JobType.FACILITY_MANAGER and self.building_location is None:
            raise ValueError("building_location is required for facility managers")
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
    building: BuildingLocationResponse | None = None


class SignupResponse(BaseModel):
    message: str
    user: UserResponse


class LoginResponse(BaseModel):
    message: str
    access_token: str
    token_type: str
    user: UserResponse
