"""Admin panel business logic."""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.campaign import Campaign, CampaignMember
from app.models.session import Session, SessionStatus
from app.models.session_attendance import SessionAttendance
from app.models.user import User


@dataclass
class CampaignStat:
    campaign_id: uuid.UUID
    campaign_name: str
    role: str
    joined_at: object  # datetime
    session_count: int
    attended_count: int


@dataclass
class UserDetail:
    user: User
    campaigns: list[CampaignStat]


async def get_user_detail(db: AsyncSession, user_id: uuid.UUID) -> UserDetail | None:
    """Return a user plus per-campaign membership and attendance stats."""
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        return None

    # Fetch all campaign memberships with campaign info
    memberships_result = await db.execute(
        select(CampaignMember)
        .where(CampaignMember.user_id == user_id)
        .options(selectinload(CampaignMember.campaign))
    )
    memberships = list(memberships_result.scalars().all())

    campaign_stats: list[CampaignStat] = []
    for m in memberships:
        campaign: Campaign = m.campaign

        # Count sessions in this campaign (excluding cancelled)
        session_count = await db.scalar(
            select(func.count(Session.id)).where(
                Session.campaign_id == campaign.id,
                Session.status != SessionStatus.cancelled,
            )
        ) or 0

        # Count sessions this user attended
        attended_count = await db.scalar(
            select(func.count(SessionAttendance.id))
            .join(Session, SessionAttendance.session_id == Session.id)
            .where(
                Session.campaign_id == campaign.id,
                SessionAttendance.user_id == user_id,
                SessionAttendance.attended == True,  # noqa: E712
            )
        ) or 0

        campaign_stats.append(
            CampaignStat(
                campaign_id=campaign.id,
                campaign_name=campaign.name,
                role=m.role.value,
                joined_at=m.joined_at,
                session_count=session_count,
                attended_count=attended_count,
            )
        )

    return UserDetail(user=user, campaigns=campaign_stats)
