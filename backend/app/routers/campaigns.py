"""Campaign API routes.

Route ordering matters: literal paths (/join, /me) must come before
parameterised paths (/{campaign_id}) so FastAPI matches them first.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_user,
    require_campaign_member,
    require_gm,
)
from app.database import get_db
from app.models.user import User
from app.schemas.campaign import (
    CampaignCreate,
    CampaignResponse,
    CampaignSummary,
    CampaignUpdate,
    JoinRequest,
    MemberResponse,
    MemberUpdate,
)
from datetime import datetime

from pydantic import BaseModel
from app.schemas.session import CampaignNoteEntry, SessionListItem
from app.services import campaign_service, milestone_service, session_note_service, session_service


# ── Milestone schemas (inline) ─────────────────────────────────────────────────

class MilestoneCreate(BaseModel):
    title: str
    description: str | None = None
    session_id: uuid.UUID | None = None
    milestone_date: datetime | None = None


class MilestoneUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    session_id: uuid.UUID | None = None
    milestone_date: datetime | None = None


class MilestoneResponse(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    title: str
    description: str | None
    session_id: uuid.UUID | None
    created_by: uuid.UUID | None
    created_at: datetime
    milestone_date: datetime | None

    model_config = {"from_attributes": True}

router = APIRouter()


# ── Collection endpoints ───────────────────────────────────────────────────────

@router.get("", response_model=list[CampaignSummary])
async def list_campaigns(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CampaignSummary]:
    """List all campaigns the authenticated user belongs to."""
    return await campaign_service.list_user_campaigns(db, current_user.id)


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: CampaignCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    """Create a new campaign.  The creator is automatically assigned the GM role."""
    return await campaign_service.create_campaign(db, current_user, data)


# ── Join (literal path — must precede /{campaign_id}) ─────────────────────────

@router.post("/join", response_model=CampaignResponse)
async def join_campaign(
    body: JoinRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    """Join a campaign using its invite code.  Joining user becomes a player."""
    try:
        return await campaign_service.join_campaign(db, current_user, body.invite_code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ── Single-campaign endpoints ──────────────────────────────────────────────────

@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: uuid.UUID,
    _: User = Depends(require_campaign_member),
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    campaign = await campaign_service.get_campaign(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: uuid.UUID,
    data: CampaignUpdate,
    _: User = Depends(require_gm),
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    campaign = await campaign_service.get_campaign(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return await campaign_service.update_campaign(db, campaign, data)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: uuid.UUID,
    _: User = Depends(require_gm),
    db: AsyncSession = Depends(get_db),
) -> None:
    campaign = await campaign_service.get_campaign(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    await campaign_service.delete_campaign(db, campaign)


# ── Invite code ────────────────────────────────────────────────────────────────

@router.post("/{campaign_id}/invite/regenerate", response_model=CampaignResponse)
async def regenerate_invite_code(
    campaign_id: uuid.UUID,
    _: User = Depends(require_gm),
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    """Generate a new invite code, invalidating the previous one."""
    campaign = await campaign_service.get_campaign(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return await campaign_service.regenerate_invite_code(db, campaign)


# ── Members ────────────────────────────────────────────────────────────────────

@router.delete("/{campaign_id}/members/me", status_code=status.HTTP_204_NO_CONTENT)
async def leave_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(require_campaign_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Leave a campaign voluntarily. The last GM cannot leave."""
    try:
        await campaign_service.leave_campaign(db, campaign_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{campaign_id}/members", response_model=list[MemberResponse])
async def list_members(
    campaign_id: uuid.UUID,
    _: User = Depends(require_campaign_member),
    db: AsyncSession = Depends(get_db),
) -> list[MemberResponse]:
    return await campaign_service.list_members(db, campaign_id)


@router.patch("/{campaign_id}/members/{user_id}", response_model=MemberResponse)
async def update_member(
    campaign_id: uuid.UUID,
    user_id: uuid.UUID,
    data: MemberUpdate,
    current_user: User = Depends(require_campaign_member),
    db: AsyncSession = Depends(get_db),
) -> MemberResponse:
    """Update a member's character name.  Members can only update their own record."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own member record",
        )
    member = await campaign_service.update_member(db, campaign_id, user_id, data)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    # Re-fetch with user info to build MemberResponse
    members = await campaign_service.list_members(db, campaign_id)
    for m in members:
        if m.user_id == user_id:
            return m
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")


@router.delete(
    "/{campaign_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    campaign_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(require_gm),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a member from a campaign.  GMs cannot remove themselves."""
    try:
        await campaign_service.remove_member(
            db, campaign_id, user_id, current_user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{campaign_id}/next-session", response_model=SessionListItem | None)
async def get_next_session(
    campaign_id: uuid.UUID,
    _: User = Depends(require_campaign_member),
    db: AsyncSession = Depends(get_db),
) -> SessionListItem | None:
    """Return the next upcoming confirmed session for this campaign, or null."""
    return await session_service.get_next_confirmed_session(db, campaign_id)


@router.get(
    "/{campaign_id}/my-notes",
    response_model=list[CampaignNoteEntry],
)
async def get_campaign_notes(
    campaign_id: uuid.UUID,
    current_user: User = Depends(require_campaign_member),
    db: AsyncSession = Depends(get_db),
) -> list[CampaignNoteEntry]:
    """Return the current user's aggregated session journal for this campaign.

    Includes the user's own notes (any visibility) and public GM notes,
    ordered chronologically by session time.
    """
    return await session_note_service.get_campaign_notes(
        db, current_user.id, campaign_id
    )


# ── Milestones ─────────────────────────────────────────────────────────────────

@router.get("/{campaign_id}/milestones", response_model=list[MilestoneResponse])
async def list_milestones(
    campaign_id: uuid.UUID,
    _: User = Depends(require_campaign_member),
    db: AsyncSession = Depends(get_db),
) -> list[MilestoneResponse]:
    """Return all milestones for a campaign (any member)."""
    milestones = await milestone_service.list_milestones(db, campaign_id)
    return [MilestoneResponse.model_validate(m) for m in milestones]


@router.post(
    "/{campaign_id}/milestones",
    response_model=MilestoneResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_milestone(
    campaign_id: uuid.UUID,
    data: MilestoneCreate,
    current_user: User = Depends(require_gm),
    db: AsyncSession = Depends(get_db),
) -> MilestoneResponse:
    """Create a new milestone (GM only)."""
    milestone = await milestone_service.create_milestone(
        db,
        campaign_id=campaign_id,
        creator_id=current_user.id,
        title=data.title,
        description=data.description,
        session_id=data.session_id,
        milestone_date=data.milestone_date,
    )
    return MilestoneResponse.model_validate(milestone)


@router.patch("/{campaign_id}/milestones/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(
    campaign_id: uuid.UUID,
    milestone_id: uuid.UUID,
    data: MilestoneUpdate,
    _: User = Depends(require_gm),
    db: AsyncSession = Depends(get_db),
) -> MilestoneResponse:
    """Update a milestone (GM only)."""
    from app.models.milestone import Milestone
    from sqlalchemy import select as sel
    milestone = await db.scalar(
        sel(Milestone).where(
            Milestone.id == milestone_id,
            Milestone.campaign_id == campaign_id,
        )
    )
    if milestone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
    updates = data.model_dump(exclude_unset=True)
    if not updates:
        return MilestoneResponse.model_validate(milestone)
    updated = await milestone_service.update_milestone(db, milestone, updates)
    return MilestoneResponse.model_validate(updated)


@router.delete(
    "/{campaign_id}/milestones/{milestone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_milestone(
    campaign_id: uuid.UUID,
    milestone_id: uuid.UUID,
    _: User = Depends(require_gm),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a milestone (GM only)."""
    from app.models.milestone import Milestone
    from sqlalchemy import select as sel
    milestone = await db.scalar(
        sel(Milestone).where(
            Milestone.id == milestone_id,
            Milestone.campaign_id == campaign_id,
        )
    )
    if milestone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
    await milestone_service.delete_milestone(db, milestone)
