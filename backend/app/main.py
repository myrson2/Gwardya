from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import models  # noqa: F401 - importing registers every table on Base.metadata
from app.api.routes import admin, auth, tickets
from app.core.config import settings
from app.core.security import REFRESH_COOKIE_NAME
from app.db.base import Base
from app.db.session import engine, get_session
from app.services.errors import AppError


@asynccontextmanager
async def lifespan(_: FastAPI):
    # M1 schema mechanism: create_all creates missing tables but never alters existing
    # ones. Until Alembic arrives in M3, a model change needs an explicit dev reset.
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
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


@app.exception_handler(AppError)
async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )
    if exc.clear_refresh_cookie:
        response.delete_cookie(REFRESH_COOKIE_NAME, path="/auth")
    return response


app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(admin.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


SessionDep = Annotated[AsyncSession, Depends(get_session)]


@app.get("/health/db", tags=["health"])
async def health_db(session: SessionDep) -> dict[str, str]:
    value = (await session.execute(text("SELECT 1"))).scalar_one()
    return {"status": "ok" if value == 1 else "error", "database": "mysql"}
