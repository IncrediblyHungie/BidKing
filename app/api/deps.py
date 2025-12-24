"""
API Dependencies

Common dependencies for authentication, database sessions, and rate limiting.
Supports both Supabase JWT tokens and internal JWT tokens.
"""

from typing import Generator, Optional
from uuid import UUID
import logging

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.database import SessionLocal
from app.models import User
from app.utils.security import decode_token
from app.utils.redis_client import api_rate_limiter
from app.config import SUBSCRIPTION_TIERS, settings

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)


def get_db() -> Generator:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def decode_supabase_token(token: str) -> Optional[dict]:
    """
    Decode and validate a Supabase JWT token.

    Supabase JWTs contain:
    - sub: User UUID
    - email: User email
    - aud: "authenticated"
    - role: "authenticated"
    """
    if not settings.supabase_jwt_secret:
        logger.warning("Supabase JWT secret not configured")
        return None

    # Log secret length for debugging (not the actual secret)
    logger.info(f"JWT secret length: {len(settings.supabase_jwt_secret)}")

    try:
        # Supabase uses HS256 algorithm
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except JWTError as e:
        logger.warning(f"Supabase token decode failed: {e}")
        # Try without audience verification as fallback
        try:
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            logger.info(f"Token decoded without audience check: sub={payload.get('sub')}")
            return payload
        except JWTError as e2:
            logger.warning(f"Supabase token decode failed (no aud): {e2}")
            # Decode without verification to see what's in the token
            try:
                unverified = jwt.decode(token, options={"verify_signature": False})
                logger.warning(f"Unverified token payload: iss={unverified.get('iss')}, aud={unverified.get('aud')}, sub={unverified.get('sub')}")
            except Exception as e3:
                logger.warning(f"Could not decode token at all: {e3}")
            return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Get current authenticated user from JWT token.
    Supports both Supabase JWTs and internal JWTs.

    Args:
        credentials: HTTP Bearer credentials
        db: Database session

    Returns:
        Authenticated User

    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    user_id = None
    email = None

    # Try Supabase token first
    payload = decode_supabase_token(token)
    if payload:
        user_id = payload.get("sub")
        email = payload.get("email")
    else:
        # Fall back to internal token
        payload = decode_token(token)
        if payload and payload.get("type") == "access":
            user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Try to find user by ID first
    user = db.query(User).filter(User.id == UUID(user_id)).first()

    # If not found and we have email from Supabase, create the user
    if not user and email:
        # Auto-create user from Supabase auth
        user = User(
            id=UUID(user_id),
            email=email,
            password_hash="",  # No password - Supabase handles auth
            is_active=True,
            email_verified=True,  # Supabase handles email verification
            subscription_tier="free",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created new user from Supabase: {email}")

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
    Supports both Supabase JWTs and internal JWTs.

    Useful for endpoints that work differently for authenticated users.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ")[1]
    user_id = None
    email = None

    # Try Supabase token first
    payload = decode_supabase_token(token)
    if payload:
        user_id = payload.get("sub")
        email = payload.get("email")
    else:
        # Fall back to internal token
        payload = decode_token(token)
        if payload and payload.get("type") == "access":
            user_id = payload.get("sub")

    if not user_id:
        return None

    # Try to find user
    user = db.query(User).filter(User.id == UUID(user_id)).first()

    # If not found and we have email from Supabase, create the user
    if not user and email:
        user = User(
            id=UUID(user_id),
            email=email,
            password_hash="",  # Supabase handles auth, we don't need a password
            is_active=True,
            email_verified=True,
            subscription_tier="free",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created new user from Supabase: {email}")

    return user


class RateLimitDependency:
    """
    Rate limiting dependency.

    Uses user's subscription tier to determine limits.
    """

    def __init__(self, resource: str = "api", require_auth: bool = True):
        self.resource = resource
        self.require_auth = require_auth

    async def __call__(
        self,
        request: Request,
        db: Session = Depends(get_db),
    ):
        # Try to get user from auth header
        user = await get_optional_user(request, db)

        if user:
            # Authenticated user - use their tier limits
            tier_config = SUBSCRIPTION_TIERS.get(
                user.subscription_tier,
                SUBSCRIPTION_TIERS["free"]
            )
            limit = tier_config["limits"]["api_calls_per_hour"]
            identifier = str(user.id)
        else:
            # Anonymous user - use IP-based rate limiting with lower limits
            client_ip = request.client.host if request.client else "unknown"
            limit = 100  # 100 requests per hour for anonymous users
            identifier = f"anon:{client_ip}"

        # Check rate limit
        allowed, info = api_rate_limiter.is_allowed(
            identifier=identifier,
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
rate_limit_search = RateLimitDependency(resource="search", require_auth=False)


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


async def get_user_from_token(request: Request, db: Session) -> Optional[User]:
    """
    Get user from request token without using FastAPI dependencies.

    This is for use in endpoints that need to optionally get the user
    without using Depends().
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ")[1]
    user_id = None
    email = None

    # Try Supabase token first
    payload = decode_supabase_token(token)
    if payload:
        user_id = payload.get("sub")
        email = payload.get("email")
    else:
        # Fall back to internal token
        payload = decode_token(token)
        if payload and payload.get("type") == "access":
            user_id = payload.get("sub")

    if not user_id:
        return None

    # Try to find user
    user = db.query(User).filter(User.id == UUID(user_id)).first()

    # If not found and we have email from Supabase, create the user
    if not user and email:
        user = User(
            id=UUID(user_id),
            email=email,
            password_hash="",
            is_active=True,
            email_verified=True,
            subscription_tier="free",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created new user from Supabase: {email}")

    return user
