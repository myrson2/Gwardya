from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession  # type: ignore

from app.core.config import settings
from app.db.session import engine, get_session


@asynccontextmanager
async def lifespan(_: FastAPI):
    # M1-1 will call Base.metadata.create_all(engine) here once models exist.
    yield
    await engine.dispose()


app = FastAPI(title="Gwardya API", version="0.1.0", lifespan=lifespan)

# Exact allowlist + credentials; never a wildcard origin (Constitution §2.5).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


SessionDep = Annotated[AsyncSession, Depends(get_session)]

@app.get("/health/db", tags=["health"])
async def health_db(session: SessionDep) -> dict[str, str]:
    value = (await session.execute(text("SELECT 1"))).scalar_one()
    return {"status": "ok" if value == 1 else "error", "database": "mysql"}
