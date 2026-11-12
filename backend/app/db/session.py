from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# Async-only stack (Constitution §3). pool_pre_ping avoids handing out dead
# connections after MySQL restarts.
engine = create_async_engine(settings.database_url, pool_pre_ping=True)

# expire_on_commit=False: objects stay usable after commit, so response
# serialization never triggers a lazy load (which would raise MissingGreenlet).
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """One session per request: commit on success, roll back on exception."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
