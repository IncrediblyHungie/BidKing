"""
Cleanup and maintenance tasks.

Handles data cleanup, archiving, and cache management.
"""

import logging
from datetime import datetime, timedelta

from celery import shared_task

from app.database import SessionLocal
from app.models import Opportunity, AlertSent, LaborRateCache, ContractAward
from app.utils.redis_client import redis_client

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def cleanup_archived_opportunities(self, days_old: int = 90):
    """
    Clean up old archived opportunities.

    Args:
        days_old: Delete opportunities archived more than this many days ago
    """
    logger.info(f"Cleaning up opportunities archived more than {days_old} days ago")

    cutoff_date = datetime.utcnow() - timedelta(days=days_old)

    with SessionLocal() as db:
        # Archive opportunities past their response deadline
        archived = db.query(Opportunity).filter(
            Opportunity.status == "active",
            Opportunity.response_deadline < datetime.utcnow() - timedelta(days=30),
        ).update({"status": "archived"})

        logger.info(f"Archived {archived} expired opportunities")

        # Delete very old archived opportunities
        deleted = db.query(Opportunity).filter(
            Opportunity.status == "archived",
            Opportunity.updated_at < cutoff_date,
        ).delete()

        logger.info(f"Deleted {deleted} old archived opportunities")

        db.commit()

    return {
        "archived": archived,
        "deleted": deleted,
    }


@shared_task(bind=True)
def cleanup_old_alerts(self, days_old: int = 365):
    """
    Clean up old alert sent records.

    Args:
        days_old: Delete records older than this many days
    """
    logger.info(f"Cleaning up alert records older than {days_old} days")

    cutoff_date = datetime.utcnow() - timedelta(days=days_old)

    with SessionLocal() as db:
        deleted = db.query(AlertSent).filter(
            AlertSent.sent_at < cutoff_date,
        ).delete()

        db.commit()

    logger.info(f"Deleted {deleted} old alert records")
    return {"deleted": deleted}


@shared_task(bind=True)
def cleanup_expired_cache(self):
    """
    Clean up expired cache entries in Redis and database.
    """
    logger.info("Cleaning up expired cache entries")

    # Database cache cleanup
    with SessionLocal() as db:
        # Clean expired labor rate cache
        expired_rates = db.query(LaborRateCache).filter(
            LaborRateCache.expires_at < datetime.utcnow(),
        ).delete()

        logger.info(f"Deleted {expired_rates} expired labor rate cache entries")

        db.commit()

    # Redis cache cleanup is handled automatically by TTL
    # But we can clean up any stale keys

    cleaned_redis = 0
    try:
        # Clean up old deduplication sets
        pattern = "dedup:*"
        for key in redis_client.scan_iter(match=pattern):
            ttl = redis_client.ttl(key)
            if ttl == -1:  # No expiry set
                redis_client.expire(key, 604800)  # Set 7-day expiry
                cleaned_redis += 1

        # Clean up old rate limit keys
        pattern = "ratelimit:*"
        for key in redis_client.scan_iter(match=pattern):
            ttl = redis_client.ttl(key)
            if ttl == -1:
                redis_client.expire(key, 3600)  # Set 1-hour expiry
                cleaned_redis += 1

    except Exception as e:
        logger.error(f"Error cleaning Redis cache: {e}")

    logger.info(f"Set expiry on {cleaned_redis} Redis keys")

    return {
        "expired_labor_rates": expired_rates,
        "redis_keys_updated": cleaned_redis,
    }


@shared_task(bind=True)
def cleanup_old_awards(self, years_old: int = 5):
    """
    Clean up very old contract award records.

    Args:
        years_old: Delete awards older than this many years
    """
    logger.info(f"Cleaning up contract awards older than {years_old} years")

    cutoff_date = datetime.utcnow() - timedelta(days=years_old * 365)

    with SessionLocal() as db:
        deleted = db.query(ContractAward).filter(
            ContractAward.award_date < cutoff_date.date(),
        ).delete()

        db.commit()

    logger.info(f"Deleted {deleted} old contract awards")
    return {"deleted": deleted}


@shared_task(bind=True)
def update_opportunity_status(self):
    """
    Update opportunity statuses based on deadlines.

    Marks opportunities as expired if past deadline.
    """
    logger.info("Updating opportunity statuses")

    now = datetime.utcnow()

    with SessionLocal() as db:
        # Mark expired opportunities
        expired = db.query(Opportunity).filter(
            Opportunity.status == "active",
            Opportunity.response_deadline < now,
        ).update({"status": "expired"})

        logger.info(f"Marked {expired} opportunities as expired")

        # Mark about-to-expire opportunities (within 48 hours)
        expiring_soon = db.query(Opportunity).filter(
            Opportunity.status == "active",
            Opportunity.response_deadline.between(now, now + timedelta(hours=48)),
        ).count()

        logger.info(f"Found {expiring_soon} opportunities expiring within 48 hours")

        db.commit()

    return {
        "expired": expired,
        "expiring_soon": expiring_soon,
    }


@shared_task(bind=True)
def generate_daily_stats(self):
    """
    Generate daily statistics for reporting.
    """
    logger.info("Generating daily statistics")

    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)

    with SessionLocal() as db:
        # Count new opportunities
        new_opportunities = db.query(Opportunity).filter(
            Opportunity.created_at >= datetime.combine(yesterday, datetime.min.time()),
            Opportunity.created_at < datetime.combine(today, datetime.min.time()),
        ).count()

        # Count active opportunities
        active_opportunities = db.query(Opportunity).filter(
            Opportunity.status == "active",
        ).count()

        # Count alerts sent
        alerts_sent = db.query(AlertSent).filter(
            AlertSent.sent_at >= datetime.combine(yesterday, datetime.min.time()),
            AlertSent.sent_at < datetime.combine(today, datetime.min.time()),
        ).count()

        # High score opportunities
        high_score = db.query(Opportunity).filter(
            Opportunity.status == "active",
            Opportunity.likelihood_score >= 70,
        ).count()

    stats = {
        "date": yesterday.isoformat(),
        "new_opportunities": new_opportunities,
        "active_opportunities": active_opportunities,
        "alerts_sent": alerts_sent,
        "high_score_opportunities": high_score,
        "generated_at": datetime.utcnow().isoformat(),
    }

    # Cache stats in Redis
    redis_client.setex(
        f"daily_stats:{yesterday.isoformat()}",
        604800,  # 7 days
        str(stats),
    )

    logger.info(f"Daily stats: {stats}")
    return stats
