from typing import Any
from uuid import UUID

import asyncpg

from app.core.database import db


class DuplicateEmailError(Exception):
    pass


USER_PROFILE_SELECT = """
SELECT
    u.id,
    u.email,
    u.password_hash,
    u.name,
    u.job,
    u.jurisdiction_code,
    u.jurisdiction_name,
    u.created_at
FROM users u
"""


async def get_profile_by_id(user_id: UUID) -> dict[str, Any] | None:
    return await db.fetch_one(
        f"""
        {USER_PROFILE_SELECT}
        WHERE u.id = $1
        """,
        user_id,
    )


async def get_profile_by_email(email: str) -> dict[str, Any] | None:
    return await db.fetch_one(
        f"""
        {USER_PROFILE_SELECT}
        WHERE u.email = $1
        """,
        email,
    )


async def email_exists(email: str) -> bool:
    existing_user = await db.fetch_one(
        "SELECT id FROM users WHERE email = $1",
        email,
    )
    return existing_user is not None


async def create_user_profile(
    *,
    email: str,
    password_hash: str,
    name: str | None,
    job: str,
    jurisdiction: dict[str, Any] | None,
) -> dict[str, Any] | None:
    jurisdiction_code = jurisdiction["district_code"] if jurisdiction else None
    jurisdiction_name = jurisdiction["district_name"] if jurisdiction else None
    async with db.acquire() as conn:
        async with conn.transaction():
            try:
                user = await conn.fetchrow(
                    """
                    INSERT INTO users (
                        email,
                        password_hash,
                        name,
                        job,
                        jurisdiction_code,
                        jurisdiction_name
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    email,
                    password_hash,
                    name,
                    job,
                    jurisdiction_code,
                    jurisdiction_name,
                )
            except asyncpg.UniqueViolationError as exc:
                raise DuplicateEmailError from exc

            if user is None:
                return None

            profile = await conn.fetchrow(
                f"""
                {USER_PROFILE_SELECT}
                WHERE u.id = $1
                """,
                user["id"],
            )

    return dict(profile) if profile else None
