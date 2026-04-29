from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SignupRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    name: str | None = Field(default=None, max_length=100)

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
    role: str
    created_at: datetime


class SignupResponse(BaseModel):
    message: str
    user: UserResponse


class LoginResponse(BaseModel):
    message: str
    user: UserResponse
