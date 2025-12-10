"""Celery tasks package."""

from worker.tasks.sam_sync import sync_all_opportunities, sync_opportunities_by_naics
from worker.tasks.alert_matching import process_realtime_alerts, send_daily_digests
from worker.tasks.email_sending import send_alert_email, send_welcome_email
from worker.tasks.usaspending_sync import sync_recent_awards, update_naics_statistics
from worker.tasks.calc_sync import fetch_labor_rates
from worker.tasks.cleanup import cleanup_archived_opportunities, cleanup_expired_cache

__all__ = [
    "sync_all_opportunities",
    "sync_opportunities_by_naics",
    "process_realtime_alerts",
    "send_daily_digests",
    "send_alert_email",
    "send_welcome_email",
    "sync_recent_awards",
    "update_naics_statistics",
    "fetch_labor_rates",
    "cleanup_archived_opportunities",
    "cleanup_expired_cache",
]
