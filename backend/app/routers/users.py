"""User-facing API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from app.services import user_service

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
