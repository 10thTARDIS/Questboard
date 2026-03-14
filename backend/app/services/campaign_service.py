"""Campaign business logic.

All functions take an AsyncSession and return plain Python / SQLAlchemy objects.
HTTP concerns (status codes, HTTPException) are handled in the router layer.
"""

import secrets
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign, CampaignMember, MemberRole
from app.models.user import User
from app.schemas.campaign import (
    CampaignCreate,
    CampaignSummary,
    CampaignUpdate,
    MemberResponse,
    MemberUpdate,
)


async def create_campaign(
    db: AsyncSession,
    creator: User,
    data: CampaignCreate,
) -> Campaign:
    """Create a campaign and add the creator as its first GM."""
    campaign = Campaign(
        name=data.name,
        game_system=data.game_system,
        description=data.description,
        discord_webhook_url=data.discord_webhook_url,
        timezone=data.timezone,
        reminder_offsets_minutes=data.reminder_offsets_minutes,
        invite_code=secrets.token_urlsafe(8),
    )
    db.add(campaign)
    await db.flush()  # populate campaign.id before creating the member row

    db.add(CampaignMember(
        campaign_id=campaign.id,
        user_id=creator.id,
        role=MemberRole.gm,
    ))
    await db.commit()
    await db.refresh(campaign)
    return campaign


async def get_campaign(
    db: AsyncSession,
    campaign_id: uuid.UUID,
) -> Campaign | None:
    """Return a Campaign by its primary key, or None if not found."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    return result.scalar_one_or_none()


async def list_user_campaigns(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[CampaignSummary]:
    """Return all campaigns the user belongs to, with their role in each."""
    result = await db.execute(
        select(Campaign, CampaignMember.role)
        .join(CampaignMember, Campaign.id == CampaignMember.campaign_id)
        .where(CampaignMember.user_id == user_id)
        .order_by(Campaign.created_at.desc())
    )
    return [
        CampaignSummary(
            id=campaign.id,
            name=campaign.name,
            game_system=campaign.game_system,
            description=campaign.description,
            created_at=campaign.created_at,
            my_role=role,
        )
        for campaign, role in result.all()
    ]


async def update_campaign(
    db: AsyncSession,
    campaign: Campaign,
    data: CampaignUpdate,
) -> Campaign:
    """Apply only the fields present in the PATCH body (partial update)."""
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(campaign, field, value)
    await db.commit()
    await db.refresh(campaign)
    return campaign


async def delete_campaign(db: AsyncSession, campaign: Campaign) -> None:
    """Delete a campaign and all its children (sessions, members) via CASCADE."""
    await db.delete(campaign)
    await db.commit()


async def join_campaign(
    db: AsyncSession,
    user: User,
    invite_code: str,
) -> Campaign:
    """Add user to a campaign as a player.  Raises ValueError for invalid states."""
    result = await db.execute(
        select(Campaign).where(Campaign.invite_code == invite_code)
    )
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise ValueError("Invalid invite code")

    existing = await db.execute(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign.id,
            CampaignMember.user_id == user.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError("You are already a member of this campaign")

    db.add(CampaignMember(
        campaign_id=campaign.id,
        user_id=user.id,
        role=MemberRole.player,
    ))
    await db.commit()
    await db.refresh(campaign)
    return campaign


async def regenerate_invite_code(
    db: AsyncSession,
    campaign: Campaign,
) -> Campaign:
    """Replace the existing invite code with a fresh one, invalidating the old one."""
    campaign.invite_code = secrets.token_urlsafe(8)
    await db.commit()
    await db.refresh(campaign)
    return campaign


async def list_members(
    db: AsyncSession,
    campaign_id: uuid.UUID,
) -> list[MemberResponse]:
    """Return all members of a campaign ordered by join date (oldest first)."""
    result = await db.execute(
        select(CampaignMember, User)
        .join(User, CampaignMember.user_id == User.id)
        .where(CampaignMember.campaign_id == campaign_id)
        .order_by(CampaignMember.joined_at)
    )
    return [
        MemberResponse(
            user_id=row.CampaignMember.user_id,
            display_name=row.User.effective_display_name,
            email=row.User.email,
            avatar_url=row.User.avatar_url,
            role=row.CampaignMember.role,
            character_name=row.CampaignMember.character_name,
            joined_at=row.CampaignMember.joined_at,
        )
        for row in result.all()
    ]


async def update_member(
    db: AsyncSession,
    campaign_id: uuid.UUID,
    user_id: uuid.UUID,
    data: MemberUpdate,
) -> CampaignMember | None:
    """Update a member's character name.  Returns None if the member doesn't exist."""
    result = await db.execute(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(member, field, value)
    await db.commit()
    await db.refresh(member)
    return member


async def remove_member(
    db: AsyncSession,
    campaign_id: uuid.UUID,
    user_id_to_remove: uuid.UUID,
    requesting_user_id: uuid.UUID,
) -> None:
    """Remove a member from a campaign.  Raises ValueError for invalid operations."""
    if user_id_to_remove == requesting_user_id:
        raise ValueError("You cannot remove yourself from a campaign")

    # Prevent removing the last GM
    gm_count = await db.scalar(
        select(func.count()).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.role == MemberRole.gm,
        )
    )
    target = await db.execute(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == user_id_to_remove,
        )
    )
    member = target.scalar_one_or_none()
    if member is None:
        raise ValueError("User is not a member of this campaign")

    if member.role == MemberRole.gm and (gm_count or 0) <= 1:
        raise ValueError("Cannot remove the last GM from a campaign")

    await db.delete(member)
    await db.commit()
