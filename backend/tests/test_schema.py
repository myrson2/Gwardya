"""V-01 .. V-09 — schema and database-enforced constraints (M1-1)."""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.security import utcnow
from app.models import RefreshToken, Ticket, User

EXPECTED_TABLES = {
    "users",
    "roles",
    "permissions",
    "user_roles",
    "role_permissions",
    "tickets",
    "refresh_tokens",
}


async def _get_table_names(engine: AsyncEngine) -> list[str]:
    async with engine.connect() as connection:
        return await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_table_names()
        )


async def _get_columns(engine: AsyncEngine, table: str) -> list[str]:
    async with engine.connect() as connection:
        columns = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_columns(table)
        )
    return [column["name"] for column in columns]


async def _show_create_table(session: AsyncSession, table: str) -> str:
    result = await session.execute(text(f"SHOW CREATE TABLE {table}"))
    return str(result.first()[1])


async def _alice_id(session: AsyncSession) -> int:
    user = await session.scalar(
        text("SELECT id FROM users WHERE email = 'alice@example.com'")
    )
    assert user is not None
    return int(user)


async def test_schema_has_expected_tables(test_engine: AsyncEngine) -> None:
    assert set(await _get_table_names(test_engine)) == EXPECTED_TABLES


async def test_users_email_is_unique(db_session: AsyncSession) -> None:
    db_session.add(
        User(email="alice@example.com", hashed_password="x" * 60, full_name="Dup")
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_status_check_rejects_unknown_value(db_session: AsyncSession) -> None:
    customer_id = await _alice_id(db_session)
    # MySQL reports a CHECK violation as error 3819 (OperationalError), not as an
    # IntegrityError like PostgreSQL does, so assert on the shared DBAPIError base.
    with pytest.raises(DBAPIError):
        await db_session.execute(
            text(
                "INSERT INTO tickets (title, description, status, customer_id) "
                "VALUES ('bad', 'bad', 'bogus', :customer_id)"
            ),
            {"customer_id": customer_id},
        )
    await db_session.rollback()


async def test_status_accepts_three_valid_values(db_session: AsyncSession) -> None:
    from app.core.enums import TicketStatus

    customer_id = await _alice_id(db_session)
    for index, status in enumerate(TicketStatus):
        db_session.add(
            Ticket(
                title=f"Status probe {index}",
                description="probe",
                status=status,
                customer_id=customer_id,
            )
        )
    await db_session.flush()


async def test_ticket_customer_fk_is_restrict(db_session: AsyncSession) -> None:
    ddl = await _show_create_table(db_session, "tickets")
    assert "ON DELETE RESTRICT" in ddl
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("DELETE FROM users WHERE email = 'alice@example.com'")
        )
    await db_session.rollback()


async def test_association_fks_are_cascade(db_session: AsyncSession) -> None:
    assert "ON DELETE CASCADE" in await _show_create_table(db_session, "user_roles")
    assert "ON DELETE CASCADE" in await _show_create_table(
        db_session, "role_permissions"
    )


async def test_refresh_tokens_cascade_with_user(db_session: AsyncSession) -> None:
    user = User(
        email="cascade@example.com", hashed_password="x" * 60, full_name="Cascade"
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        RefreshToken(
            user_id=user.id,
            token_hash="a" * 64,
            expires_at=utcnow(),
        )
    )
    await db_session.flush()

    await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
    db_session.expunge_all()
    assert await db_session.scalar(
        text("SELECT COUNT(*) FROM refresh_tokens WHERE user_id = :id"),
        {"id": user.id},
    ) == 0


async def test_replacement_pointer_is_set_null(db_session: AsyncSession) -> None:
    assert "ON DELETE SET NULL" in await _show_create_table(
        db_session, "refresh_tokens"
    )
    customer_id = await _alice_id(db_session)
    parent = RefreshToken(
        user_id=customer_id, token_hash="b" * 64, expires_at=utcnow()
    )
    db_session.add(parent)
    await db_session.flush()
    child = RefreshToken(
        user_id=customer_id,
        token_hash="c" * 64,
        expires_at=utcnow(),
        replaced_by_id=parent.id,
    )
    db_session.add(child)
    await db_session.flush()

    await db_session.execute(
        text("DELETE FROM refresh_tokens WHERE id = :id"), {"id": parent.id}
    )
    # The DELETE above bypasses the ORM, so drop the stale identity map entries
    # and read the row back explicitly instead of touching expired attributes.
    db_session.expunge_all()
    refreshed = await db_session.get(RefreshToken, child.id)
    assert refreshed is not None
    assert refreshed.replaced_by_id is None


async def test_users_have_no_superuser_column(test_engine: AsyncEngine) -> None:
    assert "is_superuser" not in await _get_columns(test_engine, "users")
