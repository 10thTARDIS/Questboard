"""Pydantic input/output schemas for the Vote resource."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.vote import Availability


class VoteSubmit(BaseModel):
    """Request body for PUT /sessions/{id}/timeslots/{slot_id}/vote."""

    availability: Availability  # "yes" | "maybe" | "no"


class VoteResponse(BaseModel):
    """Represents a single vote as returned by the API."""

    id: uuid.UUID
    time_slot_id: uuid.UUID
    user_id: uuid.UUID
    availability: Availability
    updated_at: datetime  # Set server-side on each upsert

    model_config = {"from_attributes": True}
