"""Identity resolution and authorization gates (tech-stack layer 2).

``get_current_user`` and ``verify_origin`` are boilerplate (M1-2). The two guards are
the **M1-3 exercise**: they are the only place in the codebase where an access decision
is made.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.enums import PermissionCode
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models import Role, User

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False)

STUDENT_TASK = (
    "M1-3 student task: implement the permission check in app/api/deps.py. "
    "See docs/M1-3-authorization-task.md."
)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ] = None,
) -> User:
    """Decode the access token, then load the user *and their grants* from MySQL.

    The token carries no roles or permissions, so a role change is visible on the very
    next request (no reissue, no stale grants). The eager loads are mandatory because
    every relationship is ``lazy="raise"``.
    """
    if credentials is None:
        raise _unauthorized()
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(str(payload["sub"]))
    except (InvalidTokenError, KeyError, ValueError) as exc:
        raise _unauthorized() from exc

    user = await session.scalar(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles).selectinload(Role.permissions))
    )
    if user is None:
        raise _unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def verify_origin(request: Request) -> None:
    """POST /auth/refresh and /auth/logout accept only the configured frontend origin."""
    if request.headers.get("origin") != settings.frontend_origin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin not allowed",
        )


def require_permission(
    code: PermissionCode | str,
) -> Callable[..., Awaitable[User]]:
    """Guard dependency factory: allow the request only if the user holds ``code``.

    Contract
    --------
    * Runs *after* ``get_current_user``; identity failures stay 401.
    * A valid identity without the permission is **403**, never 404/401.
    * Read the permission from ``user.permission_codes`` — resolved from MySQL by
      ``get_current_user`` on this request.
    * Never inspect role names, never decode the token again, never trust the client.
    * Return the same ``User`` so handlers can use it (and so ``Depends`` can chain).

    Roughly three lines: check membership, raise ``HTTPException(403, ...)``, return.
    """

    async def guard(user: User = Depends(get_current_user)) -> User:
        raise NotImplementedError(STUDENT_TASK)

    return guard


def require_any_permission(
    *codes: PermissionCode | str,
) -> Callable[..., Awaitable[User]]:
    """Guard factory with **any-of** semantics.

    Ticket listing needs both ``ticket:read_own`` and ``ticket:read_all`` because the
    catalog gives each role only one of them. Implement it with the same rules as
    ``require_permission``; only the membership test differs (``isdisjoint``).
    """

    async def guard(user: User = Depends(get_current_user)) -> User:
        raise NotImplementedError(STUDENT_TASK)

    return guard
