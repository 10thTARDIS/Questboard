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

_VOTE_NOTIFICATION_MODES = {"each_vote", "all_voted"}


def _validate_vote_notification_mode(v: str | None) -> str | None:
    if v is not None and v not in _VOTE_NOTIFICATION_MODES:
        raise ValueError("vote_notification_mode must be 'each_vote', 'all_voted', or null")
    return v


class CampaignCreate(BaseModel):
    name: str
    game_system: str | None = None
    description: str | None = None
    discord_webhook_url: str | None = None
    guild_id: str | None = None
    notification_channel_id: str | None = None
    timezone: str | None = None
    reminder_offsets_minutes: list[int] | None = None
    vote_notification_mode: str | None = None
    vote_auto_close_hours: int | None = None
    recap_email_enabled: bool | None = None

    @field_validator("discord_webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        return _validate_webhook(v)

    @field_validator("vote_notification_mode")
    @classmethod
    def validate_vote_notification_mode(cls, v: str | None) -> str | None:
        return _validate_vote_notification_mode(v)

    @field_validator("guild_id", "notification_channel_id")
    @classmethod
    def validate_discord_snowflake(cls, v: str | None) -> str | None:
        if v is not None and not v.isdigit():
            raise ValueError("must be a Discord snowflake ID (numeric string)")
        return v


class CampaignUpdate(BaseModel):
    name: str | None = None
    game_system: str | None = None
    description: str | None = None
    discord_webhook_url: str | None = None
    guild_id: str | None = None
    notification_channel_id: str | None = None
    timezone: str | None = None
    reminder_offsets_minutes: list[int] | None = None
    vote_notification_mode: str | None = None
    vote_auto_close_hours: int | None = None
    recap_email_enabled: bool | None = None

    @field_validator("discord_webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        return _validate_webhook(v)

    @field_validator("vote_notification_mode")
    @classmethod
    def validate_vote_notification_mode(cls, v: str | None) -> str | None:
        return _validate_vote_notification_mode(v)

    @field_validator("guild_id", "notification_channel_id")
    @classmethod
    def validate_discord_snowflake(cls, v: str | None) -> str | None:
        if v is not None and not v.isdigit():
            raise ValueError("must be a Discord snowflake ID (numeric string)")
        return v


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
    guild_id: str | None
    notification_channel_id: str | None
    invite_code: str | None
    timezone: str | None
    reminder_offsets_minutes: list[int] | None
    vote_notification_mode: str | None
    vote_auto_close_hours: int | None
    recap_email_enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberResponse(BaseModel):
    user_id: uuid.UUID
    display_name: str
    email: str | None
    avatar_url: str | None
    role: MemberRole
    character_name: str | None
    character_sheet_url: str | None
    character_sheet_notes: str | None
    joined_at: datetime

    model_config = {"from_attributes": True}


class MemberUpdate(BaseModel):
    """PATCH /{campaign_id}/members/{user_id} — members can update their character info."""
    character_name: str | None = None
    character_sheet_url: str | None = None
    character_sheet_notes: str | None = None
