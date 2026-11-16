"""Password hashing and access-token primitives (Constitution §2.1, §2.2)."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from jwt import InvalidTokenError
from pwdlib.hashers.bcrypt import BcryptHasher
from starlette.concurrency import run_in_threadpool

from app.core.config import settings

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"
REFRESH_COOKIE_NAME = "refresh_token"

# bcrypt cost 12, explicitly selected. PasswordHash.recommended() may pick Argon2,
# which would violate the constitution's bcrypt rule.
_bcrypt = BcryptHasher(rounds=12)


def utcnow() -> datetime:
    """Naive UTC — the shape MySQL DATETIME returns.

    MySQL drops tzinfo, so comparing an aware datetime against a stored value raises
    TypeError. All persistence timestamps in this project are naive UTC by convention.
    """
    return datetime.now(UTC).replace(tzinfo=None)


async def hash_password(password: str) -> str:
    """CPU-bound crypto never runs on the event loop (Constitution §2.2)."""
    return await run_in_threadpool(_bcrypt.hash, password)


async def verify_password(password: str, hashed_password: str) -> bool:
    return await run_in_threadpool(_bcrypt.verify, password, hashed_password)


def create_access_token(user_id: int) -> str:
    """15-minute JWT carrying identity only — never roles or permissions."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "typ": ACCESS_TOKEN_TYPE,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, object]:
    """Validate signature, expiry, and token type. Raises InvalidTokenError."""
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["sub", "iat", "exp", "typ"]},
    )
    if payload.get("typ") != ACCESS_TOKEN_TYPE:
        raise InvalidTokenError("Not an access token")
    return payload


def generate_refresh_token() -> str:
    """256 bits of entropy, URL-safe. Only the hash is stored."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
