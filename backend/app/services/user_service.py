"""User profile business logic."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserUpdate


async def update_user(
    db: AsyncSession,
    user: User,
    data: UserUpdate,
) -> User:
    """Apply only the provided profile fields to the user."""
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_count(db: AsyncSession) -> int:
    """Return the total number of registered users."""
    from sqlalchemy import func, select
    result = await db.scalar(select(func.count()).select_from(User))
    return result or 0


async def get_all_users(db: AsyncSession) -> list[User]:
    """Return all users ordered by creation date (admin view)."""
    from sqlalchemy import select
    result = await db.execute(select(User).order_by(User.created_at))
    return list(result.scalars().all())


async def set_admin(db: AsyncSession, user: User, is_admin: bool) -> User:
    """Grant or revoke admin status for a user."""
    user.is_admin = is_admin
    await db.commit()
    await db.refresh(user)
    return user
