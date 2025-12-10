"""
Redis client utilities for caching and rate limiting.

Provides helper classes for common Redis operations.
"""

import json
from datetime import timedelta
from typing import Optional, Any, Callable
from functools import wraps
import hashlib

import redis

from app.config import settings


# Global Redis client
redis_client = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
)


class RateLimiter:
    """
    Token bucket rate limiter using Redis.

    Used to enforce API rate limits per user/tier.
    """

    def __init__(
        self,
        key_prefix: str = "ratelimit",
        default_limit: int = 100,
        default_window: int = 3600,  # 1 hour in seconds
    ):
        self.key_prefix = key_prefix
        self.default_limit = default_limit
        self.default_window = default_window

    def _get_key(self, identifier: str, resource: str = "default") -> str:
        """Generate Redis key for rate limit tracking."""
        return f"{self.key_prefix}:{resource}:{identifier}"

    def is_allowed(
        self,
        identifier: str,
        resource: str = "default",
        limit: Optional[int] = None,
        window: Optional[int] = None,
    ) -> tuple[bool, dict]:
        """
        Check if request is allowed under rate limit.

        Args:
            identifier: User ID or API key
            resource: Resource being accessed (e.g., 'api', 'alerts')
            limit: Max requests allowed in window
            window: Time window in seconds

        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        limit = limit or self.default_limit
        window = window or self.default_window
        key = self._get_key(identifier, resource)

        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        results = pipe.execute()

        current_count = results[0]
        ttl = results[1]

        # Set expiry on first request
        if ttl == -1:
            redis_client.expire(key, window)
            ttl = window

        remaining = max(0, limit - current_count)
        is_allowed = current_count <= limit

        return is_allowed, {
            "limit": limit,
            "remaining": remaining,
            "reset_in": ttl,
            "current": current_count,
        }

    def get_usage(self, identifier: str, resource: str = "default") -> int:
        """Get current usage count for identifier."""
        key = self._get_key(identifier, resource)
        count = redis_client.get(key)
        return int(count) if count else 0

    def reset(self, identifier: str, resource: str = "default") -> None:
        """Reset rate limit for identifier."""
        key = self._get_key(identifier, resource)
        redis_client.delete(key)


class Cache:
    """
    Redis-based cache with TTL support.

    Used for caching API responses, opportunity data, etc.
    """

    def __init__(self, key_prefix: str = "cache", default_ttl: int = 3600):
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl

    def _get_key(self, key: str) -> str:
        """Generate Redis key."""
        return f"{self.key_prefix}:{key}"

    def get(self, key: str) -> Optional[Any]:
        """
        Get cached value.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        redis_key = self._get_key(key)
        data = redis_client.get(redis_key)

        if data is None:
            return None

        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """
        Set cached value with TTL.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds
        """
        redis_key = self._get_key(key)
        ttl = ttl or self.default_ttl

        if isinstance(value, (dict, list)):
            data = json.dumps(value)
        else:
            data = str(value)

        redis_client.setex(redis_key, ttl, data)

    def delete(self, key: str) -> None:
        """Delete cached value."""
        redis_key = self._get_key(key)
        redis_client.delete(redis_key)

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        redis_key = self._get_key(key)
        return redis_client.exists(redis_key) > 0

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[int] = None,
    ) -> Any:
        """
        Get cached value or compute and cache it.

        Args:
            key: Cache key
            factory: Function to generate value if not cached
            ttl: Time to live in seconds

        Returns:
            Cached or newly computed value
        """
        value = self.get(key)
        if value is not None:
            return value

        value = factory()
        self.set(key, value, ttl)
        return value


def cached(
    key_prefix: str,
    ttl: int = 3600,
    key_builder: Optional[Callable[..., str]] = None,
):
    """
    Decorator for caching function results.

    Args:
        key_prefix: Prefix for cache keys
        ttl: Time to live in seconds
        key_builder: Optional function to build cache key from args

    Usage:
        @cached("opportunities", ttl=300)
        def get_opportunities(naics_code: str):
            ...
    """
    cache = Cache(key_prefix=key_prefix, default_ttl=ttl)

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default: hash of function name + args
                key_data = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
                cache_key = hashlib.md5(key_data.encode()).hexdigest()

            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Compute and cache
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result

        return wrapper

    return decorator


# Deduplication utilities
class Deduplicator:
    """
    Deduplication using Redis sets.

    Tracks which items have been processed to avoid duplicates.
    """

    def __init__(self, key_prefix: str = "dedup", ttl: int = 86400):
        self.key_prefix = key_prefix
        self.ttl = ttl

    def _get_key(self, namespace: str) -> str:
        """Generate Redis key for dedup set."""
        return f"{self.key_prefix}:{namespace}"

    def is_duplicate(self, namespace: str, item_id: str) -> bool:
        """
        Check if item has been processed.

        Args:
            namespace: Category of items (e.g., 'alerts', 'opportunities')
            item_id: Unique identifier for item

        Returns:
            True if item was already processed
        """
        key = self._get_key(namespace)
        return redis_client.sismember(key, item_id)

    def mark_processed(self, namespace: str, item_id: str) -> None:
        """
        Mark item as processed.

        Args:
            namespace: Category of items
            item_id: Unique identifier for item
        """
        key = self._get_key(namespace)
        pipe = redis_client.pipeline()
        pipe.sadd(key, item_id)
        pipe.expire(key, self.ttl)
        pipe.execute()

    def mark_many_processed(self, namespace: str, item_ids: list[str]) -> None:
        """Mark multiple items as processed."""
        if not item_ids:
            return

        key = self._get_key(namespace)
        pipe = redis_client.pipeline()
        pipe.sadd(key, *item_ids)
        pipe.expire(key, self.ttl)
        pipe.execute()

    def clear(self, namespace: str) -> None:
        """Clear all processed items in namespace."""
        key = self._get_key(namespace)
        redis_client.delete(key)


# Pre-configured instances
opportunity_cache = Cache(key_prefix="opportunities", default_ttl=1800)  # 30 min
api_rate_limiter = RateLimiter(key_prefix="api_rate", default_limit=100, default_window=3600)
alert_deduplicator = Deduplicator(key_prefix="alert_sent", ttl=604800)  # 7 days
