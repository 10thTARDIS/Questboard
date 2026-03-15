"""FastAPI dependency injectors for authentication and authorisation."""

import secrets
import uuid

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import get_session
from app.database import get_db
from app.models.campaign import CampaignMember, MemberRole
from app.models.session import Session
from app.models.user import User
from app.services import session_service

_COOKIE_NAME = "qb_session"

# ── Authentication ────────────────────────────────────────────────────────────

async def get_current_user(
    cookie_token: str | None = Cookie(default=None, alias=_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Return the authenticated User, or raise 401.

    Reads the opaque session cookie → Redis → database.
    """
    if not cookie_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user_id = await get_session(cookie_token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


# ── Authorisation ─────────────────────────────────────────────────────────────

async def require_campaign_member(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require the current user to be a member (any role) of the campaign."""
    result = await db.execute(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == current_user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this campaign",
        )
    return current_user


async def require_gm(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require the current user to be the GM of the campaign."""
    result = await db.execute(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == current_user.id,
            CampaignMember.role == MemberRole.gm,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="GM role required for this campaign",
        )
    return current_user


# ── Session-scoped authorisation ───────────────────────────────────────────────
# These resolve the campaign from the session, so callers only need session_id.

async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require the current user to be a site admin."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


# ── Session-scoped authorisation ───────────────────────────────────────────────
# These resolve the campaign from the session, so callers only need session_id.

async def get_session_for_member(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Session:
    """Return the Session if the current user is a member of its campaign."""
    session = await session_service.get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    member = await db.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == session.campaign_id,
            CampaignMember.user_id == current_user.id,
        )
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this campaign",
        )
    return session


async def require_bot_auth(
    x_bot_key: str = Header(..., alias="X-Bot-Key"),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Verify the X-Bot-Key header against the stored bot API key."""
    from app.services.settings_service import get_bot_api_key
    stored = await get_bot_api_key(db)
    if not stored or not secrets.compare_digest(x_bot_key, stored):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bot API key",
        )


async def get_session_for_gm(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Session:
    """Return the Session if the current user is the GM of its campaign."""
    session = await session_service.get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    member = await db.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == session.campaign_id,
            CampaignMember.user_id == current_user.id,
            CampaignMember.role == MemberRole.gm,
        )
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="GM role required for this campaign",
        )
    return session
