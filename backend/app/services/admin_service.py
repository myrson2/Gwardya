"""Admin queries and role assignment (M1-5)."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import RoleName
from app.models import Permission, Role, User
from app.services.errors import NotFoundError


async def list_users(session: AsyncSession) -> Sequence[User]:
    stmt = (
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .order_by(User.id)
    )
    return (await session.scalars(stmt)).all()


async def list_roles(session: AsyncSession) -> Sequence[Role]:
    stmt = (
        select(Role)
        .options(selectinload(Role.permissions))
        .order_by(Role.name)
    )
    return (await session.scalars(stmt)).all()


async def list_permissions(session: AsyncSession) -> Sequence[Permission]:
    return (await session.scalars(select(Permission).order_by(Permission.code))).all()


async def assign_roles(
    session: AsyncSession, user_id: int, role_names: Sequence[RoleName]
) -> User:
    """Replace the user's role set. The next request resolves the new grants from DB."""
    user = await session.scalar(
        select(User).where(User.id == user_id).options(selectinload(User.roles))
    )
    if user is None:
        raise NotFoundError("User not found")

    roles = (
        await session.scalars(
            select(Role)
            .where(Role.name.in_([str(name) for name in role_names]))
            .options(selectinload(Role.permissions))
        )
    ).all()
    user.roles = list(roles)
    await session.flush()
    return user
