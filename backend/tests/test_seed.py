"""V-10 .. V-18 — the seeded baseline and idempotency (M1-1)."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.catalog import PERMISSION_CATALOG, ROLE_PERMISSIONS
from app.core.config import settings
from app.core.enums import PermissionCode, RoleName, TicketStatus
from app.core.security import verify_password
from app.db.seed import seed
from app.models import Permission, Role, Ticket, User, role_permissions


async def _count(session: AsyncSession, model: type) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)))


async def _count_grants(session: AsyncSession) -> int:
    return int(
        await session.scalar(select(func.count()).select_from(role_permissions))
    )


async def test_seed_creates_expected_rows(db_session: AsyncSession) -> None:
    assert await _count(db_session, Role) == 3
    assert await _count(db_session, Permission) == 7
    assert await _count_grants(db_session) == 11
    assert await _count(db_session, User) == 4
    assert await _count(db_session, Ticket) == 4


async def test_role_permission_matrix_is_exact(db_session: AsyncSession) -> None:
    roles = {
        role.name: role
        for role in (
            await db_session.scalars(
                select(Role).options(selectinload(Role.permissions))
            )
        ).all()
    }
    for role_name, expected in ROLE_PERMISSIONS.items():
        actual = {permission.code for permission in roles[str(role_name)].permissions}
        assert actual == {str(code) for code in expected}


async def test_admin_holds_every_catalog_permission(db_session: AsyncSession) -> None:
    admin = await db_session.scalar(
        select(Role)
        .where(Role.name == RoleName.ADMIN)
        .options(selectinload(Role.permissions))
    )
    assert admin is not None
    assert {permission.code for permission in admin.permissions} == {
        str(code) for code in PermissionCode
    }
    assert set(PermissionCode) == set(PERMISSION_CATALOG)


async def test_catalog_descriptions_are_present() -> None:
    assert all(PERMISSION_CATALOG.values())
    assert set(PERMISSION_CATALOG) == set(PermissionCode)


async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    before_counts = (
        await _count(db_session, Role),
        await _count(db_session, Permission),
        await _count_grants(db_session),
        await _count(db_session, User),
        await _count(db_session, Ticket),
    )
    before_hash = await db_session.scalar(
        select(User.hashed_password).where(User.email == "alice@example.com")
    )

    report = await seed(db_session)
    await db_session.flush()
    db_session.expire_all()

    after_counts = (
        await _count(db_session, Role),
        await _count(db_session, Permission),
        await _count_grants(db_session),
        await _count(db_session, User),
        await _count(db_session, Ticket),
    )
    after_hash = await db_session.scalar(
        select(User.hashed_password).where(User.email == "alice@example.com")
    )

    assert report.permissions_created == 0
    assert report.roles_created == 0
    assert report.users_created == 0
    assert report.tickets_created == 0
    assert report.grants_added == 0
    assert report.grants_removed == 0
    assert before_counts == after_counts
    assert before_hash == after_hash


async def test_seed_does_not_overwrite_password_hash(
    db_session: AsyncSession,
) -> None:
    hash_before = await db_session.scalar(
        select(User.hashed_password).where(User.email == "alice@example.com")
    )
    await seed(db_session, dev_password="DifferentPassw0rd!")
    await db_session.flush()
    db_session.expire_all()
    hash_after = await db_session.scalar(
        select(User.hashed_password).where(User.email == "alice@example.com")
    )
    assert hash_before == hash_after


async def test_seed_tickets_cover_both_customers_and_all_statuses(
    db_session: AsyncSession,
) -> None:
    rows = (
        await db_session.execute(
            select(User.email, Ticket.status)
            .join(Ticket, Ticket.customer_id == User.id)
            .order_by(Ticket.id)
        )
    ).all()
    emails = [row[0] for row in rows]
    statuses = {row[1] for row in rows}
    assert emails.count("alice@example.com") == 2
    assert emails.count("bob@example.com") == 2
    assert statuses == set(TicketStatus)


async def test_seed_refuses_production(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(RuntimeError):
        await seed(db_session)


async def test_demo_password_is_bcrypt_cost_12(db_session: AsyncSession) -> None:
    hashed = await db_session.scalar(
        select(User.hashed_password).where(User.email == "alice@example.com")
    )
    assert hashed is not None
    assert hashed.startswith("$2b$12$")
    assert await verify_password(settings.seed_dev_password, hashed)


async def test_seed_rejects_password_over_72_bytes(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(ValueError, match="72-byte"):
        await seed(db_session, dev_password="a" * 73)
