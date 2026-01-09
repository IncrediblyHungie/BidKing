"""
Competitor Analytics API

Provides endpoints for analyzing competitor win rates, market share,
and company profiles based on USAspending data.
"""

from typing import Optional, List
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, desc, and_, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.market_data import ContractAward, RecompeteOpportunity

router = APIRouter(prefix="/analytics/competitors", tags=["competitor-analytics"])


# =============================================================================
# Schemas
# =============================================================================

from pydantic import BaseModel


class CompetitorByNAICS(BaseModel):
    """Competitor stats for a specific NAICS code."""
    company_name: str
    uei: Optional[str] = None
    contract_count: int
    total_value: float
    average_contract_size: float
    win_rate_estimate: Optional[float] = None  # % of contracts in this NAICS


class NAICSCompetitorResponse(BaseModel):
    """Response for competitors by NAICS endpoint."""
    naics_code: str
    total_contracts: int
    total_value: float
    competitors: List[CompetitorByNAICS]


class CompanyProfile(BaseModel):
    """Detailed company profile."""
    company_name: str
    uei: Optional[str] = None
    total_contracts: int
    total_value: float
    average_contract_size: float
    naics_codes: List[str]
    top_agencies: List[dict]
    recent_wins: List[dict]
    contract_size_distribution: dict


class WinRateEntry(BaseModel):
    """Win rate for a company in a NAICS."""
    company_name: str
    contract_count: int
    total_value: float
    market_share_percent: float


class WinRatesResponse(BaseModel):
    """Response for win rates endpoint."""
    naics_code: Optional[str]
    total_market_value: float
    total_contracts: int
    winners: List[WinRateEntry]


class VulnerabilityFactor(BaseModel):
    """Single vulnerability factor with score and detail."""
    score: float
    detail: str
    weight: float


class IncumbentVulnerabilityResponse(BaseModel):
    """Response for incumbent vulnerability endpoint."""
    incumbent_name: Optional[str] = None
    incumbent_uei: str
    vulnerability_score: float
    level: str  # "Low", "Medium", "High"
    factors: dict  # Factor name -> score/detail/weight
    recommendation: str
    summary: Optional[dict] = None  # Contract stats and analysis context
    algorithm_version: Optional[str] = None
    calculated_at: Optional[str] = None


class SetAsideBreakdown(BaseModel):
    """Stats for a single set-aside type."""
    set_aside_type: str
    total_contracts: int
    total_value: float
    percent_of_contracts: float
    percent_of_value: float
    top_companies: List[dict]


class SetAsideAnalysisResponse(BaseModel):
    """Response for set-aside analysis endpoint."""
    naics_filter: Optional[str] = None
    total_contracts: int
    total_value: float
    breakdown: List[SetAsideBreakdown]


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/by-naics/{naics_code}", response_model=NAICSCompetitorResponse)
async def get_competitors_by_naics(
    naics_code: str,
    limit: int = Query(default=20, le=100),
    min_contracts: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
):
    """
    Get top competitors for a specific NAICS code.

    Returns companies ranked by total contract value within the NAICS code,
    based on USAspending award data.
    """
    # Query contract awards grouped by recipient
    query = db.query(
        ContractAward.recipient_name,
        ContractAward.recipient_uei,
        func.count(ContractAward.award_id).label("contract_count"),
        func.sum(ContractAward.base_and_all_options_value).label("total_value"),
        func.avg(ContractAward.base_and_all_options_value).label("avg_value"),
    ).filter(
        ContractAward.naics_code == naics_code,
        ContractAward.recipient_name.isnot(None),
    ).group_by(
        ContractAward.recipient_name,
        ContractAward.recipient_uei,
    ).having(
        func.count(ContractAward.award_id) >= min_contracts
    ).order_by(
        desc("total_value")
    ).limit(limit)

    results = query.all()

    # Calculate totals
    totals_query = db.query(
        func.count(ContractAward.award_id).label("total_contracts"),
        func.sum(ContractAward.base_and_all_options_value).label("total_value"),
    ).filter(
        ContractAward.naics_code == naics_code,
    ).first()

    total_contracts = totals_query.total_contracts or 0
    total_value = float(totals_query.total_value or 0)

    competitors = []
    for r in results:
        win_rate = None
        if total_contracts > 0:
            win_rate = round((r.contract_count / total_contracts) * 100, 2)

        competitors.append(CompetitorByNAICS(
            company_name=r.recipient_name,
            uei=r.recipient_uei,
            contract_count=r.contract_count,
            total_value=float(r.total_value or 0),
            average_contract_size=float(r.avg_value or 0),
            win_rate_estimate=win_rate,
        ))

    return NAICSCompetitorResponse(
        naics_code=naics_code,
        total_contracts=total_contracts,
        total_value=total_value,
        competitors=competitors,
    )


@router.get("/profile/{company_name}", response_model=CompanyProfile)
async def get_company_profile(
    company_name: str,
    db: Session = Depends(get_db),
):
    """
    Get detailed profile for a specific company.

    Provides contract history, NAICS expertise, top agencies worked with,
    and recent contract wins.
    """
    # Get basic stats
    basic_query = db.query(
        func.count(ContractAward.award_id).label("total_contracts"),
        func.sum(ContractAward.base_and_all_options_value).label("total_value"),
        func.avg(ContractAward.base_and_all_options_value).label("avg_value"),
    ).filter(
        ContractAward.recipient_name.ilike(f"%{company_name}%"),
    ).first()

    if not basic_query or basic_query.total_contracts == 0:
        raise HTTPException(status_code=404, detail=f"Company not found: {company_name}")

    # Get UEI
    uei_query = db.query(ContractAward.recipient_uei).filter(
        ContractAward.recipient_name.ilike(f"%{company_name}%"),
        ContractAward.recipient_uei.isnot(None),
    ).first()
    uei = uei_query.recipient_uei if uei_query else None

    # Get NAICS codes
    naics_query = db.query(
        ContractAward.naics_code,
    ).filter(
        ContractAward.recipient_name.ilike(f"%{company_name}%"),
        ContractAward.naics_code.isnot(None),
    ).distinct().all()
    naics_codes = [n.naics_code for n in naics_query]

    # Get top agencies
    agency_query = db.query(
        ContractAward.awarding_agency_name,
        func.count(ContractAward.award_id).label("contract_count"),
        func.sum(ContractAward.base_and_all_options_value).label("total_value"),
    ).filter(
        ContractAward.recipient_name.ilike(f"%{company_name}%"),
        ContractAward.awarding_agency_name.isnot(None),
    ).group_by(
        ContractAward.awarding_agency_name,
    ).order_by(
        desc("total_value")
    ).limit(10).all()

    top_agencies = [
        {
            "agency_name": a.awarding_agency_name,
            "contract_count": a.contract_count,
            "total_value": float(a.total_value or 0),
        }
        for a in agency_query
    ]

    # Get recent wins
    recent_query = db.query(
        ContractAward.piid,
        ContractAward.award_description,
        ContractAward.base_and_all_options_value,
        ContractAward.naics_code,
        ContractAward.awarding_agency_name,
        ContractAward.period_of_performance_start,
    ).filter(
        ContractAward.recipient_name.ilike(f"%{company_name}%"),
    ).order_by(
        desc(ContractAward.period_of_performance_start)
    ).limit(10).all()

    recent_wins = [
        {
            "piid": r.piid,
            "description": (r.award_description or "")[:200],
            "value": float(r.base_and_all_options_value or 0),
            "naics_code": r.naics_code,
            "agency": r.awarding_agency_name,
            "start_date": r.period_of_performance_start.isoformat() if r.period_of_performance_start else None,
        }
        for r in recent_query
    ]

    # Get contract size distribution
    size_query = db.query(
        func.count(ContractAward.award_id).label("count"),
    ).filter(
        ContractAward.recipient_name.ilike(f"%{company_name}%"),
    )

    under_100k = size_query.filter(
        ContractAward.base_and_all_options_value < 100000
    ).scalar() or 0

    size_100k_500k = db.query(func.count(ContractAward.award_id)).filter(
        ContractAward.recipient_name.ilike(f"%{company_name}%"),
        ContractAward.base_and_all_options_value >= 100000,
        ContractAward.base_and_all_options_value < 500000,
    ).scalar() or 0

    size_500k_1m = db.query(func.count(ContractAward.award_id)).filter(
        ContractAward.recipient_name.ilike(f"%{company_name}%"),
        ContractAward.base_and_all_options_value >= 500000,
        ContractAward.base_and_all_options_value < 1000000,
    ).scalar() or 0

    size_1m_5m = db.query(func.count(ContractAward.award_id)).filter(
        ContractAward.recipient_name.ilike(f"%{company_name}%"),
        ContractAward.base_and_all_options_value >= 1000000,
        ContractAward.base_and_all_options_value < 5000000,
    ).scalar() or 0

    over_5m = db.query(func.count(ContractAward.award_id)).filter(
        ContractAward.recipient_name.ilike(f"%{company_name}%"),
        ContractAward.base_and_all_options_value >= 5000000,
    ).scalar() or 0

    return CompanyProfile(
        company_name=company_name,
        uei=uei,
        total_contracts=basic_query.total_contracts or 0,
        total_value=float(basic_query.total_value or 0),
        average_contract_size=float(basic_query.avg_value or 0),
        naics_codes=naics_codes[:20],  # Limit to 20 NAICS codes
        top_agencies=top_agencies,
        recent_wins=recent_wins,
        contract_size_distribution={
            "under_100k": under_100k,
            "100k_to_500k": size_100k_500k,
            "500k_to_1m": size_500k_1m,
            "1m_to_5m": size_1m_5m,
            "over_5m": over_5m,
        },
    )


@router.get("/win-rates", response_model=WinRatesResponse)
async def get_win_rates(
    naics: Optional[str] = Query(default=None, description="Filter by NAICS code"),
    limit: int = Query(default=20, le=100),
    min_contracts: int = Query(default=2, ge=1),
    db: Session = Depends(get_db),
):
    """
    Get win rates (market share) for companies.

    Optionally filter by NAICS code. Returns companies ranked by total
    contract value with their market share percentage.
    """
    # Base query
    base_filter = []
    if naics:
        base_filter.append(ContractAward.naics_code == naics)

    # Get market totals
    totals_query = db.query(
        func.count(ContractAward.award_id).label("total_contracts"),
        func.sum(ContractAward.base_and_all_options_value).label("total_value"),
    )
    if base_filter:
        totals_query = totals_query.filter(*base_filter)
    totals = totals_query.first()

    total_market_value = float(totals.total_value or 0)
    total_contracts = totals.total_contracts or 0

    # Get winners
    winners_query = db.query(
        ContractAward.recipient_name,
        func.count(ContractAward.award_id).label("contract_count"),
        func.sum(ContractAward.base_and_all_options_value).label("total_value"),
    ).filter(
        ContractAward.recipient_name.isnot(None),
    )

    if base_filter:
        winners_query = winners_query.filter(*base_filter)

    winners_query = winners_query.group_by(
        ContractAward.recipient_name,
    ).having(
        func.count(ContractAward.award_id) >= min_contracts
    ).order_by(
        desc("total_value")
    ).limit(limit)

    results = winners_query.all()

    winners = []
    for r in results:
        market_share = 0.0
        if total_market_value > 0:
            market_share = round((float(r.total_value or 0) / total_market_value) * 100, 2)

        winners.append(WinRateEntry(
            company_name=r.recipient_name,
            contract_count=r.contract_count,
            total_value=float(r.total_value or 0),
            market_share_percent=market_share,
        ))

    return WinRatesResponse(
        naics_code=naics,
        total_market_value=total_market_value,
        total_contracts=total_contracts,
        winners=winners,
    )


@router.get("/incumbent-analysis")
async def get_incumbent_analysis(
    naics: Optional[str] = Query(default=None),
    days_until_expiration: int = Query(default=365, ge=30, le=730),
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
):
    """
    Analyze incumbents on expiring contracts (recompetes).

    Shows which companies have the most contracts expiring soon,
    making them targets for teaming or competition.
    """
    from datetime import date

    # Calculate expiration window
    today = date.today()
    end_date = today + timedelta(days=days_until_expiration)

    # Base filter
    filters = [
        RecompeteOpportunity.period_of_performance_end >= today,
        RecompeteOpportunity.period_of_performance_end <= end_date,
        RecompeteOpportunity.incumbent_name.isnot(None),
    ]

    if naics:
        filters.append(RecompeteOpportunity.naics_code == naics)

    # Get incumbents with expiring contracts
    query = db.query(
        RecompeteOpportunity.incumbent_name,
        RecompeteOpportunity.incumbent_uei,
        func.count(RecompeteOpportunity.id).label("expiring_contracts"),
        func.sum(RecompeteOpportunity.total_value).label("expiring_value"),
    ).filter(
        *filters
    ).group_by(
        RecompeteOpportunity.incumbent_name,
        RecompeteOpportunity.incumbent_uei,
    ).order_by(
        desc("expiring_value")
    ).limit(limit)

    results = query.all()

    # Get total expiring
    totals = db.query(
        func.count(RecompeteOpportunity.id).label("total"),
        func.sum(RecompeteOpportunity.total_value).label("value"),
    ).filter(*filters).first()

    return {
        "analysis_window_days": days_until_expiration,
        "naics_filter": naics,
        "total_expiring_contracts": totals.total or 0,
        "total_expiring_value": float(totals.value or 0),
        "incumbents": [
            {
                "company_name": r.incumbent_name,
                "uei": r.incumbent_uei,
                "expiring_contracts": r.expiring_contracts,
                "expiring_value": float(r.expiring_value or 0),
                "market_share_percent": round(
                    (float(r.expiring_value or 0) / float(totals.value or 1)) * 100, 2
                ) if totals.value else 0,
            }
            for r in results
        ],
    }


@router.get("/incumbent/{uei}/vulnerability", response_model=IncumbentVulnerabilityResponse)
async def get_incumbent_vulnerability(
    uei: str,
    naics_code: Optional[str] = Query(default=None, description="Filter analysis to specific NAICS code"),
    agency_name: Optional[str] = Query(default=None, description="Filter analysis to specific agency"),
    db: Session = Depends(get_db),
):
    """
    Calculate vulnerability score for an incumbent contractor.

    Returns 0-100 vulnerability score (higher = more beatable):
    - **concentration** (25%): Agency concentration risk - high reliance on one agency = vulnerable
    - **expertise** (20%): NAICS specialization - generalist = more vulnerable in specialized contracts
    - **trajectory** (20%): Contract value trend - declining portfolio = possible problems
    - **market_share** (20%): Market dominance - small share = more beatable
    - **recompete_history** (15%): Track record of losing recompetes

    Note: Performance-based vulnerability (CPARS), protest history (GAO), and financial
    health (D&B) data are not available through public APIs.
    """
    from app.services.incumbent_analysis import get_incumbent_vulnerability as calculate_vulnerability

    result = calculate_vulnerability(
        db=db,
        uei=uei,
        naics_code=naics_code,
        agency_name=agency_name,
    )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return IncumbentVulnerabilityResponse(
        incumbent_name=result.get("incumbent_name"),
        incumbent_uei=uei,
        vulnerability_score=result["vulnerability_score"],
        level=result["level"],
        factors=result["factors"],
        recommendation=result["recommendation"],
        summary=result.get("summary"),
        algorithm_version=result.get("algorithm_version"),
        calculated_at=result.get("calculated_at"),
    )


@router.get("/incumbent/by-name/{company_name}/vulnerability")
async def get_incumbent_vulnerability_by_name(
    company_name: str,
    naics_code: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Calculate vulnerability score for an incumbent by company name.

    Looks up the UEI for the company and calculates vulnerability score.
    Useful when you only have the company name from a recompete listing.
    """
    # Look up UEI for company name
    award = db.query(ContractAward.recipient_uei).filter(
        ContractAward.recipient_name.ilike(f"%{company_name}%"),
        ContractAward.recipient_uei.isnot(None),
    ).first()

    if not award or not award.recipient_uei:
        raise HTTPException(
            status_code=404,
            detail=f"No UEI found for company: {company_name}. Try searching with exact name or use UEI directly."
        )

    from app.services.incumbent_analysis import get_incumbent_vulnerability as calculate_vulnerability

    result = calculate_vulnerability(
        db=db,
        uei=award.recipient_uei,
        naics_code=naics_code,
    )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return {
        "incumbent_name": result.get("incumbent_name"),
        "incumbent_uei": award.recipient_uei,
        "vulnerability_score": result["vulnerability_score"],
        "level": result["level"],
        "factors": result["factors"],
        "recommendation": result["recommendation"],
        "summary": result.get("summary"),
        "algorithm_version": result.get("algorithm_version"),
        "calculated_at": result.get("calculated_at"),
    }


@router.get("/set-aside-analysis", response_model=SetAsideAnalysisResponse)
async def get_set_aside_analysis(
    naics: Optional[str] = Query(default=None, description="Filter by NAICS code"),
    limit: int = Query(default=5, le=20, description="Top companies per set-aside type"),
    db: Session = Depends(get_db),
):
    """
    Analyze competition by set-aside type.

    Shows breakdown of contracts across set-aside categories (8(a), HUBZone, SDVOSB, etc.)
    with top winners in each category. Helps identify which set-aside programs are most
    active and who dominates each category.
    """
    # Base filter
    base_filter = [ContractAward.set_aside_type.isnot(None)]
    if naics:
        base_filter.append(ContractAward.naics_code == naics)

    # Get overall totals
    totals_query = db.query(
        func.count(ContractAward.award_id).label("total_contracts"),
        func.sum(ContractAward.base_and_all_options_value).label("total_value"),
    ).filter(*base_filter).first()

    total_contracts = totals_query.total_contracts or 0
    total_value = float(totals_query.total_value or 0)

    # Get breakdown by set-aside type
    set_aside_query = db.query(
        ContractAward.set_aside_type,
        func.count(ContractAward.award_id).label("contracts"),
        func.sum(ContractAward.base_and_all_options_value).label("value"),
    ).filter(
        *base_filter
    ).group_by(
        ContractAward.set_aside_type
    ).order_by(
        desc("value")
    ).all()

    breakdown = []
    for sa in set_aside_query:
        # Get top companies for this set-aside type
        company_filter = base_filter + [ContractAward.set_aside_type == sa.set_aside_type]
        top_companies_query = db.query(
            ContractAward.recipient_name,
            ContractAward.recipient_uei,
            func.count(ContractAward.award_id).label("contracts"),
            func.sum(ContractAward.base_and_all_options_value).label("value"),
        ).filter(
            *company_filter,
            ContractAward.recipient_name.isnot(None),
        ).group_by(
            ContractAward.recipient_name,
            ContractAward.recipient_uei,
        ).order_by(
            desc("value")
        ).limit(limit).all()

        sa_value = float(sa.value or 0)
        top_companies = [
            {
                "company_name": c.recipient_name,
                "uei": c.recipient_uei,
                "contracts": c.contracts,
                "value": float(c.value or 0),
                "market_share": round((float(c.value or 0) / sa_value) * 100, 2) if sa_value > 0 else 0,
            }
            for c in top_companies_query
        ]

        breakdown.append(SetAsideBreakdown(
            set_aside_type=sa.set_aside_type,
            total_contracts=sa.contracts,
            total_value=sa_value,
            percent_of_contracts=round((sa.contracts / total_contracts) * 100, 2) if total_contracts > 0 else 0,
            percent_of_value=round((sa_value / total_value) * 100, 2) if total_value > 0 else 0,
            top_companies=top_companies,
        ))

    return SetAsideAnalysisResponse(
        naics_filter=naics,
        total_contracts=total_contracts,
        total_value=total_value,
        breakdown=breakdown,
    )
