"""
Celery application configuration.

Defines the Celery app instance and beat schedule for periodic tasks.
"""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

# Create Celery app
celery_app = Celery(
    "bidking",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "worker.tasks.sam_sync",
        "worker.tasks.alert_matching",
        "worker.tasks.email_sending",
        "worker.tasks.usaspending_sync",
        "worker.tasks.calc_sync",
        "worker.tasks.cleanup",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution settings
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,  # Reject task if worker dies
    worker_prefetch_multiplier=1,  # One task at a time per worker

    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour

    # Task routing (optional - for scaling)
    task_routes={
        "worker.tasks.sam_sync.*": {"queue": "sync"},
        "worker.tasks.usaspending_sync.*": {"queue": "sync"},
        "worker.tasks.calc_sync.*": {"queue": "sync"},
        "worker.tasks.alert_matching.*": {"queue": "alerts"},
        "worker.tasks.email_sending.*": {"queue": "emails"},
        "worker.tasks.cleanup.*": {"queue": "maintenance"},
    },

    # Rate limiting
    task_annotations={
        "worker.tasks.sam_sync.sync_opportunities": {"rate_limit": "10/m"},
        "worker.tasks.usaspending_sync.sync_awards": {"rate_limit": "20/m"},
        "worker.tasks.email_sending.send_alert_email": {"rate_limit": "30/m"},
    },
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    # SAM.gov sync - every 4 hours
    "sync-sam-opportunities": {
        "task": "worker.tasks.sam_sync.sync_all_opportunities",
        "schedule": crontab(minute=0, hour="*/4"),
        "options": {"queue": "sync"},
    },

    # Process alert matches - every hour
    "process-realtime-alerts": {
        "task": "worker.tasks.alert_matching.process_realtime_alerts",
        "schedule": crontab(minute=15),  # 15 minutes past each hour
        "options": {"queue": "alerts"},
    },

    # Daily digest alerts - every day at 6 AM UTC
    "send-daily-digests": {
        "task": "worker.tasks.alert_matching.send_daily_digests",
        "schedule": crontab(minute=0, hour=6),
        "options": {"queue": "alerts"},
    },

    # Weekly digest alerts - every Monday at 6 AM UTC
    "send-weekly-digests": {
        "task": "worker.tasks.alert_matching.send_weekly_digests",
        "schedule": crontab(minute=0, hour=6, day_of_week=1),
        "options": {"queue": "alerts"},
    },

    # USAspending sync - daily at 2 AM UTC
    "sync-usaspending": {
        "task": "worker.tasks.usaspending_sync.sync_recent_awards",
        "schedule": crontab(minute=0, hour=2),
        "options": {"queue": "sync"},
    },

    # NAICS statistics update - weekly on Sunday at 3 AM UTC
    "update-naics-statistics": {
        "task": "worker.tasks.usaspending_sync.update_naics_statistics",
        "schedule": crontab(minute=0, hour=3, day_of_week=0),
        "options": {"queue": "sync"},
    },

    # Cleanup old data - daily at 4 AM UTC
    "cleanup-old-opportunities": {
        "task": "worker.tasks.cleanup.cleanup_archived_opportunities",
        "schedule": crontab(minute=0, hour=4),
        "options": {"queue": "maintenance"},
    },

    # Cleanup expired cache - every 6 hours
    "cleanup-cache": {
        "task": "worker.tasks.cleanup.cleanup_expired_cache",
        "schedule": crontab(minute=30, hour="*/6"),
        "options": {"queue": "maintenance"},
    },
}
