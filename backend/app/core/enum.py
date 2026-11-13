from enum import StrEnum


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"

class RoleName(StrEnum):
    CUSTOMER = "customer"
    STAFF = "staff"
    ADMIN = "admin"

class PermissionCode(StrEnum):
    TICKET_CREATE = "ticket:create"
    TICKET_READ_OWN = "ticket:read_own"
    TICKET_READ_ALL = "ticket:read_all"
    TICKET_UPDATE_STATUS = "ticket:update_status"
    USER_READ = "user:read"
    USER_ASSIGN_ROLE = "user:assign_role"
    ROLE_READ = "role:read" 