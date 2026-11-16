"""Real-MySQL test harness.

The schema and seed baseline are created once per session against
``rbac_learning_test``. Every test then runs inside an outer transaction that is
rolled back, so tests never see each other's writes (Constitution §4).
"""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app import models  # noqa: F401 - registers every table on Base.metadata
from app.core.config import settings
from app.db.base import Base
from app.db.seed import seed
from app.db.session import get_session
from app.main import app


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(settings.test_database_url, pool_pre_ping=True)
    if not (engine.url.database or "").endswith("_test"):
        raise RuntimeError("Refusing to touch a non-test database")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        await seed(session)
        await session.commit()

    yield engine

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncIterator[AsyncSession]:
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """API client whose requests share the rolled-back test session."""

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        yield http_client
    app.dependency_overrides.clear()


@pytest.fixture
def login(client: AsyncClient):
    """Return an async helper that logs in and yields the access token."""

    async def _login(
        email: str, password: str | None = None
    ) -> str:
        response = await client.post(
            "/auth/login",
            json={
                "email": email,
                "password": password or settings.seed_dev_password,
            },
        )
        assert response.status_code == 200, response.text
        return response.json()["access_token"]

    return _login
