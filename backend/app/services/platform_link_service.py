"""Platform link service — manage linked Discord/Matrix accounts per user."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_link import PlatformLink, PlatformType


async def get_links(db: AsyncSession, user_id: uuid.UUID) -> list[PlatformLink]:
    """Return all platform links for a user."""
    result = await db.execute(
        select(PlatformLink).where(PlatformLink.user_id == user_id)
    )
    return list(result.scalars().all())


async def upsert_link(
    db: AsyncSession,
    user_id: uuid.UUID,
    platform: PlatformType,
    platform_user_id: str,
) -> PlatformLink:
    """Create or replace the link for this user+platform."""
    result = await db.execute(
        select(PlatformLink).where(
            PlatformLink.user_id == user_id,
            PlatformLink.platform == platform,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        link = PlatformLink(
            user_id=user_id,
            platform=platform,
            platform_user_id=platform_user_id,
        )
        db.add(link)
    else:
        link.platform_user_id = platform_user_id
        link.verified_at = None  # reset verification on re-link
    await db.commit()
    await db.refresh(link)
    return link


async def delete_link(
    db: AsyncSession,
    user_id: uuid.UUID,
    platform: PlatformType,
) -> None:
    """Remove the link for this user+platform. Raises ValueError if not found."""
    result = await db.execute(
        select(PlatformLink).where(
            PlatformLink.user_id == user_id,
            PlatformLink.platform == platform,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise ValueError(f"No {platform} link found")
    await db.delete(link)
    await db.commit()
