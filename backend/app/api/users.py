"""API routes for user management."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user, get_db_session
from app.models.auth import User, Role, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


def check_permission(user: User, required_permission: str):
    """Ensure the user has the required permission."""
    perms = {p.name for r in user.roles for p in r.permissions}
    if required_permission not in perms:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required permission: {required_permission}",
        )


@router.get("/", response_model=list[UserResponse])
async def list_users(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """List all users. Requires users.read or users.manage."""
    perms = {p.name for r in current_user.roles for p in r.permissions}
    if "users.read" not in perms and "users.manage" not in perms:
        raise HTTPException(status_code=403, detail="Forbidden")

    stmt = select(User).order_by(User.email)
    result = await db.scalars(stmt)
    return list(result.all())


class UpdateUserRolesRequest(BaseModel):
    roles: list[str]


@router.patch("/{user_id}/roles", response_model=UserResponse)
async def update_user_roles(
    user_id: uuid.UUID,
    request: UpdateUserRolesRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Update roles for a user. Requires users.manage."""
    check_permission(current_user, "users.manage")

    stmt = select(User).where(User.id == user_id)
    result = await db.scalars(stmt)
    user = result.first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Fetch requested roles
    role_stmt = select(Role).where(Role.name.in_(request.roles))
    role_result = await db.scalars(role_stmt)
    new_roles = list(role_result.all())

    user.roles = new_roles
    await db.commit()
    await db.refresh(user)

    return user


class UpdateUserStatusRequest(BaseModel):
    is_active: bool


@router.patch("/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: uuid.UUID,
    request: UpdateUserStatusRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Update active status for a user. Requires users.manage."""
    check_permission(current_user, "users.manage")

    stmt = select(User).where(User.id == user_id)
    result = await db.scalars(stmt)
    user = result.first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = request.is_active
    await db.commit()
    await db.refresh(user)

    return user
