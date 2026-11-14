from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import TicketStatus


class TicketCreateRequest(BaseModel):
    # customer_id is deliberately absent; ownership comes from the access token.
    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)


class TicketStatusUpdateRequest(BaseModel):
    status: TicketStatus


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: TicketStatus
    customer_id: int
    created_at: datetime
    updated_at: datetime
