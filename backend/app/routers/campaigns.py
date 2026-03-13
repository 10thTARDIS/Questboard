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
)
from app.services import campaign_service

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

@router.get("/{campaign_id}/members", response_model=list[MemberResponse])
async def list_members(
    campaign_id: uuid.UUID,
    _: User = Depends(require_campaign_member),
    db: AsyncSession = Depends(get_db),
) -> list[MemberResponse]:
    return await campaign_service.list_members(db, campaign_id)


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
