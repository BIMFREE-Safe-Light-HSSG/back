from fastapi import APIRouter, Query

from app.core.database import db
from app.schemas.auth import UserResponse


router = APIRouter(prefix="/dev", tags=["dev"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[UserResponse]:
    users = await db.fetch_all(
        """
        SELECT id, email, name, role, created_at
        FROM users
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
    )

    return [UserResponse(**user) for user in users]
