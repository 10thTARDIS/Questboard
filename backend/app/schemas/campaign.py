import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.models.campaign import MemberRole

_DISCORD_WEBHOOK_PREFIX = "https://discord.com/api/webhooks/"


def _validate_webhook(v: str | None) -> str | None:
    """Reject any webhook URL that is not a Discord webhook — prevents SSRF."""
    if not v:
        return None
    if not v.startswith(_DISCORD_WEBHOOK_PREFIX):
        raise ValueError(
            "discord_webhook_url must be a Discord webhook URL "
            "(https://discord.com/api/webhooks/...)"
        )
    return v


# ── Input schemas ─────────────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    name: str
    game_system: str | None = None
    description: str | None = None
    discord_webhook_url: str | None = None
    timezone: str | None = None
    reminder_offsets_minutes: list[int] | None = None

    @field_validator("discord_webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        return _validate_webhook(v)


class CampaignUpdate(BaseModel):
    name: str | None = None
    game_system: str | None = None
    description: str | None = None
    discord_webhook_url: str | None = None
    timezone: str | None = None
    reminder_offsets_minutes: list[int] | None = None

    @field_validator("discord_webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        return _validate_webhook(v)


class JoinRequest(BaseModel):
    invite_code: str


# ── Output schemas ────────────────────────────────────────────────────────────

class CampaignSummary(BaseModel):
    """Returned in list views; includes the calling user's role."""
    id: uuid.UUID
    name: str
    game_system: str | None
    description: str | None
    created_at: datetime
    my_role: MemberRole


class CampaignResponse(BaseModel):
    """Returned for detail views; includes all fields."""
    id: uuid.UUID
    name: str
    game_system: str | None
    description: str | None
    discord_webhook_url: str | None
    invite_code: str | None
    timezone: str | None
    reminder_offsets_minutes: list[int] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberResponse(BaseModel):
    user_id: uuid.UUID
    display_name: str
    email: str | None
    avatar_url: str | None
    role: MemberRole
    character_name: str | None
    joined_at: datetime


class MemberUpdate(BaseModel):
    """PATCH /{campaign_id}/members/{user_id} — members can set their character name."""
    character_name: str | None = None
