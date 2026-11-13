"""ORM models.

Importing this package registers every table on ``Base.metadata``.
"""

from app.model.associations import role_permissions, user_roles
from app.model.permission import Permission
from app.model.refresh_token import RefreshToken
from app.model.role import Role
from app.model.ticket import Ticket
from app.model.user import User

__all__ = [
    "Permission",
    "RefreshToken",
    "Role",
    "Ticket",
    "User",
    "role_permissions",
    "user_roles",
]
