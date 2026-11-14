from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.associations import user_roles

if TYPE_CHECKING:
    from app.models.role import Role


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # lazy="raise" makes a forgotten selectinload fail loudly instead of raising
    # MissingGreenlet mid-serialization (Constitution §3).
    roles: Mapped[list[Role]] = relationship(
        secondary=user_roles,
        back_populates="users",
        lazy="raise",
    )

    @property
    def role_names(self) -> frozenset[str]:
        """Role names for display only. Never use this for an access decision."""
        return frozenset(role.name for role in self.roles)

    @property
    def permission_codes(self) -> frozenset[str]:
        """Effective permission codes resolved through roles.

        Requires ``roles`` and each role's ``permissions`` to be eager-loaded
        (``selectinload(User.roles).selectinload(Role.permissions)``).
        """
        return frozenset(
            permission.code
            for role in self.roles
            for permission in role.permissions
        )
