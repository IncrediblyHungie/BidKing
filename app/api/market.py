"""
Market Intelligence API endpoints.

Provides access to USAspending data, labor rates, competitor analysis.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_db, get_current_user, require_starter, require_pro, rate_limit
from app.models import User, NAICSStatistics, ContractAward, Recipient, RecompeteOpportunity, LaborRateCache
from app.schemas.market_data import (
    NAICSStatisticsResponse,
    LaborRateRequest,
    LaborRateResponse,
    CompetitorResponse,
    RecompeteResponse,
    RecompeteListResponse,
    MarketOverview,
)
from worker.tasks.calc_sync import fetch_labor_rates

router = APIRouter()


@router.get("/overview", response_model=MarketOverview)
async def get_market_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get market overview dashboard data.

    Available to all authenticated users.
    """
    from app.models import Opportunity

    today = datetime.utcnow()

    # Opportunity counts
    total_active = db.query(Opportunity).filter(
        Opportunity.status == "active"
    ).count()

    new_today = db.query(Opportunity).filter(
        Opportunity.status == "active",
        func.date(Opportunity.created_at) == today.date(),
    ).count()

    new_week = db.query(Opportunity).filter(
        Opportunity.status == "active",
        Opportunity.created_at >= today - timedelta(days=7),
    ).count()

    # By type
    by_type = dict(db.query(
        Opportunity.type,
        func.count(Opportunity.id),
    ).filter(
        Opportunity.status == "active",
        Opportunity.type.isnot(None),
    ).group_by(Opportunity.type).all())

    # By set-aside
    by_setaside = dict(db.query(
        Opportunity.set_aside_type,
        func.count(Opportunity.id),
    ).filter(
        Opportunity.status == "active",
        Opportunity.set_aside_type.isnot(None),
    ).group_by(Opportunity.set_aside_type).all())

    # Top agencies
    top_agencies = db.query(
        Opportunity.agency_name,
        func.count(Opportunity.id).label("count"),
    ).filter(
        Opportunity.status == "active",
        Opportunity.agency_name.isnot(None),
    ).group_by(Opportunity.agency_name).order_by(
        func.count(Opportunity.id).desc()
    ).limit(10).all()

    # Expiring contracts
    contracts_30 = db.query(RecompeteOpportunity).filter(
        RecompeteOpportunity.period_of_performance_end.between(
            today.date(),
            today.date() + timedelta(days=30),
        )
    ).count()

    contracts_90 = db.query(RecompeteOpportunity).filter(
        RecompeteOpportunity.period_of_performance_end.between(
            today.date(),
            today.date() + timedelta(days=90),
        )
    ).count()

    # Score distribution
    from app.models import Opportunity as Opp
    high_score = db.query(Opp).filter(Opp.status == "active", Opp.likelihood_score >= 70).count()
    medium_score = db.query(Opp).filter(Opp.status == "active", Opp.likelihood_score >= 40, Opp.likelihood_score < 70).count()
    low_score = db.query(Opp).filter(Opp.status == "active", Opp.likelihood_score < 40).count()

    return MarketOverview(
        total_active_opportunities=total_active,
        new_opportunities_today=new_today,
        new_opportunities_week=new_week,
        opportunities_by_type=by_type,
        opportunities_by_setaside=by_setaside,
        top_agencies=[{"name": a[0], "count": a[1]} for a in top_agencies],
        contracts_expiring_30_days=contracts_30,
        contracts_expiring_90_days=contracts_90,
        high_score_opportunities=high_score,
        medium_score_opportunities=medium_score,
        low_score_opportunities=low_score,
        generated_at=datetime.utcnow(),
    )


@router.get("/naics/{naics_code}", response_model=NAICSStatisticsResponse)
async def get_naics_statistics(
    naics_code: str,
    current_user: User = Depends(require_starter),
    db: Session = Depends(get_db),
):
    """
    Get market statistics for a NAICS code.

    Requires Starter tier or higher.
    """
    stats = db.query(NAICSStatistics).filter(
        NAICSStatistics.naics_code == naics_code
    ).first()

    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No statistics available for NAICS {naics_code}",
        )

    return stats


@router.get("/naics", response_model=List[NAICSStatisticsResponse])
async def list_naics_statistics(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_starter),
    db: Session = Depends(get_db),
):
    """
    List NAICS statistics sorted by total awards.

    Requires Starter tier or higher.
    """
    stats = db.query(NAICSStatistics).order_by(
        NAICSStatistics.total_awards_12mo.desc()
    ).limit(limit).all()

    return stats


@router.post("/labor-rates", response_model=LaborRateResponse)
async def get_labor_rates(
    data: LaborRateRequest,
    current_user: User = Depends(require_starter),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit),
):
    """
    Get labor rate data from GSA CALC.

    Requires Starter tier or higher.
    """
    # Check cache first
    cached = db.query(LaborRateCache).filter(
        LaborRateCache.search_query == data.job_title,
        LaborRateCache.experience_min == data.experience_min,
        LaborRateCache.experience_max == data.experience_max,
        LaborRateCache.expires_at > datetime.utcnow(),
    ).first()

    if cached:
        return LaborRateResponse(
            search_query=cached.search_query,
            experience_range=f"{cached.experience_min or 0}-{cached.experience_max or 'any'} years" if cached.experience_min or cached.experience_max else None,
            education_level=cached.education_level,
            match_count=cached.match_count,
            min_rate=cached.min_rate,
            max_rate=cached.max_rate,
            avg_rate=cached.avg_rate,
            median_rate=cached.median_rate,
            percentile_25=cached.percentile_25,
            percentile_75=cached.percentile_75,
            sample_categories=cached.sample_categories or [],
            cached_at=cached.cached_at,
            data_freshness=f"cached {int((datetime.utcnow() - cached.cached_at).total_seconds() / 3600)} hours ago",
        )

    # Fetch fresh data
    result = fetch_labor_rates(
        job_title=data.job_title,
        experience_min=data.experience_min,
        experience_max=data.experience_max,
        education_level=data.education_level,
    )

    if "error" in result or result.get("match_count", 0) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("message", "No labor rate data found"),
        )

    return LaborRateResponse(**result)


@router.get("/competitors/{uei}", response_model=CompetitorResponse)
async def get_competitor(
    uei: str,
    current_user: User = Depends(require_pro),
    db: Session = Depends(get_db),
):
    """
    Get competitor/recipient profile by UEI.

    Requires Pro tier.
    """
    recipient = db.query(Recipient).filter(
        Recipient.uei == uei
    ).first()

    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient not found",
        )

    return recipient


@router.get("/competitors", response_model=List[CompetitorResponse])
async def search_competitors(
    name: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    naics_code: Optional[str] = Query(None),
    small_business: Optional[bool] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_pro),
    db: Session = Depends(get_db),
):
    """
    Search competitors/recipients.

    Requires Pro tier.
    """
    query = db.query(Recipient)

    if name:
        query = query.filter(Recipient.name.ilike(f"%{name}%"))

    if state:
        query = query.filter(Recipient.state == state.upper())

    if naics_code:
        query = query.filter(Recipient.primary_naics_codes.contains([naics_code]))

    if small_business is not None:
        query = query.filter(Recipient.is_small_business == small_business)

    recipients = query.order_by(
        Recipient.total_obligation.desc()
    ).limit(limit).all()

    return recipients


@router.get("/recompetes", response_model=RecompeteListResponse)
async def list_recompetes(
    naics_code: Optional[str] = Query(None),
    days_ahead: int = Query(180, ge=30, le=365),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_starter),
    db: Session = Depends(get_db),
):
    """
    List expiring contracts (recompete opportunities).

    Requires Starter tier or higher.
    """
    today = datetime.utcnow().date()
    end_date = today + timedelta(days=days_ahead)

    query = db.query(RecompeteOpportunity).filter(
        RecompeteOpportunity.period_of_performance_end.between(today, end_date),
    )

    if naics_code:
        query = query.filter(RecompeteOpportunity.naics_code == naics_code)

    total = query.count()

    recompetes = query.order_by(
        RecompeteOpportunity.period_of_performance_end.asc()
    ).offset((page - 1) * page_size).limit(page_size).all()

    # Add days_until_expiration
    items = []
    for r in recompetes:
        item = RecompeteResponse(
            id=r.id,
            award_id=r.award_id,
            piid=r.piid,
            period_of_performance_end=r.period_of_performance_end,
            days_until_expiration=(r.period_of_performance_end - today).days,
            naics_code=r.naics_code,
            total_value=r.total_value,
            awarding_agency_name=r.awarding_agency_name,
            incumbent_name=r.incumbent_name,
            incumbent_uei=r.incumbent_uei,
            status=r.status,
            linked_opportunity_id=r.linked_opportunity_id,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        items.append(item)

    return RecompeteListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/recompetes/{recompete_id}", response_model=RecompeteResponse)
async def get_recompete(
    recompete_id: UUID,
    current_user: User = Depends(require_starter),
    db: Session = Depends(get_db),
):
    """
    Get a specific recompete opportunity.

    Requires Starter tier or higher.
    """
    recompete = db.query(RecompeteOpportunity).filter(
        RecompeteOpportunity.id == recompete_id
    ).first()

    if not recompete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recompete opportunity not found",
        )

    today = datetime.utcnow().date()

    return RecompeteResponse(
        id=recompete.id,
        award_id=recompete.award_id,
        piid=recompete.piid,
        period_of_performance_end=recompete.period_of_performance_end,
        days_until_expiration=(recompete.period_of_performance_end - today).days,
        naics_code=recompete.naics_code,
        total_value=recompete.total_value,
        awarding_agency_name=recompete.awarding_agency_name,
        incumbent_name=recompete.incumbent_name,
        incumbent_uei=recompete.incumbent_uei,
        status=recompete.status,
        linked_opportunity_id=recompete.linked_opportunity_id,
        created_at=recompete.created_at,
        updated_at=recompete.updated_at,
    )
