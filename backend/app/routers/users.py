"""User-facing API routes."""

import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from app.services import admin_service, settings_service, user_service


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

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return the currently authenticated user's profile."""
    return current_user


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
