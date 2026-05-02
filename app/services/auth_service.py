import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg
from jose import JWTError, jwt

from app.core.database import db
from app.schemas.auth import LoginRequest, SignupRequest


HASH_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000
JWT_ALGORITHM = "HS256"
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
DEFAULT_JWT_SECRET_KEY = "change-this-jwt-secret-key"


class EmailAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class AuthConfigurationError(Exception):
    pass


class InvalidAccessTokenError(Exception):
    pass


def _access_token_expire_minutes() -> int:
    raw_minutes = os.getenv(
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        str(DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    try:
        minutes = int(raw_minutes)
    except ValueError as exc:
        raise AuthConfigurationError(
            "ACCESS_TOKEN_EXPIRE_MINUTES must be an integer."
        ) from exc

    if minutes < 1:
        raise AuthConfigurationError(
            "ACCESS_TOKEN_EXPIRE_MINUTES must be greater than 0."
        )

    return minutes


def _jwt_secret_key() -> str:
    return os.getenv("JWT_SECRET_KEY", DEFAULT_JWT_SECRET_KEY)


def create_access_token(user: dict[str, Any]) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=_access_token_expire_minutes())
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    return jwt.encode(payload, _jwt_secret_key(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, _jwt_secret_key(), algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise InvalidAccessTokenError from exc

    if not payload.get("sub"):
        raise InvalidAccessTokenError

    return payload


async def get_user_from_access_token(token: str) -> dict[str, Any]:
    payload = decode_access_token(token)

    try:
        user_id = UUID(str(payload["sub"]))
    except (TypeError, ValueError) as exc:
        raise InvalidAccessTokenError from exc

    user = await db.fetch_one(
        """
        SELECT id, email, name, role, created_at
        FROM users
        WHERE id = $1
        """,
        user_id,
    )
    if user is None:
        raise InvalidAccessTokenError

    return user


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
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "user": user,
    }
