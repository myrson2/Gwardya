"""ORM models.

Importing this package registers every table on ``Base.metadata``.
"""

from app.models.associations import role_permissions, user_roles
from app.models.permission import Permission
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.ticket import Ticket
from app.models.user import User

__all__ = [
    "Permission",
    "RefreshToken",
    "Role",
    "Ticket",
    "User",
    "role_permissions",
    "user_roles",
]
