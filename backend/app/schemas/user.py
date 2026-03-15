"""Pydantic schemas for the User resource."""

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
    display_name_override: str | None = None
    effective_display_name: str
    email: str | None = None
    avatar_url: str | None = None
    timezone: str | None = None
    is_admin: bool = False
    recap_email_opt_in: bool = False
    last_login_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """PATCH /api/me — all fields optional."""

    display_name_override: str | None = None
    timezone: str | None = None
    recap_email_opt_in: bool | None = None
