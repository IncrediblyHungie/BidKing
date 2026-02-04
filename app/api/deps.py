"""
API Dependencies

Common dependencies for authentication, database sessions, and rate limiting.
Supports both Supabase JWT tokens and internal JWT tokens.
"""

from typing import Generator, Optional
from uuid import UUID
from datetime import date, datetime, timedelta
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


async def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current user and verify they have admin privileges.

    Args:
        current_user: Current authenticated user

    Returns:
        Admin User

    Raises:
        HTTPException: If user is not an admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def get_optional_admin_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Get admin user if authenticated, None otherwise.

    Used by endpoints that accept either admin JWT or sync secret auth.
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

    # Find user
    user = db.query(User).filter(User.id == UUID(user_id)).first()

    # Return user only if they're an admin
    if user and user.is_admin:
        return user
    return None


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
            # Use X-Forwarded-For header for requests behind proxy (Fly.io, nginx, etc.)
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                # X-Forwarded-For can be comma-separated; first IP is the client
                client_ip = forwarded.split(",")[0].strip()
            else:
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


class AIRateLimitDependency:
    """
    Rate limiting dependency specifically for AI generation endpoints.

    Enforces:
    - Daily generation limits (stored in Redis, resets at midnight UTC)
    - Monthly token quotas (stored in database via UsageTracking)

    Limits by tier:
    - Free: 3 generations/day, 50K tokens/month
    - Starter: 20 generations/day, 500K tokens/month
    - Pro: 100 generations/day, 2M tokens/month
    """

    async def __call__(
        self,
        request: Request,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> User:
        from app.models.subscription import UsageTracking

        tier_config = SUBSCRIPTION_TIERS.get(
            current_user.subscription_tier,
            SUBSCRIPTION_TIERS["free"]
        )
        daily_limit = tier_config["limits"]["ai_generations_per_day"]
        monthly_token_limit = tier_config["limits"]["ai_tokens_per_month"]

        # Check daily generation count via Redis
        today = date.today().isoformat()
        daily_key = f"ai_gen:{current_user.id}:{today}"

        try:
            current_count = api_rate_limiter.redis.get(daily_key)
            current_count = int(current_count) if current_count else 0
        except Exception as e:
            logger.warning(f"Redis error checking AI rate limit: {e}")
            current_count = 0

        if current_count >= daily_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "message": f"Daily AI generation limit ({daily_limit}) exceeded",
                    "limit": daily_limit,
                    "current": current_count,
                    "resets": "midnight UTC",
                    "upgrade_url": "/pricing" if current_user.subscription_tier == "free" else None,
                },
            )

        # Check monthly token usage from database
        month_start = datetime(date.today().year, date.today().month, 1)
        usage = db.query(UsageTracking).filter(
            UsageTracking.user_id == current_user.id,
            UsageTracking.period_start == month_start,
        ).first()

        tokens_used = usage.ai_tokens_used if usage and hasattr(usage, 'ai_tokens_used') else 0

        if tokens_used >= monthly_token_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "message": f"Monthly AI token quota ({monthly_token_limit:,}) exceeded",
                    "limit": monthly_token_limit,
                    "used": tokens_used,
                    "resets": "first of next month",
                    "upgrade_url": "/pricing" if current_user.subscription_tier != "pro" else None,
                },
            )

        # Increment daily counter in Redis (set to expire at midnight UTC)
        try:
            pipe = api_rate_limiter.redis.pipeline()
            pipe.incr(daily_key)
            # Calculate seconds until midnight UTC
            now = datetime.utcnow()
            midnight = datetime(now.year, now.month, now.day) + timedelta(days=1)
            seconds_until_midnight = int((midnight - now).total_seconds())
            pipe.expire(daily_key, seconds_until_midnight)
            pipe.execute()
        except Exception as e:
            logger.warning(f"Redis error incrementing AI counter: {e}")

        # Store request state for token tracking after generation
        request.state.ai_rate_limit_user = current_user
        request.state.ai_rate_limit_db = db

        return current_user


# AI rate limiting dependency
rate_limit_ai = AIRateLimitDependency()


def track_ai_token_usage(db: Session, user_id: UUID, tokens_used: int):
    """
    Track AI token usage in the database.
    Call this after successful AI generation to update monthly totals.
    Non-blocking - errors are logged but don't fail the request.
    """
    try:
        from app.models.subscription import UsageTracking

        month_start = datetime(date.today().year, date.today().month, 1)

        usage = db.query(UsageTracking).filter(
            UsageTracking.user_id == user_id,
            UsageTracking.period_start == month_start,
        ).first()

        if not usage:
            usage = UsageTracking(
                user_id=user_id,
                period_start=month_start,
                ai_generations=1,
                ai_tokens_used=tokens_used,
            )
            db.add(usage)
        else:
            if hasattr(usage, 'ai_generations'):
                usage.ai_generations = (usage.ai_generations or 0) + 1
            if hasattr(usage, 'ai_tokens_used'):
                usage.ai_tokens_used = (usage.ai_tokens_used or 0) + tokens_used

        db.commit()
    except Exception as e:
        logger.warning(f"Failed to track AI token usage: {e}")
        db.rollback()
