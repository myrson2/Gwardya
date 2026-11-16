"""Ticket business rules.

Authorization (may you attempt this?) is already enforced by the route guard. The
ownership predicate (which rows may you see?) lives in ``ticket_scope`` and is the
M1-3 exercise. Status transitions here are the deliberately naive M1 policy; the M3
Pattern Lab refactors them into a Strategy.
"""

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import TicketStatus
from app.models import Ticket, User
from app.schemas.ticket import TicketCreateRequest
from app.services.errors import ConflictError, NotFoundError
from app.services.ticket_scope import scope_tickets

# closed is final in M1 (Constitution §3). M3 may introduce an admin reopen policy.
_ALLOWED_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    TicketStatus.OPEN: frozenset({TicketStatus.IN_PROGRESS}),
    TicketStatus.IN_PROGRESS: frozenset({TicketStatus.CLOSED}),
    TicketStatus.CLOSED: frozenset(),
}


async def create_ticket(
    session: AsyncSession, user: User, payload: TicketCreateRequest
) -> Ticket:
    """Ownership is taken from the authenticated identity, never from the payload."""
    ticket = Ticket(
        title=payload.title,
        description=payload.description,
        customer_id=user.id,
    )
    session.add(ticket)
    await session.flush()
    # Server-side defaults (created_at/updated_at) are loaded here; reading them later
    # without an await would raise MissingGreenlet.
    await session.refresh(ticket)
    return ticket


async def list_tickets(session: AsyncSession, user: User) -> list[Ticket]:
    stmt: Select[tuple[Ticket]] = select(Ticket).order_by(
        Ticket.created_at.desc(), Ticket.id.desc()
    )
    stmt = scope_tickets(stmt, user)
    return list((await session.scalars(stmt)).all())


async def get_ticket(session: AsyncSession, user: User, ticket_id: int) -> Ticket:
    """Query-level ownership: a foreign id cannot be distinguished from a missing one."""
    stmt: Select[tuple[Ticket]] = select(Ticket).where(Ticket.id == ticket_id)
    stmt = scope_tickets(stmt, user)
    ticket = (await session.scalars(stmt)).one_or_none()
    if ticket is None:
        raise NotFoundError("Ticket not found")
    return ticket


async def change_status(
    session: AsyncSession, ticket_id: int, target: TicketStatus
) -> Ticket:
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        raise NotFoundError("Ticket not found")
    if target == ticket.status:
        return ticket
    if target not in _ALLOWED_TRANSITIONS[ticket.status]:
        raise ConflictError(
            f"Cannot move ticket from '{ticket.status}' to '{target}'"
        )
    ticket.status = target
    await session.flush()
    await session.refresh(ticket)
    return ticket
