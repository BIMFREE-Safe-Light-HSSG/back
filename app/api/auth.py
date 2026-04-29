from fastapi import APIRouter, HTTPException, status

from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    SignupRequest,
    SignupResponse,
    UserResponse,
)
from app.services.auth_service import (
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
        user = await login(payload)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        ) from exc

    return LoginResponse(
        message="Login completed successfully.",
        user=UserResponse(**user),
    )
