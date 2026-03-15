"""User-facing API routes."""

import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.platform_link import PlatformType
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from app.services import admin_service, platform_link_service, settings_service, user_service


# ── Admin response schemas (inline — small enough not to warrant a separate file)

class CampaignStatResponse(BaseModel):
    campaign_id: uuid.UUID
    campaign_name: str
    role: str
    joined_at: datetime
    session_count: int
    attended_count: int

    model_config = {"from_attributes": True}


class UserDetailResponse(BaseModel):
    user: UserResponse
    campaigns: list[CampaignStatResponse]

    model_config = {"from_attributes": True}


class SmtpConfigRequest(BaseModel):
    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    from_address: str = ""
    use_tls: bool = True


class NotificationSettingsRequest(BaseModel):
    smtp: SmtpConfigRequest | None = None
    discord_webhook_url: str | None = None


class SmtpConfigResponse(BaseModel):
    host: str
    port: int
    username: str
    from_address: str
    use_tls: bool
    configured: bool  # True if host is non-empty; password is never returned


class NotificationSettingsResponse(BaseModel):
    smtp: SmtpConfigResponse
    discord_webhook_url: str | None


# ── Platform link schemas ──────────────────────────────────────────────────────

class PlatformLinkResponse(BaseModel):
    platform: str
    platform_user_id: str
    linked_at: datetime
    verified_at: datetime | None

    model_config = {"from_attributes": True}


class PlatformLinkCreate(BaseModel):
    platform: Literal["discord", "matrix"]
    platform_user_id: str


# ── Bot settings schemas ───────────────────────────────────────────────────────

class BotSettingsRequest(BaseModel):
    bot_token: str = ""
    whisper_endpoint_url: str = ""
    whisper_api_key: str = ""
    llm_endpoint_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""


class BotSettingsResponse(BaseModel):
    bot_token_configured: bool
    whisper_endpoint_url: str
    whisper_configured: bool
    llm_endpoint_url: str
    llm_model: str
    llm_configured: bool
    api_key_configured: bool


router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return the currently authenticated user's profile."""
    return current_user


# ── Platform links ────────────────────────────────────────────────────────────

@router.get("/me/platform-links", response_model=list[PlatformLinkResponse])
async def get_platform_links(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlatformLinkResponse]:
    """Return all platform links for the current user."""
    links = await platform_link_service.get_links(db, current_user.id)
    return [PlatformLinkResponse.model_validate(l) for l in links]


@router.post(
    "/me/platform-links",
    response_model=PlatformLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_platform_link(
    data: PlatformLinkCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformLinkResponse:
    """Link (or re-link) a platform account to the current user."""
    link = await platform_link_service.upsert_link(
        db, current_user.id, PlatformType(data.platform), data.platform_user_id
    )
    return PlatformLinkResponse.model_validate(link)


@router.delete("/me/platform-links/{platform}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_platform_link(
    platform: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Unlink a platform account from the current user."""
    try:
        platform_type = PlatformType(platform)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown platform: {platform}",
        )
    try:
        await platform_link_service.delete_link(db, current_user.id, platform_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Update the current user's profile (display name override, timezone)."""
    return await user_service.update_user(db, current_user, data)


# ── Admin endpoints ────────────────────────────────────────────────────────────

@router.get("/admin/users", response_model=list[UserResponse])
async def admin_list_users(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[User]:
    """Return all users (admin only)."""
    return await user_service.get_all_users(db)


@router.patch("/admin/users/{user_id}/admin", response_model=UserResponse)
async def admin_set_admin(
    user_id: uuid.UUID,
    is_admin: bool,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Grant or revoke admin status for a user (admin only)."""
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return await user_service.set_admin(db, target, is_admin)


@router.get("/admin/users/{user_id}/details", response_model=UserDetailResponse)
async def admin_get_user_detail(
    user_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserDetailResponse:
    """Return a user's profile, campaign memberships, and attendance stats (admin only)."""
    detail = await admin_service.get_user_detail(db, user_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserDetailResponse(
        user=UserResponse.model_validate(detail.user),
        campaigns=[
            CampaignStatResponse(
                campaign_id=c.campaign_id,
                campaign_name=c.campaign_name,
                role=c.role,
                joined_at=c.joined_at,
                session_count=c.session_count,
                attended_count=c.attended_count,
            )
            for c in detail.campaigns
        ],
    )


@router.get("/admin/settings/notifications", response_model=NotificationSettingsResponse)
async def admin_get_notification_settings(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> NotificationSettingsResponse:
    """Return current notification settings (admin only). Password is never returned."""
    smtp_cfg = await settings_service.get_smtp_config(db)
    webhook = await settings_service.get_discord_webhook_fallback(db)

    smtp_resp = SmtpConfigResponse(
        host=smtp_cfg.host if smtp_cfg else "",
        port=smtp_cfg.port if smtp_cfg else 587,
        username=smtp_cfg.username if smtp_cfg else "",
        from_address=smtp_cfg.from_address if smtp_cfg else "",
        use_tls=smtp_cfg.use_tls if smtp_cfg else True,
        configured=bool(smtp_cfg and smtp_cfg.host),
    )
    return NotificationSettingsResponse(smtp=smtp_resp, discord_webhook_url=webhook)


@router.post("/admin/settings/notifications/test-email", status_code=status.HTTP_202_ACCEPTED)
async def admin_send_test_email(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Queue a test email to the current admin's email address (admin only)."""
    if not current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No email address on file for your account",
        )
    smtp_cfg = await settings_service.get_smtp_config(db)
    if smtp_cfg is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMTP is not configured",
        )
    from app.tasks.reminder_tasks import send_test_email
    send_test_email.delay(current_user.email)
    return {"detail": f"Test email queued for {current_user.email}"}


@router.put("/admin/settings/notifications", response_model=NotificationSettingsResponse)
async def admin_set_notification_settings(
    data: NotificationSettingsRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> NotificationSettingsResponse:
    """Update notification settings (admin only)."""
    if data.smtp is not None:
        # Preserve existing password if the field is left blank (client sends "")
        existing = await settings_service.get_setting(db, settings_service.KEY_SMTP)
        existing_password = (existing or {}).get("password", "") if existing else ""
        smtp_dict: dict[str, Any] = {
            "host": data.smtp.host,
            "port": data.smtp.port,
            "username": data.smtp.username,
            "password": data.smtp.password if data.smtp.password else existing_password,
            "from_address": data.smtp.from_address,
            "use_tls": data.smtp.use_tls,
        }
        await settings_service.set_setting(db, settings_service.KEY_SMTP, smtp_dict)

    if data.discord_webhook_url is not None:
        await settings_service.set_setting(
            db,
            settings_service.KEY_DISCORD_WEBHOOK,
            {"url": data.discord_webhook_url},
        )

    # Return fresh state
    smtp_cfg = await settings_service.get_smtp_config(db)
    webhook = await settings_service.get_discord_webhook_fallback(db)
    smtp_resp = SmtpConfigResponse(
        host=smtp_cfg.host if smtp_cfg else "",
        port=smtp_cfg.port if smtp_cfg else 587,
        username=smtp_cfg.username if smtp_cfg else "",
        from_address=smtp_cfg.from_address if smtp_cfg else "",
        use_tls=smtp_cfg.use_tls if smtp_cfg else True,
        configured=bool(smtp_cfg and smtp_cfg.host),
    )
    return NotificationSettingsResponse(smtp=smtp_resp, discord_webhook_url=webhook)


# ── Admin: bot settings ────────────────────────────────────────────────────────

def _build_bot_settings_response(
    bot_raw: dict | None,
    whisper_raw: dict | None,
    llm_raw: dict | None,
    api_key_raw: dict | None,
) -> BotSettingsResponse:
    return BotSettingsResponse(
        bot_token_configured=bool(bot_raw and bot_raw.get("token")),
        whisper_endpoint_url=(whisper_raw or {}).get("endpoint_url", ""),
        whisper_configured=bool(whisper_raw and whisper_raw.get("endpoint_url")),
        llm_endpoint_url=(llm_raw or {}).get("endpoint_url", ""),
        llm_model=(llm_raw or {}).get("model", ""),
        llm_configured=bool(llm_raw and llm_raw.get("endpoint_url")),
        api_key_configured=bool(api_key_raw and api_key_raw.get("key")),
    )


@router.get("/admin/settings/bot", response_model=BotSettingsResponse)
async def admin_get_bot_settings(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> BotSettingsResponse:
    """Return bot settings (admin only). Secrets are never returned — only presence flags."""
    bot_raw = await settings_service.get_setting(db, settings_service.KEY_BOT_TOKEN)
    whisper_raw = await settings_service.get_setting(db, settings_service.KEY_WHISPER)
    llm_raw = await settings_service.get_setting(db, settings_service.KEY_LLM)
    api_key_raw = await settings_service.get_setting(db, settings_service.KEY_BOT_API_KEY)
    return _build_bot_settings_response(bot_raw, whisper_raw, llm_raw, api_key_raw)


@router.put("/admin/settings/bot", response_model=BotSettingsResponse)
async def admin_set_bot_settings(
    data: BotSettingsRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> BotSettingsResponse:
    """Update bot settings (admin only). Blank fields preserve existing values."""
    existing_bot = await settings_service.get_setting(db, settings_service.KEY_BOT_TOKEN)
    await settings_service.set_setting(
        db,
        settings_service.KEY_BOT_TOKEN,
        {"token": data.bot_token if data.bot_token else (existing_bot or {}).get("token", "")},
    )

    existing_whisper = await settings_service.get_setting(db, settings_service.KEY_WHISPER)
    await settings_service.set_setting(
        db,
        settings_service.KEY_WHISPER,
        {
            "endpoint_url": data.whisper_endpoint_url or (existing_whisper or {}).get("endpoint_url", ""),
            "api_key": data.whisper_api_key if data.whisper_api_key else (existing_whisper or {}).get("api_key", ""),
        },
    )

    existing_llm = await settings_service.get_setting(db, settings_service.KEY_LLM)
    await settings_service.set_setting(
        db,
        settings_service.KEY_LLM,
        {
            "endpoint_url": data.llm_endpoint_url or (existing_llm or {}).get("endpoint_url", ""),
            "api_key": data.llm_api_key if data.llm_api_key else (existing_llm or {}).get("api_key", ""),
            "model": data.llm_model or (existing_llm or {}).get("model", ""),
        },
    )

    bot_raw = await settings_service.get_setting(db, settings_service.KEY_BOT_TOKEN)
    whisper_raw = await settings_service.get_setting(db, settings_service.KEY_WHISPER)
    llm_raw = await settings_service.get_setting(db, settings_service.KEY_LLM)
    api_key_raw = await settings_service.get_setting(db, settings_service.KEY_BOT_API_KEY)
    return _build_bot_settings_response(bot_raw, whisper_raw, llm_raw, api_key_raw)


@router.post("/admin/settings/bot/regenerate-key", response_model=dict)
async def admin_regenerate_bot_api_key(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate a new bot API key and return it once (admin only).

    The key is shown only in this response — subsequent GET calls only return
    whether a key is configured, not the key itself.
    """
    import secrets
    new_key = secrets.token_hex(32)
    await settings_service.set_setting(db, settings_service.KEY_BOT_API_KEY, {"key": new_key})
    return {"api_key": new_key}
