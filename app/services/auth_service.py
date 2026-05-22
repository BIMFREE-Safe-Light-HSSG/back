import hashlib
import logging
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from jose import JWTError, jwt

from app.repositories import users as users_repository
from app.repositories.users import DuplicateEmailError
from app.schemas.auth import JobType, LoginRequest, SignupRequest


HASH_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000
JWT_ALGORITHM = "HS256"
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
DEFAULT_JWT_SECRET_KEY = "change-this-jwt-secret-key"
logger = logging.getLogger("app.services.auth")


class EmailAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class AuthConfigurationError(Exception):
    pass


class InvalidAccessTokenError(Exception):
    pass


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
        }
    else:
        user["jurisdiction"] = None

    return user


async def _resolve_jurisdiction(payload: SignupRequest) -> dict[str, Any]:
    if payload.jurisdiction is None:
        raise RuntimeError("jurisdiction is required.")

    return {
        "district_code": payload.jurisdiction.code,
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

    user = await users_repository.get_profile_by_id(user_id)
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
    if await users_repository.email_exists(payload.email):
        logger.warning("signup_rejected reason=duplicate_email job=%s", payload.job.value)
        raise EmailAlreadyExistsError

    password_hash = hash_password(payload.password)
    jurisdiction = None
    if payload.job == JobType.FIREFIGHTER:
        jurisdiction = await _resolve_jurisdiction(payload)

    try:
        profile = await users_repository.create_user_profile(
            email=payload.email,
            password_hash=password_hash,
            name=payload.name,
            job=payload.job.value,
            jurisdiction=jurisdiction,
        )
    except DuplicateEmailError as exc:
        raise EmailAlreadyExistsError from exc

    if profile is None:
        raise RuntimeError("Failed to load created user.")

    user_profile = _user_profile_from_row(profile)
    logger.info(
        "signup_completed user_id=%s job=%s",
        user_profile["id"],
        user_profile.get("job"),
    )
    return user_profile


async def login(payload: LoginRequest) -> dict[str, Any]:
    user = await users_repository.get_profile_by_email(payload.email)

    if user is None or not verify_password(payload.password, user["password_hash"]):
        logger.warning("login_rejected reason=invalid_credentials")
        raise InvalidCredentialsError

    user = _user_profile_from_row(user)
    logger.info("login_completed user_id=%s job=%s", user["id"], user.get("job"))
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "user": user,
    }
