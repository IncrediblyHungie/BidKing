"""User-related Pydantic schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    """Schema for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    company_name: Optional[str] = Field(None, max_length=255)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Validate password has minimum complexity."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """Schema for updating user profile."""

    email: Optional[EmailStr] = None
    company_name: Optional[str] = Field(None, max_length=255)
    notification_preferences: Optional[dict] = None


class UserResponse(BaseModel):
    """Schema for user response (public data only)."""

    id: UUID
    email: str
    company_name: Optional[str]
    subscription_tier: str
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Schema for authentication tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800  # 30 minutes in seconds


class TokenRefresh(BaseModel):
    """Schema for token refresh request."""

    refresh_token: str


class PasswordReset(BaseModel):
    """Schema for password reset request."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation."""

    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Validate password has minimum complexity."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v
