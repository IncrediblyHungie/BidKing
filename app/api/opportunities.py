"""
Opportunity API endpoints.

Handles searching, filtering, and viewing federal contract opportunities.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func

from app.api.deps import get_db, get_current_user, get_optional_user, rate_limit_search
from app.models import User, Opportunity, SavedOpportunity, PointOfContact
from app.schemas.opportunity import (
    OpportunityResponse,
    OpportunityListResponse,
    OpportunitySearch,
    SavedOpportunityCreate,
    SavedOpportunityResponse,
)
from app.services.scoring import get_score_category, explain_score

router = APIRouter()


@router.get("", response_model=OpportunityListResponse)
async def list_opportunities(
    # Search
    query: Optional[str] = Query(None, max_length=500),
    # Filters
    naics_codes: Optional[List[str]] = Query(None),
    states: Optional[List[str]] = Query(None),
    agencies: Optional[List[str]] = Query(None),
    set_aside_types: Optional[List[str]] = Query(None),
    min_score: int = Query(0, ge=0, le=100),
    max_score: int = Query(100, ge=0, le=100),
    # Pagination
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    # Sorting
    sort_by: str = Query("response_deadline"),
    sort_order: str = Query("asc"),
    # Dependencies
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
    _: None = Depends(rate_limit_search),
):
    """
    List and search opportunities.

    Supports filtering by NAICS codes, states, agencies, set-asides, and score range.
    Text search matches against title and description.
    """
    # Base query - only active opportunities
    base_query = db.query(Opportunity).filter(Opportunity.status == "active")

    # Text search
    if query:
        search_filter = or_(
            Opportunity.title.ilike(f"%{query}%"),
            Opportunity.description.ilike(f"%{query}%"),
            Opportunity.solicitation_number.ilike(f"%{query}%"),
        )
        base_query = base_query.filter(search_filter)

    # NAICS filter
    if naics_codes:
        naics_conditions = [
            Opportunity.naics_code.like(f"{code}%")
            for code in naics_codes
        ]
        base_query = base_query.filter(or_(*naics_conditions))

    # State filter
    if states:
        base_query = base_query.filter(Opportunity.pop_state.in_(states))

    # Agency filter
    if agencies:
        agency_conditions = [
            Opportunity.agency_name.ilike(f"%{agency}%")
            for agency in agencies
        ]
        base_query = base_query.filter(or_(*agency_conditions))

    # Set-aside filter
    if set_aside_types:
        base_query = base_query.filter(Opportunity.set_aside_type.in_(set_aside_types))

    # Score filter
    base_query = base_query.filter(
        Opportunity.likelihood_score >= min_score,
        Opportunity.likelihood_score <= max_score,
    )

    # Get total count
    total = base_query.count()

    # Sorting
    sort_column = getattr(Opportunity, sort_by, Opportunity.response_deadline)
    if sort_order.lower() == "desc":
        sort_column = sort_column.desc()
    else:
        sort_column = sort_column.asc()

    # Handle nulls in deadline - put them at the end
    if sort_by == "response_deadline":
        base_query = base_query.order_by(
            Opportunity.response_deadline.is_(None),
            sort_column,
        )
    else:
        base_query = base_query.order_by(sort_column)

    # Pagination
    offset = (page - 1) * page_size
    opportunities = base_query.offset(offset).limit(page_size).all()

    # Load contacts for each opportunity
    for opp in opportunities:
        opp.points_of_contact = db.query(PointOfContact).filter(
            PointOfContact.opportunity_id == opp.id
        ).all()

    return OpportunityListResponse(
        items=opportunities,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/stats")
async def get_opportunity_stats(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Get aggregated statistics about active opportunities.
    """
    today = datetime.utcnow()

    # Base counts
    total_active = db.query(Opportunity).filter(
        Opportunity.status == "active"
    ).count()

    new_today = db.query(Opportunity).filter(
        Opportunity.status == "active",
        func.date(Opportunity.created_at) == today.date(),
    ).count()

    # Score distribution
    high_score = db.query(Opportunity).filter(
        Opportunity.status == "active",
        Opportunity.likelihood_score >= 70,
    ).count()

    medium_score = db.query(Opportunity).filter(
        Opportunity.status == "active",
        Opportunity.likelihood_score >= 40,
        Opportunity.likelihood_score < 70,
    ).count()

    low_score = db.query(Opportunity).filter(
        Opportunity.status == "active",
        Opportunity.likelihood_score < 40,
    ).count()

    # Top agencies
    top_agencies = db.query(
        Opportunity.agency_name,
        func.count(Opportunity.id).label("count"),
    ).filter(
        Opportunity.status == "active",
        Opportunity.agency_name.isnot(None),
    ).group_by(
        Opportunity.agency_name
    ).order_by(
        func.count(Opportunity.id).desc()
    ).limit(10).all()

    # Top NAICS codes
    top_naics = db.query(
        Opportunity.naics_code,
        func.count(Opportunity.id).label("count"),
    ).filter(
        Opportunity.status == "active",
        Opportunity.naics_code.isnot(None),
    ).group_by(
        Opportunity.naics_code
    ).order_by(
        func.count(Opportunity.id).desc()
    ).limit(10).all()

    return {
        "total_active": total_active,
        "new_today": new_today,
        "score_distribution": {
            "high": high_score,
            "medium": medium_score,
            "low": low_score,
        },
        "top_agencies": [{"name": a[0], "count": a[1]} for a in top_agencies],
        "top_naics": [{"code": n[0], "count": n[1]} for n in top_naics],
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/{opportunity_id}", response_model=OpportunityResponse)
async def get_opportunity(
    opportunity_id: UUID,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Get a specific opportunity by ID.
    """
    opportunity = db.query(Opportunity).filter(
        Opportunity.id == opportunity_id
    ).first()

    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    # Load contacts
    opportunity.points_of_contact = db.query(PointOfContact).filter(
        PointOfContact.opportunity_id == opportunity.id
    ).all()

    return opportunity


@router.get("/{opportunity_id}/analysis")
async def get_opportunity_analysis(
    opportunity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed analysis for an opportunity.

    Includes score explanation and category.
    Requires authentication.
    """
    opportunity = db.query(Opportunity).filter(
        Opportunity.id == opportunity_id
    ).first()

    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    # Get score explanation
    raw_data = opportunity.raw_data or {}
    reasons = explain_score(raw_data, opportunity.likelihood_score)
    category = get_score_category(opportunity.likelihood_score)

    return {
        "opportunity_id": str(opportunity.id),
        "title": opportunity.title,
        "likelihood_score": opportunity.likelihood_score,
        "score_category": category,
        "score_reasons": reasons,
    }


# Saved opportunities endpoints
@router.get("/saved/list", response_model=List[SavedOpportunityResponse])
async def list_saved_opportunities(
    status_filter: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List user's saved opportunities.
    """
    query = db.query(SavedOpportunity).filter(
        SavedOpportunity.user_id == current_user.id
    ).options(joinedload(SavedOpportunity.opportunity))

    if status_filter:
        query = query.filter(SavedOpportunity.status == status_filter)

    saved = query.order_by(SavedOpportunity.updated_at.desc()).all()
    return saved


@router.post("/saved", response_model=SavedOpportunityResponse)
async def save_opportunity(
    data: SavedOpportunityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Save an opportunity for tracking.
    """
    # Check if already saved
    existing = db.query(SavedOpportunity).filter(
        SavedOpportunity.user_id == current_user.id,
        SavedOpportunity.opportunity_id == data.opportunity_id,
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Opportunity already saved",
        )

    # Verify opportunity exists
    opportunity = db.query(Opportunity).filter(
        Opportunity.id == data.opportunity_id
    ).first()

    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    saved = SavedOpportunity(
        user_id=current_user.id,
        **data.model_dump(),
    )

    db.add(saved)
    db.commit()
    db.refresh(saved)

    return saved


@router.delete("/saved/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_opportunity(
    saved_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Remove a saved opportunity.
    """
    saved = db.query(SavedOpportunity).filter(
        SavedOpportunity.id == saved_id,
        SavedOpportunity.user_id == current_user.id,
    ).first()

    if not saved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved opportunity not found",
        )

    db.delete(saved)
    db.commit()
