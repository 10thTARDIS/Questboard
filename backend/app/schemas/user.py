"""Pydantic output schemas for the User resource."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class UserResponse(BaseModel):
    """Returned by GET /api/me.

    Does not expose oidc_sub or oidc_issuer — those are internal identifiers
    that the frontend has no need to display.
    """

    id: uuid.UUID
    display_name: str
    email: str | None = None
    avatar_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
