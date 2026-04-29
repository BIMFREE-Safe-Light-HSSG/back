from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserBase(BaseModel):
    email: str = Field(..., examples=["user@example.com"])
    name: str | None = Field(default=None, examples=["홍길동"])


class UserCreate(UserBase):
    password: str = Field(..., min_length=4, examples=["password123"])


class UserResponse(UserBase):
    id: UUID
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)