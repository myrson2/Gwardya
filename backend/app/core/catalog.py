"""The single source of truth for the seeded permission matrix.

The database is the runtime authority; this module only describes the baseline the
idempotent seed converges to. Nothing here may be imported by a route handler to make
an access decision — guards read permissions from MySQL instead.
"""

from app.core.enums import PermissionCode, RoleName

PERMISSION_CATALOG: dict[PermissionCode, str] = {
    PermissionCode.TICKET_CREATE: "Create tickets",
    PermissionCode.TICKET_READ_OWN: "Read own tickets",
    PermissionCode.TICKET_READ_ALL: "Read all tickets",
    PermissionCode.TICKET_UPDATE_STATUS: "Change ticket status",
    PermissionCode.USER_READ: "List users",
    PermissionCode.USER_ASSIGN_ROLE: "Assign roles to users",
    PermissionCode.ROLE_READ: "List roles and permissions",
}

ROLE_DESCRIPTIONS: dict[RoleName, str] = {
    RoleName.CUSTOMER: "Creates and reads only their own tickets",
    RoleName.STAFF: "Reads all tickets and moves their status",
    RoleName.ADMIN: "Full staff access plus user and role administration",
}

# Admin is listed explicitly. Do NOT derive it from PermissionCode: a new code must be a
# deliberate admin grant, and a test fails if the two drift apart (Constitution §2.4).
ROLE_PERMISSIONS: dict[RoleName, frozenset[PermissionCode]] = {
    RoleName.CUSTOMER: frozenset(
        {PermissionCode.TICKET_CREATE, PermissionCode.TICKET_READ_OWN}
    ),
    RoleName.STAFF: frozenset(
        {PermissionCode.TICKET_READ_ALL, PermissionCode.TICKET_UPDATE_STATUS}
    ),
    RoleName.ADMIN: frozenset(
        {
            PermissionCode.TICKET_CREATE,
            PermissionCode.TICKET_READ_OWN,
            PermissionCode.TICKET_READ_ALL,
            PermissionCode.TICKET_UPDATE_STATUS,
            PermissionCode.USER_READ,
            PermissionCode.USER_ASSIGN_ROLE,
            PermissionCode.ROLE_READ,
        }
    ),
}
