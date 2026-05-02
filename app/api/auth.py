from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    SignupRequest,
    SignupResponse,
    UserResponse,
)
from app.services.auth_service import (
    AuthConfigurationError,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    login,
    signup,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup_user(payload: SignupRequest) -> SignupResponse:
    try:
        user = await signup(payload)
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered.",
        ) from exc

    return SignupResponse(
        message="Signup completed successfully.",
        user=UserResponse(**user),
    )


@router.post("/login", response_model=LoginResponse)
async def login_user(payload: LoginRequest) -> LoginResponse:
    try:
        login_result = await login(payload)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        ) from exc
    except AuthConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return LoginResponse(
        message="Login completed successfully.",
        access_token=login_result["access_token"],
        token_type=login_result["token_type"],
        user=UserResponse(**login_result["user"]),
    )


@router.get("/me", response_model=UserResponse)
async def read_me(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> UserResponse:
    return UserResponse(**current_user)
