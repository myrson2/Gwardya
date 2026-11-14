"""Idempotent demo seed (M1-1).

``seed()`` converges an existing database to the documented baseline and deliberately
does not commit — the CLI commits, and tests can call it inside a rollback fixture.
Passwords are the one exception to reconciliation: an existing hash is never replaced.
"""

import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.catalog import PERMISSION_CATALOG, ROLE_DESCRIPTIONS, ROLE_PERMISSIONS
from app.core.config import settings
from app.core.enums import RoleName, TicketStatus
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Permission, Role, Ticket, User

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeedReport:
    permissions_created: int
    roles_created: int
    users_created: int
    tickets_created: int
    grants_added: int
    grants_removed: int


@dataclass(frozen=True)
class DemoUser:
    email: str
    full_name: str
    role: RoleName


@dataclass(frozen=True)
class DemoTicket:
    owner_email: str
    title: str
    description: str
    status: TicketStatus


DEMO_USERS: tuple[DemoUser, ...] = (
    DemoUser("alice@example.com", "Alice Customer", RoleName.CUSTOMER),
    DemoUser("bob@example.com", "Bob Customer", RoleName.CUSTOMER),
    DemoUser("staff@example.com", "Sam Staff", RoleName.STAFF),
    DemoUser("admin@example.com", "Ada Admin", RoleName.ADMIN),
)

SAMPLE_TICKETS: tuple[DemoTicket, ...] = (
    DemoTicket(
        "alice@example.com",
        "Printer will not connect",
        "Office printer refuses every job over Wi-Fi.",
        TicketStatus.OPEN,
    ),
    DemoTicket(
        "alice@example.com",
        "Invoice copy request",
        "Please resend the March invoice as a PDF.",
        TicketStatus.CLOSED,
    ),
    DemoTicket(
        "bob@example.com",
        "VPN drops every hour",
        "The VPN connection resets roughly every sixty minutes.",
        TicketStatus.IN_PROGRESS,
    ),
    DemoTicket(
        "bob@example.com",
        "Cannot reset password",
        "The reset email never arrives in the inbox.",
        TicketStatus.OPEN,
    ),
)


async def _converge_permissions(session: AsyncSession) -> int:
    created = 0
    existing = {
        permission.code: permission
        for permission in (await session.scalars(select(Permission))).all()
    }
    for code, description in PERMISSION_CATALOG.items():
        permission = existing.get(str(code))
        if permission is None:
            session.add(Permission(code=str(code), description=description))
            created += 1
        elif permission.description != description:
            permission.description = description
    await session.flush()
    return created


async def _converge_roles(session: AsyncSession) -> int:
    created = 0
    existing = {
        role.name: role for role in (await session.scalars(select(Role))).all()
    }
    for name, description in ROLE_DESCRIPTIONS.items():
        role = existing.get(str(name))
        if role is None:
            session.add(Role(name=str(name), description=description))
            created += 1
        elif role.description != description:
            role.description = description
    await session.flush()
    return created


async def _converge_grants(session: AsyncSession) -> tuple[int, int]:
    roles = {
        role.name: role
        for role in (
            await session.scalars(select(Role).options(selectinload(Role.permissions)))
        ).all()
    }
    permissions = {
        permission.code: permission
        for permission in (await session.scalars(select(Permission))).all()
    }

    added = 0
    removed = 0
    for role_name, codes in ROLE_PERMISSIONS.items():
        role = roles[str(role_name)]
        desired = {permissions[str(code)] for code in codes}
        current = set(role.permissions)
        if desired == current:
            continue
        added += len(desired - current)
        removed += len(current - desired)
        role.permissions = list(desired)
    await session.flush()
    return added, removed


async def _converge_users(
    session: AsyncSession, *, dev_password: str
) -> tuple[dict[str, User], int]:
    users: dict[str, User] = {}
    created = 0
    for demo in DEMO_USERS:
        user = await session.scalar(
            select(User)
            .where(User.email == demo.email)
            .options(selectinload(User.roles))
        )
        if user is None:
            user = User(
                email=demo.email,
                full_name=demo.full_name,
                hashed_password=await hash_password(dev_password),
            )
            session.add(user)
            await session.flush()
            # Re-select so the (empty) roles collection is explicitly loaded; every
            # relationship is lazy="raise", and assigning to an unloaded collection
            # would otherwise trigger a forbidden lazy load.
            user = await session.scalar(
                select(User)
                .where(User.id == user.id)
                .options(selectinload(User.roles))
            )
            created += 1
        assert user is not None
        users[demo.email] = user
    await session.flush()
    return users, created


async def _converge_user_roles(
    session: AsyncSession, users: dict[str, User]
) -> None:
    roles = {
        role.name: role for role in (await session.scalars(select(Role))).all()
    }
    for demo in DEMO_USERS:
        user = users[demo.email]
        role = roles[str(demo.role)]
        if {current.id for current in user.roles} != {role.id}:
            user.roles = [role]
    await session.flush()


async def _converge_tickets(session: AsyncSession, users: dict[str, User]) -> int:
    created = 0
    for sample in SAMPLE_TICKETS:
        owner = users[sample.owner_email]
        ticket = await session.scalar(
            select(Ticket).where(
                Ticket.customer_id == owner.id,
                Ticket.title == sample.title,
            )
        )
        if ticket is None:
            session.add(
                Ticket(
                    title=sample.title,
                    description=sample.description,
                    status=sample.status,
                    customer_id=owner.id,
                )
            )
            created += 1
        else:
            ticket.description = sample.description
            ticket.status = sample.status
    await session.flush()
    return created


async def seed(
    session: AsyncSession, *, dev_password: str | None = None
) -> SeedReport:
    """Converge the database to the documented baseline. Does not commit."""
    if settings.is_production:
        raise RuntimeError("Refusing to seed demo data in production")

    password = dev_password if dev_password is not None else settings.seed_dev_password
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Seed password exceeds bcrypt's 72-byte limit")

    permissions_created = await _converge_permissions(session)
    roles_created = await _converge_roles(session)
    grants_added, grants_removed = await _converge_grants(session)
    users, users_created = await _converge_users(session, dev_password=password)
    await _converge_user_roles(session, users)
    tickets_created = await _converge_tickets(session, users)

    return SeedReport(
        permissions_created=permissions_created,
        roles_created=roles_created,
        users_created=users_created,
        tickets_created=tickets_created,
        grants_added=grants_added,
        grants_removed=grants_removed,
    )


async def main() -> int:
    """CLI: connect, seed, commit, log counts only. Never logs emails or hashes."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    async with SessionLocal() as session:
        try:
            report = await seed(session)
            await session.commit()
        except Exception as exc:  # noqa: BLE001 - CLI must report and exit non-zero
            await session.rollback()
            # Type only: driver messages can echo bound parameters (hashes).
            logger.error("Seed failed (%s); nothing was committed.", type(exc).__name__)
            return 1
    logger.info(
        "Seed complete: %s permissions, %s roles, %s grants added, %s removed, "
        "%s users, %s tickets.",
        report.permissions_created,
        report.roles_created,
        report.grants_added,
        report.grants_removed,
        report.users_created,
        report.tickets_created,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
