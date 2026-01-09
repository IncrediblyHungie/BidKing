"""
SAM.gov opportunity synchronization tasks.

Fetches opportunities from SAM.gov API and stores them in the database.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from celery import shared_task
from sqlalchemy.dialects.postgresql import insert

from app.database import SessionLocal
from app.models import Opportunity, PointOfContact
from app.config import settings

logger = logging.getLogger(__name__)

# NAICS codes to sync (IT/software focused)
DEFAULT_NAICS_CODES = [
    "541511",  # Custom Computer Programming Services
    "541512",  # Computer Systems Design Services
    "541519",  # Other Computer Related Services
    "518210",  # Data Processing, Hosting, and Related Services
    "541690",  # Other Scientific and Technical Consulting
    "541712",  # R&D in Physical, Engineering, and Life Sciences
    "541330",  # Engineering Services
    "541990",  # All Other Professional, Scientific, and Technical Services
]


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_all_opportunities(self, days_back: int = 7):
    """
    Sync opportunities for all configured NAICS codes.

    Args:
        days_back: Number of days to look back for opportunities
    """
    logger.info(f"Starting SAM.gov sync for {len(DEFAULT_NAICS_CODES)} NAICS codes")

    total_synced = 0
    total_new = 0

    for naics_code in DEFAULT_NAICS_CODES:
        try:
            result = sync_opportunities_by_naics.delay(naics_code, days_back)
            # Don't wait for result - let them run in parallel
            logger.info(f"Queued sync for NAICS {naics_code}")
        except Exception as e:
            logger.error(f"Failed to queue sync for NAICS {naics_code}: {e}")

    return {
        "status": "queued",
        "naics_codes": len(DEFAULT_NAICS_CODES),
    }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_opportunities_by_naics(
    self,
    naics_code: str,
    days_back: int = 7,
    limit: int = 1000,
):
    """
    Sync opportunities for a specific NAICS code.

    Args:
        naics_code: NAICS code to filter by
        days_back: Number of days to look back
        limit: Maximum opportunities to fetch per request
    """
    import httpx
    from app.services.scoring import calculate_likelihood_score

    logger.info(f"Syncing opportunities for NAICS {naics_code}")

    # Calculate date range
    posted_from = (datetime.utcnow() - timedelta(days=days_back)).strftime("%m/%d/%Y")
    posted_to = datetime.utcnow().strftime("%m/%d/%Y")

    # SAM.gov API request
    url = "https://api.sam.gov/opportunities/v2/search"
    params = {
        "api_key": settings.sam_gov_api_key,
        "postedFrom": posted_from,
        "postedTo": posted_to,
        "ncode": naics_code,
        "limit": limit,
        "offset": 0,
    }

    synced_count = 0
    new_count = 0

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        opportunities = data.get("opportunitiesData", [])
        logger.info(f"Fetched {len(opportunities)} opportunities for NAICS {naics_code}")

        with SessionLocal() as db:
            for opp_data in opportunities:
                try:
                    # Calculate likelihood score
                    score = calculate_likelihood_score(opp_data)

                    # Skip low-score opportunities
                    if score < 30:
                        continue

                    # Prepare opportunity record
                    opp_record = {
                        "notice_id": opp_data.get("noticeId"),
                        "solicitation_number": opp_data.get("solicitationNumber"),
                        "title": opp_data.get("title", "")[:500],
                        "description": opp_data.get("description"),
                        "posted_date": _parse_date(opp_data.get("postedDate")),
                        "response_deadline": _parse_datetime(opp_data.get("responseDeadLine")),
                        "archive_date": _parse_date(opp_data.get("archiveDate")),
                        "type": opp_data.get("type"),
                        "type_description": opp_data.get("typeOfSetAsideDescription"),
                        "naics_code": opp_data.get("naicsCode"),
                        "naics_description": opp_data.get("naicsCodes", [{}])[0].get("description") if opp_data.get("naicsCodes") else None,
                        "psc_code": opp_data.get("classificationCode"),
                        "agency_name": opp_data.get("fullParentPathName", "").split(".")[0] if opp_data.get("fullParentPathName") else opp_data.get("departmentName"),
                        "sub_agency_name": opp_data.get("subtierAgencyName"),
                        "office_name": opp_data.get("officeName"),
                        "pop_city": opp_data.get("placeOfPerformance", {}).get("city", {}).get("name") if opp_data.get("placeOfPerformance") else None,
                        "pop_state": opp_data.get("placeOfPerformance", {}).get("state", {}).get("code") if opp_data.get("placeOfPerformance") else None,
                        "pop_zip": opp_data.get("placeOfPerformance", {}).get("zip") if opp_data.get("placeOfPerformance") else None,
                        "pop_country": opp_data.get("placeOfPerformance", {}).get("country", {}).get("code") if opp_data.get("placeOfPerformance") else None,
                        "set_aside_type": opp_data.get("typeOfSetAside"),
                        "set_aside_description": opp_data.get("typeOfSetAsideDescription"),
                        "likelihood_score": score,
                        "sam_gov_link": f"https://sam.gov/opp/{opp_data.get('noticeId')}/view",
                        "raw_data": opp_data,
                        "status": "active",
                        "fetched_at": datetime.utcnow(),
                    }

                    # Upsert opportunity
                    stmt = insert(Opportunity).values(**opp_record)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["notice_id"],
                        set_={
                            "title": stmt.excluded.title,
                            "description": stmt.excluded.description,
                            "response_deadline": stmt.excluded.response_deadline,
                            "likelihood_score": stmt.excluded.likelihood_score,
                            "raw_data": stmt.excluded.raw_data,
                            "fetched_at": stmt.excluded.fetched_at,
                            "updated_at": datetime.utcnow(),
                        },
                    )
                    result = db.execute(stmt)

                    if result.rowcount > 0:
                        synced_count += 1
                        # Check if it was an insert (new) vs update
                        existing = db.query(Opportunity).filter_by(
                            notice_id=opp_data.get("noticeId")
                        ).first()
                        if existing and existing.created_at >= datetime.utcnow() - timedelta(minutes=1):
                            new_count += 1

                    # Handle points of contact
                    contacts = opp_data.get("pointOfContact", [])
                    if contacts and existing:
                        for contact in contacts:
                            contact_record = {
                                "opportunity_id": existing.id,
                                "name": contact.get("fullName"),
                                "email": contact.get("email"),
                                "phone": contact.get("phone"),
                                "title": contact.get("title"),
                                "type": contact.get("type"),
                            }
                            contact_stmt = insert(PointOfContact).values(**contact_record)
                            contact_stmt = contact_stmt.on_conflict_do_nothing()
                            db.execute(contact_stmt)

                except Exception as e:
                    logger.error(f"Error processing opportunity {opp_data.get('noticeId')}: {e}")
                    continue

            db.commit()

    except httpx.HTTPError as e:
        logger.error(f"HTTP error syncing NAICS {naics_code}: {e}")
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(f"Error syncing NAICS {naics_code}: {e}")
        raise self.retry(exc=e)

    logger.info(f"Synced {synced_count} opportunities ({new_count} new) for NAICS {naics_code}")

    return {
        "naics_code": naics_code,
        "synced": synced_count,
        "new": new_count,
    }


def _parse_date(date_str: Optional[str]):
    """Parse date string to date object."""
    if not date_str:
        return None
    try:
        # SAM.gov uses various formats
        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"]:
            try:
                return datetime.strptime(date_str[:10], fmt[:len(date_str[:10])+1]).date()
            except ValueError:
                continue
        return None
    except Exception:
        return None


def _parse_datetime(dt_str: Optional[str]):
    """Parse datetime string to datetime object."""
    if not dt_str:
        return None
    try:
        # Handle ISO format with timezone
        if "T" in dt_str:
            dt_str = dt_str.replace("Z", "+00:00")
            return datetime.fromisoformat(dt_str.replace("+0000", "+00:00"))
        # Handle date-only format
        return datetime.strptime(dt_str, "%Y-%m-%d")
    except Exception:
        return None
