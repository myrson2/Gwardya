from sqlalchemy import Column, Integer, Table

from app.db.base import Base

# Association tables only: the foreign keys are intentionally omitted here,
# so these stay plain join tables with composite primary keys.
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, primary_key=True),
    Column("role_id", Integer, primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, primary_key=True),
    Column("permission_id", Integer, primary_key=True),
)
