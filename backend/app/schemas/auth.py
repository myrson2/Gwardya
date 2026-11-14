from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import User

MAX_PASSWORD_BYTES = 72


def _reject_over_72_bytes(value: str) -> str:
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("Password must be at most 72 UTF-8 bytes")
    return value


class RegisterRequest(BaseModel):
    # extra="ignore" is the documented behaviour: a client-supplied role,
    # roles, permissions, or is_superuser field is silently dropped, and the
    # service always assigns the customer role (Constitution §2.4).
    model_config = ConfigDict(extra="ignore")

    email: str
    password: str = Field(min_length=8)
    full_name: str = Field(default="", max_length=120)

    _password_bytes = field_validator("password")(_reject_over_72_bytes)


class LoginRequest(BaseModel):
    email: str
    password: str

    _password_bytes = field_validator("password")(_reject_over_72_bytes)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    roles: list[str]
    permissions: list[str]

    @classmethod
    def from_user(cls, user: User) -> UserResponse:
        """Requires roles and their permissions to be eager-loaded."""
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            roles=sorted(user.role_names),
            permissions=sorted(user.permission_codes),
        )
