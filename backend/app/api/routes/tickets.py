"""Ticket routes (M1-4).

Every handler is guarded by an explicit permission dependency. No handler contains a
role name, and none decides access itself — that is M1-3's job.
"""

from fastapi import APIRouter, Depends, status

from app.api.deps import SessionDep, require_any_permission, require_permission
from app.core.enums import PermissionCode
from app.models import Ticket, User
from app.schemas.ticket import (
    TicketCreateRequest,
    TicketResponse,
    TicketStatusUpdateRequest,
)
from app.services import ticket_service

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TicketResponse)
async def create_ticket(
    payload: TicketCreateRequest,
    session: SessionDep,
    user: User = Depends(require_permission(PermissionCode.TICKET_CREATE)),
) -> Ticket:
    return await ticket_service.create_ticket(session, user, payload)


@router.get("", response_model=list[TicketResponse])
async def list_tickets(
    session: SessionDep,
    user: User = Depends(
        require_any_permission(
            PermissionCode.TICKET_READ_OWN, PermissionCode.TICKET_READ_ALL
        )
    ),
) -> list[Ticket]:
    return await ticket_service.list_tickets(session, user)


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: int,
    session: SessionDep,
    user: User = Depends(
        require_any_permission(
            PermissionCode.TICKET_READ_OWN, PermissionCode.TICKET_READ_ALL
        )
    ),
) -> Ticket:
    return await ticket_service.get_ticket(session, user, ticket_id)


@router.patch("/{ticket_id}/status", response_model=TicketResponse)
async def update_ticket_status(
    ticket_id: int,
    payload: TicketStatusUpdateRequest,
    session: SessionDep,
    _: User = Depends(require_permission(PermissionCode.TICKET_UPDATE_STATUS)),
) -> Ticket:
    return await ticket_service.change_status(session, ticket_id, payload.status)
