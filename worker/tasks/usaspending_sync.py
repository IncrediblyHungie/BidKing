"""
USAspending.gov synchronization tasks.

Fetches contract award data for market intelligence.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from celery import shared_task
import httpx
from sqlalchemy.dialects.postgresql import insert

from app.database import SessionLocal
from app.models import ContractAward, NAICSStatistics, Recipient, RecompeteOpportunity

logger = logging.getLogger(__name__)

# USAspending API base URL
USASPENDING_API_BASE = "https://api.usaspending.gov/api/v2"


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def sync_recent_awards(self, days_back: int = 30, naics_codes: Optional[list[str]] = None):
    """
    Sync recent contract awards from USAspending.gov.

    Args:
        days_back: Number of days to look back
        naics_codes: Optional list of NAICS codes to filter
    """
    logger.info(f"Syncing USAspending awards for last {days_back} days")

    if naics_codes is None:
        naics_codes = [
            "541511", "541512", "541519", "518210",
            "541690", "541712", "541330", "541990",
        ]

    # Calculate date range
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    total_synced = 0

    for naics_code in naics_codes:
        try:
            synced = _sync_awards_for_naics(naics_code, start_date, end_date)
            total_synced += synced
            logger.info(f"Synced {synced} awards for NAICS {naics_code}")
        except Exception as e:
            logger.error(f"Error syncing NAICS {naics_code}: {e}")
            continue

    logger.info(f"Total awards synced: {total_synced}")
    return {"synced": total_synced}


def _sync_awards_for_naics(naics_code: str, start_date: str, end_date: str) -> int:
    """Sync awards for a specific NAICS code."""
    url = f"{USASPENDING_API_BASE}/search/spending_by_award/"

    payload = {
        "filters": {
            "time_period": [
                {"start_date": start_date, "end_date": end_date}
            ],
            "award_type_codes": ["A", "B", "C", "D"],  # Contracts only
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
            "recipient_id",
            "generated_internal_id",
            "Type of Set Aside",
        ],
        "page": 1,
        "limit": 100,
        "sort": "Award Amount",
        "order": "desc",
    }

    synced = 0

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
                        award_record = {
                            "award_id": award.get("generated_internal_id") or award.get("Award ID"),
                            "piid": award.get("Award ID"),
                            "award_type": award.get("Award Type"),
                            "total_obligation": Decimal(str(award.get("Total Obligation") or 0)),
                            "base_and_all_options_value": Decimal(str(award.get("Award Amount") or 0)),
                            "award_date": _parse_date(award.get("Start Date")),
                            "period_of_performance_start": _parse_date(award.get("Start Date")),
                            "period_of_performance_end": _parse_date(award.get("End Date")),
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
                            "set_aside_type": award.get("Type of Set Aside"),
                            "fetched_at": datetime.utcnow(),
                        }

                        stmt = insert(ContractAward).values(**award_record)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=["award_id"],
                            set_={
                                "total_obligation": stmt.excluded.total_obligation,
                                "period_of_performance_end": stmt.excluded.period_of_performance_end,
                                "set_aside_type": stmt.excluded.set_aside_type,
                                "fetched_at": stmt.excluded.fetched_at,
                            },
                        )
                        db.execute(stmt)
                        synced += 1

                        # Also update recipient info
                        if award.get("Recipient UEI"):
                            _upsert_recipient(db, award)

                        # Check for recompete opportunity
                        end_date = _parse_date(award.get("End Date"))
                        if end_date and end_date <= (datetime.utcnow().date() + timedelta(days=365)):
                            _upsert_recompete(db, award, naics_code)

                    except Exception as e:
                        logger.error(f"Error processing award {award.get('Award ID')}: {e}")
                        continue

                db.commit()

            # Check for more pages
            if len(results) < payload["limit"]:
                break

            payload["page"] += 1

    return synced


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def update_naics_statistics(self, naics_codes: Optional[list[str]] = None):
    """
    Update NAICS statistics from USAspending aggregated data.

    Args:
        naics_codes: Optional list of NAICS codes to update
    """
    logger.info("Updating NAICS statistics")

    if naics_codes is None:
        naics_codes = [
            "541511", "541512", "541519", "518210",
            "541690", "541712", "541330", "541990",
        ]

    for naics_code in naics_codes:
        try:
            _update_naics_stats(naics_code)
            logger.info(f"Updated statistics for NAICS {naics_code}")
        except Exception as e:
            logger.error(f"Error updating stats for NAICS {naics_code}: {e}")
            continue

    return {"updated": len(naics_codes)}


def _update_naics_stats(naics_code: str):
    """Update statistics for a specific NAICS code."""
    url = f"{USASPENDING_API_BASE}/spending/naics/"

    # Calculate 12-month period
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")

    with SessionLocal() as db:
        # Get awards from our database
        awards = db.query(ContractAward).filter(
            ContractAward.naics_code == naics_code,
            ContractAward.award_date >= (datetime.utcnow() - timedelta(days=365)).date(),
        ).all()

        if not awards:
            return

        obligations = [float(a.total_obligation or 0) for a in awards]

        # Calculate statistics
        total_awards = len(awards)
        total_obligation = sum(obligations)
        avg_award = total_obligation / total_awards if total_awards else 0

        # Sort for median and percentiles
        sorted_amounts = sorted(obligations)
        median = sorted_amounts[len(sorted_amounts) // 2] if sorted_amounts else 0

        # Size buckets
        under_25k = len([a for a in obligations if a < 25000])
        _25k_to_100k = len([a for a in obligations if 25000 <= a < 100000])
        _100k_to_250k = len([a for a in obligations if 100000 <= a < 250000])
        _250k_to_1m = len([a for a in obligations if 250000 <= a < 1000000])
        over_1m = len([a for a in obligations if a >= 1000000])

        # Small business count (rough estimate based on recipient data)
        small_business_awards = db.query(ContractAward).join(
            Recipient, ContractAward.recipient_uei == Recipient.uei
        ).filter(
            ContractAward.naics_code == naics_code,
            Recipient.is_small_business == True,
        ).count()

        # Top agencies
        agency_counts = {}
        for a in awards:
            if a.awarding_agency_name:
                agency_counts[a.awarding_agency_name] = agency_counts.get(a.awarding_agency_name, 0) + 1
        top_agencies = sorted(agency_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Top recipients
        recipient_counts = {}
        for a in awards:
            if a.recipient_name:
                recipient_counts[a.recipient_name] = recipient_counts.get(a.recipient_name, 0) + 1
        top_recipients = sorted(recipient_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Contracts expiring
        today = datetime.utcnow().date()
        expiring_90 = db.query(ContractAward).filter(
            ContractAward.naics_code == naics_code,
            ContractAward.period_of_performance_end.between(today, today + timedelta(days=90)),
        ).count()
        expiring_180 = db.query(ContractAward).filter(
            ContractAward.naics_code == naics_code,
            ContractAward.period_of_performance_end.between(today, today + timedelta(days=180)),
        ).count()
        expiring_365 = db.query(ContractAward).filter(
            ContractAward.naics_code == naics_code,
            ContractAward.period_of_performance_end.between(today, today + timedelta(days=365)),
        ).count()

        # Upsert statistics
        stats_record = {
            "naics_code": naics_code,
            "total_awards_12mo": total_awards,
            "total_obligation_12mo": Decimal(str(total_obligation)),
            "avg_award_amount_12mo": Decimal(str(avg_award)),
            "median_award_amount_12mo": Decimal(str(median)),
            "min_award_amount_12mo": Decimal(str(min(obligations))) if obligations else Decimal("0"),
            "max_award_amount_12mo": Decimal(str(max(obligations))) if obligations else Decimal("0"),
            "awards_under_25k": under_25k,
            "awards_25k_to_100k": _25k_to_100k,
            "awards_100k_to_250k": _100k_to_250k,
            "awards_250k_to_1m": _250k_to_1m,
            "awards_over_1m": over_1m,
            "small_business_awards": small_business_awards,
            "small_business_percentage": Decimal(str(small_business_awards / total_awards * 100)) if total_awards else Decimal("0"),
            "top_agencies": [{"name": n, "count": c} for n, c in top_agencies],
            "top_recipients": [{"name": n, "count": c} for n, c in top_recipients],
            "contracts_expiring_90_days": expiring_90,
            "contracts_expiring_180_days": expiring_180,
            "contracts_expiring_365_days": expiring_365,
            "calculated_at": datetime.utcnow(),
        }

        stmt = insert(NAICSStatistics).values(**stats_record)
        stmt = stmt.on_conflict_do_update(
            index_elements=["naics_code"],
            set_=stats_record,
        )
        db.execute(stmt)
        db.commit()


def _upsert_recipient(db, award: dict):
    """Update or insert recipient information."""
    uei = award.get("Recipient UEI")
    if not uei:
        return

    recipient_record = {
        "uei": uei,
        "name": award.get("Recipient Name"),
        "last_updated": datetime.utcnow(),
    }

    stmt = insert(Recipient).values(**recipient_record)
    stmt = stmt.on_conflict_do_update(
        index_elements=["uei"],
        set_={
            "name": stmt.excluded.name,
            "last_updated": stmt.excluded.last_updated,
        },
    )
    db.execute(stmt)


def _upsert_recompete(db, award: dict, naics_code: str):
    """Create or update recompete opportunity."""
    award_id = award.get("generated_internal_id") or award.get("Award ID")
    end_date = _parse_date(award.get("End Date"))

    if not award_id or not end_date:
        return

    recompete_record = {
        "award_id": award_id,
        "piid": award.get("Award ID"),
        "period_of_performance_end": end_date,
        "naics_code": naics_code,
        "total_value": Decimal(str(award.get("Award Amount") or 0)),
        "awarding_agency_name": award.get("Awarding Agency"),
        "incumbent_name": award.get("Recipient Name"),
        "incumbent_uei": award.get("Recipient UEI"),
        "status": "upcoming",
        "updated_at": datetime.utcnow(),
    }

    stmt = insert(RecompeteOpportunity).values(**recompete_record)
    stmt = stmt.on_conflict_do_update(
        index_elements=["award_id"],
        set_={
            "period_of_performance_end": stmt.excluded.period_of_performance_end,
            "total_value": stmt.excluded.total_value,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    db.execute(stmt)


def _parse_date(date_str: Optional[str]):
    """Parse date string to date object."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except Exception:
        return None
