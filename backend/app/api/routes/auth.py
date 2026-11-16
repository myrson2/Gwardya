"""Authentication routes (M1-2a / M1-2b)."""

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import CurrentUser, SessionDep, verify_origin
from app.core.config import settings
from app.core.security import REFRESH_COOKIE_NAME
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services import auth_service
from app.services.errors import UnauthorizedError

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        path="/auth",
        secure=settings.is_production,
    )


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def register(payload: RegisterRequest, session: SessionDep) -> UserResponse:
    user = await auth_service.register(session, payload)
    return UserResponse.from_user(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, response: Response, session: SessionDep
) -> TokenResponse:
    user = await auth_service.authenticate(session, payload.email, payload.password)
    access_token, refresh_token = await auth_service.issue_session(session, user)
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    session: SessionDep,
    _: None = Depends(verify_origin),
) -> TokenResponse:
    presented = request.cookies.get(REFRESH_COOKIE_NAME)
    if presented is None:
        raise UnauthorizedError("Invalid refresh token")
    _, access_token, replacement = await auth_service.rotate_refresh_token(
        session, presented
    )
    _set_refresh_cookie(response, replacement)
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    session: SessionDep,
    _: None = Depends(verify_origin),
) -> Response:
    presented = request.cookies.get(REFRESH_COOKIE_NAME)
    if presented is not None:
        await auth_service.revoke_refresh_token(session, presented)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/auth")
    return response


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.from_user(user)
