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
from app.schemas.auth import JobType, LoginRequest, SignupRequest
from app.services.geo_service import (
    GeoConfigurationError,
    fallback_location_from_address,
    reverse_geocode,
)


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


USER_PROFILE_SELECT = """
SELECT
    u.id,
    u.email,
    u.password_hash,
    u.name,
    u.job,
    u.jurisdiction_code,
    u.jurisdiction_name,
    u.jurisdiction_latitude,
    u.jurisdiction_longitude,
    u.created_at,
    b.id AS building_id,
    b.name AS building_name,
    b.address AS building_address,
    b.latitude AS building_latitude,
    b.longitude AS building_longitude,
    b.district_code AS building_district_code,
    b.district_name AS building_district_name,
    b.region_1depth_name AS building_region_1depth_name,
    b.region_2depth_name AS building_region_2depth_name,
    b.region_3depth_name AS building_region_3depth_name
FROM users u
LEFT JOIN LATERAL (
    SELECT
        id,
        name,
        address,
        latitude,
        longitude,
        district_code,
        district_name,
        region_1depth_name,
        region_2depth_name,
        region_3depth_name
    FROM buildings
    WHERE owner_id = u.id
    ORDER BY created_at DESC
    LIMIT 1
) b ON TRUE
"""


def _user_profile_from_row(row: dict[str, Any]) -> dict[str, Any]:
    user = {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "job": row.get("job"),
        "created_at": row["created_at"],
    }
    if row.get("jurisdiction_code") or row.get("jurisdiction_name"):
        user["jurisdiction"] = {
            "code": row.get("jurisdiction_code"),
            "name": row.get("jurisdiction_name"),
            "latitude": row.get("jurisdiction_latitude"),
            "longitude": row.get("jurisdiction_longitude"),
        }
    else:
        user["jurisdiction"] = None

    if (
        row.get("building_id") is not None
        and row.get("building_latitude") is not None
        and row.get("building_longitude") is not None
    ):
        user["building"] = {
            "id": row["building_id"],
            "name": row["building_name"],
            "address": row["building_address"],
            "latitude": row["building_latitude"],
            "longitude": row["building_longitude"],
            "district_code": row["building_district_code"],
            "district_name": row["building_district_name"],
            "region_1depth_name": row["building_region_1depth_name"],
            "region_2depth_name": row["building_region_2depth_name"],
            "region_3depth_name": row["building_region_3depth_name"],
        }
    else:
        user["building"] = None

    return user


async def _resolve_building_location(payload: SignupRequest) -> dict[str, Any]:
    if payload.building_location is None:
        raise RuntimeError("building_location is required.")

    try:
        location = await reverse_geocode(
            payload.building_location.latitude,
            payload.building_location.longitude,
        )
    except GeoConfigurationError:
        if not payload.building_location.address:
            raise

        return fallback_location_from_address(
            payload.building_location.latitude,
            payload.building_location.longitude,
            payload.building_location.address,
        )

    if location["address"] is None and payload.building_location.address:
        location["address"] = payload.building_location.address

    return location


async def _resolve_jurisdiction(payload: SignupRequest) -> dict[str, Any]:
    if payload.jurisdiction is None:
        raise RuntimeError("jurisdiction is required.")

    if payload.jurisdiction.latitude is not None and payload.jurisdiction.longitude is not None:
        return await reverse_geocode(
            payload.jurisdiction.latitude,
            payload.jurisdiction.longitude,
        )

    if not payload.jurisdiction.name:
        raise RuntimeError("jurisdiction name is required when coordinates are omitted.")

    return {
        "latitude": None,
        "longitude": None,
        "district_code": payload.jurisdiction.code or payload.jurisdiction.name,
        "district_name": payload.jurisdiction.name,
    }


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
        f"""
        {USER_PROFILE_SELECT}
        WHERE u.id = $1
        """,
        user_id,
    )
    if user is None:
        raise InvalidAccessTokenError

    return _user_profile_from_row(user)


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
    building_location = None
    jurisdiction = None
    if payload.job == JobType.FACILITY_MANAGER:
        building_location = await _resolve_building_location(payload)
    if payload.job == JobType.FIREFIGHTER:
        jurisdiction = await _resolve_jurisdiction(payload)

    jurisdiction_code = jurisdiction["district_code"] if jurisdiction else None
    jurisdiction_name = jurisdiction["district_name"] if jurisdiction else None
    jurisdiction_latitude = jurisdiction["latitude"] if jurisdiction else None
    jurisdiction_longitude = jurisdiction["longitude"] if jurisdiction else None

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
                        jurisdiction_name,
                        jurisdiction_latitude,
                        jurisdiction_longitude
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id
                    """,
                    payload.email,
                    password_hash,
                    payload.name,
                    payload.job.value,
                    jurisdiction_code,
                    jurisdiction_name,
                    jurisdiction_latitude,
                    jurisdiction_longitude,
                )
            except asyncpg.UniqueViolationError as exc:
                raise EmailAlreadyExistsError from exc

            if user is None:
                raise RuntimeError("Failed to create user.")

            if payload.job == JobType.FACILITY_MANAGER and building_location is not None:
                building_name = (
                    building_location["building_name"]
                    or building_location["address"]
                    or "Registered building"
                )
                await conn.fetchrow(
                    """
                    INSERT INTO buildings (
                        owner_id,
                        name,
                        address,
                        latitude,
                        longitude,
                        district_code,
                        district_name,
                        region_1depth_name,
                        region_2depth_name,
                        region_3depth_name
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    RETURNING id
                    """,
                    user["id"],
                    building_name,
                    building_location["address"],
                    building_location["latitude"],
                    building_location["longitude"],
                    building_location["district_code"],
                    building_location["district_name"],
                    building_location["region_1depth_name"],
                    building_location["region_2depth_name"],
                    building_location["region_3depth_name"],
                )

            profile = await conn.fetchrow(
                f"""
                {USER_PROFILE_SELECT}
                WHERE u.id = $1
                """,
                user["id"],
            )

    if profile is None:
        raise RuntimeError("Failed to load created user.")

    return _user_profile_from_row(dict(profile))


async def login(payload: LoginRequest) -> dict[str, Any]:
    user = await db.fetch_one(
        f"""
        {USER_PROFILE_SELECT}
        WHERE u.email = $1
        """,
        payload.email,
    )

    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise InvalidCredentialsError

    user = _user_profile_from_row(user)
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "user": user,
    }
