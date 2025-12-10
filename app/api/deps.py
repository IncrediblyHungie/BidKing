"""
API Dependencies

Common dependencies for authentication, database sessions, and rate limiting.
"""

from typing import Generator, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User
from app.utils.security import decode_token
from app.utils.redis_client import api_rate_limiter
from app.config import SUBSCRIPTION_TIERS

# Security scheme
security = HTTPBearer()


def get_db() -> Generator:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Get current authenticated user from JWT token.

    Args:
        credentials: HTTP Bearer credentials
        db: Database session

    Returns:
        Authenticated User

    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials

    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == UUID(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


async def get_current_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current user and verify email is confirmed.

    Args:
        current_user: Current authenticated user

    Returns:
        Verified User

    Raises:
        HTTPException: If email not verified
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required",
        )
    return current_user


async def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise.

    Useful for endpoints that work differently for authenticated users.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ")[1]
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    return db.query(User).filter(User.id == UUID(user_id)).first()


class RateLimitDependency:
    """
    Rate limiting dependency.

    Uses user's subscription tier to determine limits.
    """

    def __init__(self, resource: str = "api"):
        self.resource = resource

    async def __call__(
        self,
        request: Request,
        current_user: User = Depends(get_current_user),
    ):
        # Get tier limits
        tier_config = SUBSCRIPTION_TIERS.get(
            current_user.subscription_tier,
            SUBSCRIPTION_TIERS["free"]
        )
        limit = tier_config["limits"]["api_calls_per_hour"]

        # Check rate limit
        allowed, info = api_rate_limiter.is_allowed(
            identifier=str(current_user.id),
            resource=self.resource,
            limit=limit,
            window=3600,
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "message": "Rate limit exceeded",
                    "limit": info["limit"],
                    "reset_in": info["reset_in"],
                },
                headers={
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": str(info["remaining"]),
                    "X-RateLimit-Reset": str(info["reset_in"]),
                },
            )

        # Add rate limit headers to response
        request.state.rate_limit_info = info


# Convenience dependencies
rate_limit = RateLimitDependency()
rate_limit_search = RateLimitDependency(resource="search")


class TierRequirement:
    """
    Dependency to check subscription tier requirements.
    """

    def __init__(self, min_tier: str):
        self.min_tier = min_tier
        self.tier_order = ["free", "starter", "pro"]

    async def __call__(self, current_user: User = Depends(get_current_user)):
        user_tier_index = self.tier_order.index(current_user.subscription_tier)
        required_tier_index = self.tier_order.index(self.min_tier)

        if user_tier_index < required_tier_index:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires {self.min_tier} tier or higher",
            )

        return current_user


# Tier requirements
require_starter = TierRequirement("starter")
require_pro = TierRequirement("pro")
