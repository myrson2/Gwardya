"""Registration, login, and refresh-token rotation.

Constitution §2.1/§2.4/§2.2 are implemented here; the *authorization* decisions live
in ``app.api.deps`` and ``app.services.ticket_scope``.
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.enums import RoleName
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    utcnow,
    verify_password,
)
from app.models import RefreshToken, Role, User
from app.schemas.auth import RegisterRequest
from app.services.errors import (
    ConflictError,
    RefreshReuseError,
    SetupError,
    UnauthorizedError,
)


def normalize_email(email: str) -> str:
    """MySQL's collation is case-insensitive; normalise before storing/looking up."""
    return email.strip().lower()


async def register(session: AsyncSession, payload: RegisterRequest) -> User:
    """Create a customer. Any role-ish field in the payload has already been ignored."""
    email = normalize_email(str(payload.email))
    if await session.scalar(select(User.id).where(User.email == email)) is not None:
        raise ConflictError("Email already registered")

    role = await session.scalar(
        select(Role)
        .where(Role.name == RoleName.CUSTOMER)
        .options(selectinload(Role.permissions))
    )
    if role is None:
        raise SetupError("Database is not seeded. Run: uv run python -m app.db.seed")

    user = User(
        email=email,
        full_name=payload.full_name,
        hashed_password=await hash_password(payload.password),
    )
    user.roles = [role]
    session.add(user)
    await session.flush()
    return user


async def authenticate(
    session: AsyncSession, email: str, password: str
) -> User:
    """Generic 401 for both unknown email and wrong password (no enumeration)."""
    user = await session.scalar(
        select(User).where(User.email == normalize_email(email))
    )
    if user is None:
        raise UnauthorizedError("Invalid email or password")
    if not await verify_password(password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password")
    return user


async def issue_session(session: AsyncSession, user: User) -> tuple[str, str]:
    """Return (access_token, refresh_plaintext) and persist the refresh hash."""
    plaintext = generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(plaintext),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
        )
    )
    await session.flush()
    return create_access_token(user.id), plaintext


async def _revoke_descendants(
    session: AsyncSession, token: RefreshToken, now: datetime
) -> None:
    """Walk the rotation chain forward, revoking every still-active replacement."""
    node = token
    while node.replaced_by_id is not None:
        child = await session.get(RefreshToken, node.replaced_by_id)
        if child is None:
            break
        if child.revoked_at is None:
            child.revoked_at = now
        node = child
    await session.flush()


async def rotate_refresh_token(
    session: AsyncSession, presented: str
) -> tuple[User, str, str]:
    """Rotate: revoke the presented token, issue a replacement, reset the cookie."""
    record = await session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(presented)
        )
    )
    if record is None:
        raise UnauthorizedError("Invalid refresh token")

    now = utcnow()
    if record.revoked_at is not None:
        # Reuse of an already-rotated token: assume theft and kill the whole family.
        await _revoke_descendants(session, record, now)
        raise RefreshReuseError("Refresh token reuse detected; please log in again")

    if record.expires_at <= now:
        record.revoked_at = now
        raise UnauthorizedError("Refresh token expired")

    user = await session.get(User, record.user_id)
    if user is None:
        raise UnauthorizedError("Invalid refresh token")

    plaintext = generate_refresh_token()
    replacement = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(plaintext),
        expires_at=now + timedelta(days=settings.refresh_token_days),
    )
    session.add(replacement)
    await session.flush()

    record.revoked_at = now
    record.replaced_by_id = replacement.id
    await session.flush()
    return user, create_access_token(user.id), plaintext


async def revoke_refresh_token(session: AsyncSession, presented: str) -> None:
    """Logout: revoke the presented token if it exists. Idempotent."""
    record = await session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(presented)
        )
    )
    if record is not None and record.revoked_at is None:
        record.revoked_at = utcnow()
        await session.flush()
