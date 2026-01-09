"""
Alert matching and notification tasks.

Matches opportunities to user alert profiles and sends notifications.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from celery import shared_task
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.models import User, AlertProfile, Opportunity, AlertSent, UsageTracking
from app.config import settings, SUBSCRIPTION_TIERS
from app.utils.redis_client import alert_deduplicator

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_realtime_alerts(self):
    """
    Process realtime alert profiles.

    Finds new opportunities that match realtime profiles and sends alerts.
    """
    logger.info("Processing realtime alerts")

    with SessionLocal() as db:
        # Get active realtime profiles
        profiles = db.query(AlertProfile).filter(
            AlertProfile.is_active == True,
            AlertProfile.alert_frequency == "realtime",
        ).options(joinedload(AlertProfile.user)).all()

        logger.info(f"Found {len(profiles)} realtime alert profiles")

        alerts_sent = 0
        for profile in profiles:
            try:
                # Check user's subscription limits
                if not _can_send_alert(db, profile.user):
                    logger.debug(f"User {profile.user_id} has reached alert limit")
                    continue

                # Find matching opportunities since last alert
                since = profile.last_alert_sent or (datetime.utcnow() - timedelta(hours=1))
                matches = _find_matching_opportunities(db, profile, since)

                if matches:
                    # Queue email sending
                    from worker.tasks.email_sending import send_alert_email
                    send_alert_email.delay(
                        user_id=str(profile.user_id),
                        profile_id=str(profile.id),
                        opportunity_ids=[str(m.id) for m in matches],
                        alert_type="realtime",
                    )

                    # Update profile
                    profile.last_alert_sent = datetime.utcnow()
                    profile.match_count += len(matches)
                    alerts_sent += 1

                    # Track usage
                    _track_alert_usage(db, profile.user_id)

            except Exception as e:
                logger.error(f"Error processing profile {profile.id}: {e}")
                continue

        db.commit()

    logger.info(f"Sent {alerts_sent} realtime alerts")
    return {"alerts_sent": alerts_sent}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_daily_digests(self):
    """
    Send daily digest emails to users with daily alert profiles.
    """
    logger.info("Sending daily digest alerts")

    with SessionLocal() as db:
        # Get active daily profiles
        profiles = db.query(AlertProfile).filter(
            AlertProfile.is_active == True,
            AlertProfile.alert_frequency == "daily",
        ).options(joinedload(AlertProfile.user)).all()

        logger.info(f"Found {len(profiles)} daily alert profiles")

        digests_sent = 0
        for profile in profiles:
            try:
                # Check user's subscription limits
                if not _can_send_alert(db, profile.user):
                    continue

                # Find matches from last 24 hours
                since = datetime.utcnow() - timedelta(days=1)
                matches = _find_matching_opportunities(db, profile, since)

                if matches:
                    from worker.tasks.email_sending import send_alert_email
                    send_alert_email.delay(
                        user_id=str(profile.user_id),
                        profile_id=str(profile.id),
                        opportunity_ids=[str(m.id) for m in matches],
                        alert_type="daily_digest",
                    )

                    profile.last_alert_sent = datetime.utcnow()
                    profile.match_count += len(matches)
                    digests_sent += 1

                    _track_alert_usage(db, profile.user_id)

            except Exception as e:
                logger.error(f"Error processing daily digest for profile {profile.id}: {e}")
                continue

        db.commit()

    logger.info(f"Sent {digests_sent} daily digests")
    return {"digests_sent": digests_sent}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_weekly_digests(self):
    """
    Send weekly digest emails to users with weekly alert profiles.
    """
    logger.info("Sending weekly digest alerts")

    with SessionLocal() as db:
        profiles = db.query(AlertProfile).filter(
            AlertProfile.is_active == True,
            AlertProfile.alert_frequency == "weekly",
        ).options(joinedload(AlertProfile.user)).all()

        logger.info(f"Found {len(profiles)} weekly alert profiles")

        digests_sent = 0
        for profile in profiles:
            try:
                if not _can_send_alert(db, profile.user):
                    continue

                # Find matches from last 7 days
                since = datetime.utcnow() - timedelta(days=7)
                matches = _find_matching_opportunities(db, profile, since)

                if matches:
                    from worker.tasks.email_sending import send_alert_email
                    send_alert_email.delay(
                        user_id=str(profile.user_id),
                        profile_id=str(profile.id),
                        opportunity_ids=[str(m.id) for m in matches],
                        alert_type="weekly_digest",
                    )

                    profile.last_alert_sent = datetime.utcnow()
                    profile.match_count += len(matches)
                    digests_sent += 1

                    _track_alert_usage(db, profile.user_id)

            except Exception as e:
                logger.error(f"Error processing weekly digest for profile {profile.id}: {e}")
                continue

        db.commit()

    logger.info(f"Sent {digests_sent} weekly digests")
    return {"digests_sent": digests_sent}


def _find_matching_opportunities(
    db,
    profile: AlertProfile,
    since: datetime,
) -> list[Opportunity]:
    """
    Find opportunities matching an alert profile.

    Args:
        db: Database session
        profile: Alert profile to match against
        since: Only consider opportunities fetched after this time

    Returns:
        List of matching opportunities
    """
    query = db.query(Opportunity).filter(
        Opportunity.status == "active",
        Opportunity.fetched_at >= since,
        Opportunity.likelihood_score >= profile.min_likelihood_score,
    )

    # NAICS code filter
    if profile.naics_codes:
        naics_conditions = [
            Opportunity.naics_code.like(f"{code}%")
            for code in profile.naics_codes
        ]
        query = query.filter(or_(*naics_conditions))

    # PSC code filter
    if profile.psc_codes:
        query = query.filter(Opportunity.psc_code.in_(profile.psc_codes))

    # State filter
    if profile.states:
        query = query.filter(Opportunity.pop_state.in_(profile.states))

    # Agency filter
    if profile.agencies:
        agency_conditions = [
            Opportunity.agency_name.ilike(f"%{agency}%")
            for agency in profile.agencies
        ]
        query = query.filter(or_(*agency_conditions))

    # Set-aside filter
    if profile.set_aside_types:
        query = query.filter(Opportunity.set_aside_type.in_(profile.set_aside_types))

    # Keyword filters
    if profile.keywords:
        keyword_conditions = []
        for keyword in profile.keywords:
            keyword_conditions.append(
                or_(
                    Opportunity.title.ilike(f"%{keyword}%"),
                    Opportunity.description.ilike(f"%{keyword}%"),
                )
            )
        query = query.filter(or_(*keyword_conditions))

    # Excluded keywords
    if profile.excluded_keywords:
        for keyword in profile.excluded_keywords:
            query = query.filter(
                ~Opportunity.title.ilike(f"%{keyword}%"),
                ~Opportunity.description.ilike(f"%{keyword}%"),
            )

    # Filter out already-sent opportunities
    opportunities = query.order_by(Opportunity.likelihood_score.desc()).limit(50).all()

    # Deduplicate using Redis
    unsent = []
    for opp in opportunities:
        dedup_key = f"{profile.id}:{opp.id}"
        if not alert_deduplicator.is_duplicate("alerts", dedup_key):
            unsent.append(opp)
            alert_deduplicator.mark_processed("alerts", dedup_key)

    return unsent


def _can_send_alert(db, user: User) -> bool:
    """Check if user can receive more alerts based on subscription limits."""
    tier_config = SUBSCRIPTION_TIERS.get(user.subscription_tier, SUBSCRIPTION_TIERS["free"])
    limit = tier_config["limits"]["alerts_per_month"]

    # Get current month's usage
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    usage = db.query(UsageTracking).filter(
        UsageTracking.user_id == user.id,
        UsageTracking.month >= month_start,
    ).first()

    if not usage:
        return True

    return usage.alerts_sent < limit


def _track_alert_usage(db, user_id: UUID):
    """Track alert usage for a user."""
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    usage = db.query(UsageTracking).filter(
        UsageTracking.user_id == user_id,
        UsageTracking.month == month_start,
    ).first()

    if usage:
        usage.alerts_sent += 1
    else:
        usage = UsageTracking(
            user_id=user_id,
            month=month_start,
            alerts_sent=1,
        )
        db.add(usage)
