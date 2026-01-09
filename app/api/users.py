"""
User management API endpoints.

Handles user profile updates and account management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import User
from app.schemas.user import UserUpdate, UserResponse, UserNotificationSettings
from app.utils.security import get_password_hash

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's profile.
    """
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update current user's profile.
    """
    update_data = user_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)

    return current_user


@router.post("/me/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change user's password.
    """
    from app.utils.security import verify_password

    if not verify_password(current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password",
        )

    current_user.hashed_password = get_password_hash(new_password)
    db.commit()

    return {"message": "Password changed successfully"}


@router.delete("/me")
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete user's account.

    This marks the account as inactive rather than hard deleting.
    """
    current_user.is_active = False
    db.commit()

    return {"message": "Account deleted successfully"}


@router.get("/me/notification-settings", response_model=UserNotificationSettings)
async def get_notification_settings(
    current_user: User = Depends(get_current_user),
):
    """Get current user's notification settings."""
    return UserNotificationSettings(
        email_reminders_enabled=current_user.email_reminders_enabled,
        email_deadline_warnings=current_user.email_deadline_warnings,
        deadline_warning_days=current_user.deadline_warning_days,
    )


@router.patch("/me/notification-settings", response_model=UserNotificationSettings)
async def update_notification_settings(
    settings: UserNotificationSettings,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current user's notification settings."""
    current_user.email_reminders_enabled = settings.email_reminders_enabled
    current_user.email_deadline_warnings = settings.email_deadline_warnings
    current_user.deadline_warning_days = settings.deadline_warning_days

    db.commit()
    db.refresh(current_user)

    return UserNotificationSettings(
        email_reminders_enabled=current_user.email_reminders_enabled,
        email_deadline_warnings=current_user.email_deadline_warnings,
        deadline_warning_days=current_user.deadline_warning_days,
    )
