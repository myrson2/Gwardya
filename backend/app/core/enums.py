from enum import StrEnum


class RoleName(StrEnum):
    """The three seeded roles. Roles are data; code only needs their names at seed time."""

    CUSTOMER = "customer"
    STAFF = "staff"
    ADMIN = "admin"


class PermissionCode(StrEnum):
    """The permission catalog.

    Route guards reference these codes. A role is just a bundle of codes stored in
    MySQL, so adding a role never requires editing a route.
    """

    TICKET_CREATE = "ticket:create"
    TICKET_READ_OWN = "ticket:read_own"
    TICKET_READ_ALL = "ticket:read_all"
    TICKET_UPDATE_STATUS = "ticket:update_status"
    USER_READ = "user:read"
    USER_ASSIGN_ROLE = "user:assign_role"
    ROLE_READ = "role:read"


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"
