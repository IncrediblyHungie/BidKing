"""
Analytics API Routes

Market overview, value distribution, NAICS/agency breakdowns, and incumbent analysis.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RecompeteOpportunity, ContractAward

router = APIRouter()


@router.get("/market-overview")
async def get_market_overview(db: Session = Depends(get_db)):
    """
    Get overall market statistics.

    Returns contract totals, recompete pipeline, and diversity metrics.
    Cached for 15 minutes for performance.
    """
    from app.utils.redis_client import analytics_cache

    # Try cache first
    cached = analytics_cache.get("market_overview")
    if cached:
        return cached

    # Contract awards statistics
    contract_stats = db.query(
        func.count(ContractAward.id).label("total_awards"),
        func.coalesce(func.sum(ContractAward.base_and_all_options_value), 0).label("total_value"),
        func.coalesce(func.avg(ContractAward.base_and_all_options_value), 0).label("average_value"),
        func.coalesce(func.min(ContractAward.base_and_all_options_value), 0).label("min_value"),
        func.coalesce(func.max(ContractAward.base_and_all_options_value), 0).label("max_value"),
    ).first()

    # Recompete statistics
    today = datetime.utcnow().date()
    recompete_stats = db.query(
        func.count(RecompeteOpportunity.id).label("total_upcoming"),
        func.coalesce(func.sum(RecompeteOpportunity.total_value), 0).label("total_value"),
        func.coalesce(func.avg(RecompeteOpportunity.total_value), 0).label("average_value"),
    ).filter(
        RecompeteOpportunity.period_of_performance_end >= today
    ).first()

    # Expiring counts
    expiring_30 = db.query(func.count(RecompeteOpportunity.id)).filter(
        RecompeteOpportunity.period_of_performance_end >= today,
        RecompeteOpportunity.period_of_performance_end <= today + timedelta(days=30)
    ).scalar() or 0

    expiring_90 = db.query(func.count(RecompeteOpportunity.id)).filter(
        RecompeteOpportunity.period_of_performance_end >= today,
        RecompeteOpportunity.period_of_performance_end <= today + timedelta(days=90)
    ).scalar() or 0

    expiring_365 = db.query(func.count(RecompeteOpportunity.id)).filter(
        RecompeteOpportunity.period_of_performance_end >= today,
        RecompeteOpportunity.period_of_performance_end <= today + timedelta(days=365)
    ).scalar() or 0

    # Diversity metrics
    unique_agencies = db.query(func.count(func.distinct(RecompeteOpportunity.awarding_agency_name))).scalar() or 0
    unique_naics = db.query(func.count(func.distinct(RecompeteOpportunity.naics_code))).filter(
        RecompeteOpportunity.naics_code.isnot(None)
    ).scalar() or 0

    result = {
        "contracts": {
            "total_awards": contract_stats.total_awards or 0,
            "total_value": float(contract_stats.total_value or 0),
            "average_value": float(contract_stats.average_value or 0),
            "min_value": float(contract_stats.min_value or 0),
            "max_value": float(contract_stats.max_value or 0),
        },
        "recompetes": {
            "total_upcoming": recompete_stats.total_upcoming or 0,
            "total_value": float(recompete_stats.total_value or 0),
            "average_value": float(recompete_stats.average_value or 0),
            "expiring_30_days": expiring_30,
            "expiring_90_days": expiring_90,
            "expiring_365_days": expiring_365,
        },
        "diversity": {
            "unique_agencies": unique_agencies,
            "unique_naics_codes": unique_naics,
        }
    }

    # Cache for 15 minutes
    analytics_cache.set("market_overview", result)
    return result


@router.get("/value-distribution")
async def get_value_distribution(db: Session = Depends(get_db)):
    """
    Get contract value distribution by size buckets.

    Returns count and total value for each size range.
    """
    today = datetime.utcnow().date()

    # Define value buckets
    buckets = [
        ("Under $100K", 0, 100000),
        ("$100K - $500K", 100000, 500000),
        ("$500K - $1M", 500000, 1000000),
        ("$1M - $5M", 1000000, 5000000),
        ("$5M - $10M", 5000000, 10000000),
        ("Over $10M", 10000000, None),
    ]

    distribution = []

    for label, min_val, max_val in buckets:
        query = db.query(
            func.count(RecompeteOpportunity.id).label("count"),
            func.coalesce(func.sum(RecompeteOpportunity.total_value), 0).label("total_value"),
        ).filter(
            RecompeteOpportunity.period_of_performance_end >= today,
            RecompeteOpportunity.total_value.isnot(None),
            RecompeteOpportunity.total_value >= min_val,
        )

        if max_val is not None:
            query = query.filter(RecompeteOpportunity.total_value < max_val)

        result = query.first()

        distribution.append({
            "range": label,
            "count": result.count or 0,
            "total_value": float(result.total_value or 0),
        })

    return {"distribution": distribution}


@router.get("/by-naics")
async def get_analytics_by_naics(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get contract analytics grouped by NAICS code.

    Returns top NAICS codes by total contract value.
    """
    today = datetime.utcnow().date()

    # NAICS descriptions mapping (common ones)
    naics_descriptions = {
        "541511": "Custom Computer Programming Services",
        "541512": "Computer Systems Design Services",
        "541519": "Other Computer Related Services",
        "518210": "Data Processing, Hosting Services",
        "541690": "Other Scientific & Technical Consulting",
        "541330": "Engineering Services",
        "541611": "Administrative Management Consulting",
        "541618": "Other Management Consulting Services",
        "541990": "All Other Professional/Scientific/Technical",
        "561110": "Office Administrative Services",
        "561210": "Facilities Support Services",
        "541712": "R&D in Physical/Engineering Sciences",
        "611430": "Professional Development Training",
        "541620": "Environmental Consulting Services",
        "541380": "Testing Laboratories",
    }

    results = db.query(
        RecompeteOpportunity.naics_code,
        func.count(RecompeteOpportunity.id).label("contract_count"),
        func.coalesce(func.sum(RecompeteOpportunity.total_value), 0).label("total_value"),
        func.coalesce(func.avg(RecompeteOpportunity.total_value), 0).label("average_value"),
    ).filter(
        RecompeteOpportunity.period_of_performance_end >= today,
        RecompeteOpportunity.naics_code.isnot(None),
        RecompeteOpportunity.total_value.isnot(None),
    ).group_by(
        RecompeteOpportunity.naics_code
    ).order_by(
        desc("total_value")
    ).limit(limit).all()

    by_naics = []
    for row in results:
        by_naics.append({
            "naics_code": row.naics_code,
            "naics_description": naics_descriptions.get(row.naics_code, "Unknown"),
            "contract_count": row.contract_count,
            "total_value": float(row.total_value),
            "average_value": float(row.average_value),
        })

    return {"by_naics": by_naics}


@router.get("/by-agency")
async def get_analytics_by_agency(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get contract analytics grouped by awarding agency.

    Returns top agencies by total contract value.
    """
    today = datetime.utcnow().date()

    results = db.query(
        RecompeteOpportunity.awarding_agency_name,
        func.count(RecompeteOpportunity.id).label("contract_count"),
        func.coalesce(func.sum(RecompeteOpportunity.total_value), 0).label("total_value"),
        func.coalesce(func.avg(RecompeteOpportunity.total_value), 0).label("average_value"),
    ).filter(
        RecompeteOpportunity.period_of_performance_end >= today,
        RecompeteOpportunity.awarding_agency_name.isnot(None),
        RecompeteOpportunity.total_value.isnot(None),
    ).group_by(
        RecompeteOpportunity.awarding_agency_name
    ).order_by(
        desc("total_value")
    ).limit(limit).all()

    by_agency = []
    for row in results:
        by_agency.append({
            "agency_name": row.awarding_agency_name,
            "contract_count": row.contract_count,
            "total_value": float(row.total_value),
            "average_value": float(row.average_value),
        })

    return {"by_agency": by_agency}


@router.get("/top-incumbents")
async def get_top_incumbents(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get top incumbents with expiring contracts.

    Returns companies with the most contracts expiring soon.
    """
    today = datetime.utcnow().date()

    results = db.query(
        RecompeteOpportunity.incumbent_name,
        func.count(RecompeteOpportunity.id).label("contract_count"),
        func.coalesce(func.sum(RecompeteOpportunity.total_value), 0).label("total_value"),
        func.coalesce(func.avg(RecompeteOpportunity.total_value), 0).label("average_value"),
    ).filter(
        RecompeteOpportunity.period_of_performance_end >= today,
        RecompeteOpportunity.incumbent_name.isnot(None),
        RecompeteOpportunity.total_value.isnot(None),
    ).group_by(
        RecompeteOpportunity.incumbent_name
    ).order_by(
        desc("contract_count")
    ).limit(limit).all()

    top_incumbents = []
    for row in results:
        top_incumbents.append({
            "incumbent_name": row.incumbent_name,
            "contract_count": row.contract_count,
            "total_value": float(row.total_value),
            "average_value": float(row.average_value),
        })

    return {"top_incumbents": top_incumbents}
