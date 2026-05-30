import hmac
import os
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.auth_service import (
    InvalidAccessTokenError,
    get_user_from_access_token,
)


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return await get_user_from_access_token(credentials.credentials)
    except InvalidAccessTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def verify_model_callback_secret(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected_secret = os.getenv("MODEL_CALLBACK_SECRET")
    if expected_secret is None or not expected_secret.strip():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MODEL_CALLBACK_SECRET is not configured.",
        )

    expected_value = f"Bearer {expected_secret.strip()}"
    if not hmac.compare_digest(authorization or "", expected_value):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid model callback credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
