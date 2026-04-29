import hashlib
import hmac
import secrets
from typing import Any

import asyncpg

from app.core.database import db
from app.schemas.auth import LoginRequest, SignupRequest


HASH_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000


class EmailAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        PBKDF2_ITERATIONS,
    )
    return f"{HASH_ALGORITHM}${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, stored_digest = password_hash.split("$", 3)
        if algorithm != HASH_ALGORITHM:
            return False

        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("ascii"),
            int(iterations),
        )
    except (TypeError, ValueError):
        return False

    return hmac.compare_digest(digest.hex(), stored_digest)


async def signup(payload: SignupRequest) -> dict[str, Any]:
    existing_user = await db.fetch_one(
        "SELECT id FROM users WHERE email = $1",
        payload.email,
    )
    if existing_user is not None:
        raise EmailAlreadyExistsError

    password_hash = hash_password(payload.password)

    try:
        user = await db.fetch_one(
            """
            INSERT INTO users (email, password_hash, name)
            VALUES ($1, $2, $3)
            RETURNING id, email, name, role, created_at
            """,
            payload.email,
            password_hash,
            payload.name,
        )
    except asyncpg.UniqueViolationError as exc:
        raise EmailAlreadyExistsError from exc

    if user is None:
        raise RuntimeError("Failed to create user.")

    return user


async def login(payload: LoginRequest) -> dict[str, Any]:
    user = await db.fetch_one(
        """
        SELECT id, email, password_hash, name, role, created_at
        FROM users
        WHERE email = $1
        """,
        payload.email,
    )

    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise InvalidCredentialsError

    user.pop("password_hash", None)
    return user
