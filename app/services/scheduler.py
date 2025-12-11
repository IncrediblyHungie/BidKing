"""
Scheduler Service for BidKing

Automated background jobs for syncing data from SAM.gov and USAspending.gov
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = BackgroundScheduler()


def sync_usaspending_job():
    """
    Background job to sync USAspending contract awards.

    Runs daily at 6 AM UTC to fetch recent contract awards
    and create recompete opportunities for expiring contracts.
    """
    import httpx
    from app.database import SessionLocal
    from app.models import ContractAward, RecompeteOpportunity, Recipient
    from sqlalchemy.dialects.postgresql import insert

    logger.info("Starting scheduled USAspending sync...")

    USASPENDING_API_BASE = "https://api.usaspending.gov/api/v2"

    # NAICS codes for IT/Data/Cloud services
    NAICS_CODES = [
        "541511",  # Custom Computer Programming Services
        "541512",  # Computer Systems Design Services
        "541519",  # Other Computer Related Services
        "518210",  # Data Processing/Hosting - AWS, ETL
        "541690",  # Scientific/Technical Consulting - Data science
    ]

    days_back = 30  # Sync last 30 days of awards
    total_awards_synced = 0
    total_recompetes_created = 0

    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    for naics_code in NAICS_CODES:
        try:
            url = f"{USASPENDING_API_BASE}/search/spending_by_award/"

            payload = {
                "filters": {
                    "time_period": [
                        {"start_date": start_date, "end_date": end_date}
                    ],
                    "award_type_codes": ["A", "B", "C", "D"],
                    "naics_codes": [naics_code],
                },
                "fields": [
                    "Award ID",
                    "Recipient Name",
                    "Recipient UEI",
                    "Award Amount",
                    "Total Obligation",
                    "Start Date",
                    "End Date",
                    "Awarding Agency",
                    "Awarding Sub Agency",
                    "Award Type",
                    "NAICS Code",
                    "NAICS Description",
                    "PSC Code",
                    "Place of Performance City",
                    "Place of Performance State",
                    "Place of Performance Zip",
                    "generated_internal_id",
                ],
                "page": 1,
                "limit": 100,
                "sort": "Award Amount",
                "order": "desc",
            }

            with httpx.Client(timeout=60.0) as client:
                while True:
                    response = client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()

                    results = data.get("results", [])
                    if not results:
                        break

                    with SessionLocal() as db:
                        for award in results:
                            try:
                                award_id = award.get("generated_internal_id") or award.get("Award ID")
                                if not award_id:
                                    continue

                                start_dt = _parse_date(award.get("Start Date"))
                                end_dt = _parse_date(award.get("End Date"))

                                award_record = {
                                    "award_id": award_id,
                                    "piid": award.get("Award ID"),
                                    "award_type": award.get("Award Type") or "contract",
                                    "total_obligation": Decimal(str(award.get("Total Obligation") or 0)),
                                    "base_and_all_options_value": Decimal(str(award.get("Award Amount") or 0)),
                                    "award_date": start_dt,
                                    "period_of_performance_start": start_dt,
                                    "period_of_performance_end": end_dt,
                                    "naics_code": naics_code,
                                    "naics_description": award.get("NAICS Description"),
                                    "psc_code": award.get("PSC Code"),
                                    "awarding_agency_name": award.get("Awarding Agency"),
                                    "awarding_sub_agency_name": award.get("Awarding Sub Agency"),
                                    "recipient_uei": award.get("Recipient UEI"),
                                    "recipient_name": award.get("Recipient Name"),
                                    "pop_city": award.get("Place of Performance City"),
                                    "pop_state": award.get("Place of Performance State"),
                                    "pop_zip": award.get("Place of Performance Zip"),
                                    "fetched_at": datetime.utcnow(),
                                }

                                stmt = insert(ContractAward).values(**award_record)
                                stmt = stmt.on_conflict_do_update(
                                    index_elements=["award_id"],
                                    set_={
                                        "total_obligation": stmt.excluded.total_obligation,
                                        "period_of_performance_end": stmt.excluded.period_of_performance_end,
                                        "fetched_at": stmt.excluded.fetched_at,
                                    },
                                )
                                db.execute(stmt)
                                total_awards_synced += 1

                                # Create recompete if expiring within 365 days
                                today = datetime.utcnow().date()
                                if end_dt and end_dt >= today and end_dt <= (today + timedelta(days=365)):
                                    recompete_record = {
                                        "award_id": award_id,
                                        "piid": award.get("Award ID") or award_id,
                                        "period_of_performance_end": end_dt,
                                        "naics_code": naics_code,
                                        "total_value": Decimal(str(award.get("Award Amount") or 0)),
                                        "awarding_agency_name": award.get("Awarding Agency"),
                                        "incumbent_name": award.get("Recipient Name"),
                                        "incumbent_uei": award.get("Recipient UEI"),
                                        "status": "upcoming",
                                        "updated_at": datetime.utcnow(),
                                    }

                                    recompete_stmt = insert(RecompeteOpportunity).values(**recompete_record)
                                    recompete_stmt = recompete_stmt.on_conflict_do_update(
                                        index_elements=["award_id"],
                                        set_={
                                            "period_of_performance_end": recompete_stmt.excluded.period_of_performance_end,
                                            "total_value": recompete_stmt.excluded.total_value,
                                            "updated_at": recompete_stmt.excluded.updated_at,
                                        },
                                    )
                                    db.execute(recompete_stmt)
                                    total_recompetes_created += 1

                                # Update recipient info
                                if award.get("Recipient UEI"):
                                    recipient_record = {
                                        "uei": award.get("Recipient UEI"),
                                        "name": award.get("Recipient Name"),
                                        "last_updated": datetime.utcnow(),
                                    }
                                    recipient_stmt = insert(Recipient).values(**recipient_record)
                                    recipient_stmt = recipient_stmt.on_conflict_do_update(
                                        index_elements=["uei"],
                                        set_={
                                            "name": recipient_stmt.excluded.name,
                                            "last_updated": recipient_stmt.excluded.last_updated,
                                        },
                                    )
                                    db.execute(recipient_stmt)

                            except Exception as e:
                                logger.warning(f"Error processing award: {e}")
                                continue

                        db.commit()

                    if len(results) < payload["limit"] or payload["page"] >= 5:
                        break

                    payload["page"] += 1

        except Exception as e:
            logger.error(f"Error syncing NAICS {naics_code}: {e}")

    logger.info(f"USAspending sync completed: {total_awards_synced} awards, {total_recompetes_created} recompetes")


def sync_sam_gov_job():
    """
    Background job to sync SAM.gov opportunities.

    Runs daily at 7 AM UTC to fetch recent opportunities.
    Note: SAM.gov has stricter rate limits, so we're conservative.
    """
    import httpx
    from app.database import SessionLocal
    from app.models import Opportunity
    from app.config import settings
    from sqlalchemy.dialects.postgresql import insert

    if not settings.sam_gov_api_key:
        logger.warning("SAM.gov API key not configured, skipping sync")
        return

    logger.info("Starting scheduled SAM.gov sync...")

    NAICS_CODES = ["541511"]  # Start with just one to avoid rate limits

    days_back = 7  # Only sync last week to stay within quota
    total_synced = 0

    posted_from = (datetime.utcnow() - timedelta(days=days_back)).strftime("%m/%d/%Y")
    posted_to = datetime.utcnow().strftime("%m/%d/%Y")

    import time
    for i, naics_code in enumerate(NAICS_CODES):
        if i > 0:
            time.sleep(2)

        try:
            url = "https://api.sam.gov/opportunities/v2/search"
            params = {
                "api_key": settings.sam_gov_api_key,
                "postedFrom": posted_from,
                "postedTo": posted_to,
                "ncode": naics_code,
                "limit": 100,
                "offset": 0,
            }

            with httpx.Client(timeout=60.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            opportunities = data.get("opportunitiesData", [])

            with SessionLocal() as db:
                for opp_data in opportunities:
                    try:
                        opp_record = {
                            "notice_id": opp_data.get("noticeId"),
                            "solicitation_number": opp_data.get("solicitationNumber"),
                            "title": opp_data.get("title", "")[:500],
                            "description": opp_data.get("description"),
                            "posted_date": _parse_date(opp_data.get("postedDate")),
                            "response_deadline": _parse_datetime(opp_data.get("responseDeadLine")),
                            "type": opp_data.get("type"),
                            "naics_code": opp_data.get("naicsCode"),
                            "agency_name": opp_data.get("fullParentPathName", "").split(".")[0] if opp_data.get("fullParentPathName") else opp_data.get("departmentName"),
                            "office_name": opp_data.get("officeName"),
                            "pop_state": opp_data.get("placeOfPerformance", {}).get("state", {}).get("code") if opp_data.get("placeOfPerformance") else None,
                            "set_aside_type": opp_data.get("typeOfSetAside"),
                            "likelihood_score": 50,
                            "sam_gov_link": f"https://sam.gov/opp/{opp_data.get('noticeId')}/view",
                            "raw_data": opp_data,
                            "status": "active",
                            "fetched_at": datetime.utcnow(),
                        }

                        stmt = insert(Opportunity).values(**opp_record)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=["notice_id"],
                            set_={
                                "title": stmt.excluded.title,
                                "description": stmt.excluded.description,
                                "response_deadline": stmt.excluded.response_deadline,
                                "raw_data": stmt.excluded.raw_data,
                                "fetched_at": stmt.excluded.fetched_at,
                                "updated_at": datetime.utcnow(),
                            },
                        )
                        db.execute(stmt)
                        total_synced += 1

                    except Exception as e:
                        logger.warning(f"Error processing opportunity: {e}")
                        continue

                db.commit()

        except Exception as e:
            logger.error(f"Error syncing SAM.gov NAICS {naics_code}: {e}")

    logger.info(f"SAM.gov sync completed: {total_synced} opportunities")


def cleanup_expired_recompetes_job():
    """
    Remove recompetes that have already expired (contract ended).

    Runs daily at 5 AM UTC.
    """
    from app.database import SessionLocal
    from app.models import RecompeteOpportunity

    logger.info("Starting expired recompetes cleanup...")

    today = datetime.utcnow().date()

    with SessionLocal() as db:
        deleted = db.query(RecompeteOpportunity).filter(
            RecompeteOpportunity.period_of_performance_end < today
        ).delete()
        db.commit()

    logger.info(f"Cleaned up {deleted} expired recompetes")


def _parse_date(date_str):
    """Parse date string to date object."""
    if not date_str:
        return None
    try:
        for fmt in ["%Y-%m-%d", "%m/%d/%Y"]:
            try:
                return datetime.strptime(date_str[:10], fmt).date()
            except ValueError:
                continue
        return None
    except Exception:
        return None


def _parse_datetime(dt_str):
    """Parse datetime string to datetime object."""
    if not dt_str:
        return None
    try:
        if "T" in dt_str:
            dt_str = dt_str.replace("Z", "+00:00")
            return datetime.fromisoformat(dt_str.replace("+0000", "+00:00"))
        return datetime.strptime(dt_str, "%Y-%m-%d")
    except Exception:
        return None


def start_scheduler():
    """
    Start the background scheduler with all jobs configured.

    Schedule:
    - 5:00 AM UTC: Clean up expired recompetes
    - 6:00 AM UTC: Sync USAspending awards and recompetes
    - 7:00 AM UTC: Sync SAM.gov opportunities (when API quota resets)
    """
    if scheduler.running:
        logger.info("Scheduler already running")
        return

    # Clean up expired recompetes daily at 5 AM UTC
    scheduler.add_job(
        cleanup_expired_recompetes_job,
        CronTrigger(hour=5, minute=0),
        id="cleanup_expired_recompetes",
        replace_existing=True,
        name="Clean up expired recompetes",
    )

    # Sync USAspending daily at 6 AM UTC
    scheduler.add_job(
        sync_usaspending_job,
        CronTrigger(hour=6, minute=0),
        id="sync_usaspending",
        replace_existing=True,
        name="Sync USAspending awards",
    )

    # Sync SAM.gov daily at 7 AM UTC
    scheduler.add_job(
        sync_sam_gov_job,
        CronTrigger(hour=7, minute=0),
        id="sync_sam_gov",
        replace_existing=True,
        name="Sync SAM.gov opportunities",
    )

    scheduler.start()
    logger.info("Scheduler started with jobs:")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name}: {job.trigger}")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def get_scheduler_status():
    """Get current scheduler status and job info."""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })

    return {
        "running": scheduler.running,
        "jobs": jobs,
    }
