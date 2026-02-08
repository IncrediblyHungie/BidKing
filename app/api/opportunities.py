"""
Opportunity API endpoints.

Handles searching, filtering, and viewing federal contract opportunities.
"""

import csv
import io
import time
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func, text

from app.api.deps import get_db, get_current_user, get_optional_user, rate_limit_search, require_starter
from app.config import settings
from app.models import User, Opportunity, SavedOpportunity, PointOfContact, OpportunityAttachment, OpportunityHistory
from app.models.company import OpportunityScore
from app.schemas.opportunity import (
    OpportunityResponse,
    OpportunityListResponse,
    OpportunitySearch,
    SavedOpportunityCreate,
    SavedOpportunityUpdate,
    SavedOpportunityResponse,
    VALID_PIPELINE_STATUSES,
)
from app.services.scoring import get_score_category, explain_score
from app.services.scoring_service import calculate_all_scores_for_user

# FTS5 special characters to strip from user input
_FTS5_SPECIAL = set('*(){}[]^~:!"\'\\')
_USE_FTS = 'sqlite' in settings.database_url


def _sanitize_fts_query(query: str) -> str:
    """Sanitize user input for FTS5 MATCH.

    Multi-word input is treated as a phrase search (wrapped in quotes).
    Single words are searched as-is. User-provided quotes are preserved.
    """
    import re
    # If user already quoted something, preserve their intent
    if '"' in query:
        phrases = re.findall(r'"[^"]*"', query)
        remaining = re.sub(r'"[^"]*"', '', query)
        cleaned = ''.join(c for c in remaining if c not in _FTS5_SPECIAL)
        words = cleaned.split()
        parts = [w for w in words if w] + phrases
        return ' '.join(parts)
    # Strip special chars
    cleaned = ''.join(c for c in query if c not in _FTS5_SPECIAL)
    words = cleaned.split()
    if len(words) > 1:
        return '"' + ' '.join(words) + '"'
    return words[0] if words else ''


def _fts_search_ids(db: Session, query: str) -> list:
    """Run FTS5 MATCH and return matching opportunity IDs."""
    sanitized = _sanitize_fts_query(query)
    stripped = sanitized.strip().strip('"')
    if not stripped or len(stripped) < 3:
        return None  # Too short for FTS, caller should fall back to ilike
    result = db.execute(
        text("SELECT opportunity_id FROM opportunities_fts WHERE opportunities_fts MATCH :q LIMIT 5000"),
        {"q": sanitized}
    )
    return [row[0] for row in result.fetchall()]


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
    notice_types: Optional[List[str]] = Query(
        None,
        description="Filter by notice type (e.g., 'Sources Sought', 'Presolicitation', 'Solicitation')"
    ),
    early_stage_only: bool = Query(
        False,
        description="Only show early-stage opportunities (Sources Sought, RFI, Presolicitation)"
    ),
    min_score: int = Query(0, ge=0, le=100),
    max_score: int = Query(100, ge=0, le=100),
    # AI Estimated Value filter
    min_value: Optional[int] = Query(None, ge=0, description="Minimum AI estimated value"),
    max_value: Optional[int] = Query(None, ge=0, description="Maximum AI estimated value"),
    has_value_estimate: Optional[bool] = Query(None, description="Filter to only opportunities with AI value estimates"),
    has_ai_analysis: Optional[bool] = Query(None, description="Filter to only opportunities with AI analysis from PDF attachments"),
    include_expired: bool = Query(False, description="Include opportunities with past deadlines"),
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
    By default, excludes opportunities with past deadlines unless include_expired=true.
    """
    now = datetime.utcnow()

    # Base query - only active opportunities
    base_query = db.query(Opportunity).filter(Opportunity.status == "active")

    # Exclude expired opportunities by default (deadline has passed)
    if not include_expired:
        base_query = base_query.filter(
            or_(
                Opportunity.response_deadline.is_(None),  # No deadline set
                Opportunity.response_deadline >= now,  # Future deadline
            )
        )

    # Text search - FTS5 for SQLite, ilike fallback for PostgreSQL
    if query:
        used_fts = False
        if _USE_FTS:
            matching_ids = _fts_search_ids(db, query)
            if matching_ids is not None:
                base_query = base_query.filter(Opportunity.id.in_(matching_ids))
                used_fts = True
        if not used_fts:
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

    # Notice type filter
    if notice_types:
        notice_conditions = [
            Opportunity.notice_type.ilike(f"%{nt}%")
            for nt in notice_types
        ]
        base_query = base_query.filter(or_(*notice_conditions))

    # Early stage filter (Sources Sought, RFI, Presolicitation)
    if early_stage_only:
        early_stage_types = ["Sources Sought", "Presolicitation", "Special Notice"]
        early_conditions = [
            Opportunity.notice_type.ilike(f"%{et}%")
            for et in early_stage_types
        ]
        base_query = base_query.filter(or_(*early_conditions))

    # Score filter
    base_query = base_query.filter(
        Opportunity.likelihood_score >= min_score,
        Opportunity.likelihood_score <= max_score,
    )

    # AI Estimated Value filter
    if has_value_estimate is True:
        # Only show opportunities with value estimates
        base_query = base_query.filter(
            or_(
                Opportunity.ai_estimated_value_low.isnot(None),
                Opportunity.ai_estimated_value_high.isnot(None),
            )
        )
    elif has_value_estimate is False:
        # Only show opportunities without value estimates
        base_query = base_query.filter(
            Opportunity.ai_estimated_value_low.is_(None),
            Opportunity.ai_estimated_value_high.is_(None),
        )

    # AI Analysis filter - check if any attachment has ai_summary
    if has_ai_analysis is True:
        # Subquery: opportunity IDs that have at least one attachment with AI summary
        ai_analyzed_subquery = db.query(OpportunityAttachment.opportunity_id).filter(
            OpportunityAttachment.ai_summary.isnot(None)
        ).distinct().subquery()
        base_query = base_query.filter(Opportunity.id.in_(ai_analyzed_subquery))
    elif has_ai_analysis is False:
        # Subquery: opportunity IDs that have at least one attachment with AI summary
        ai_analyzed_subquery = db.query(OpportunityAttachment.opportunity_id).filter(
            OpportunityAttachment.ai_summary.isnot(None)
        ).distinct().subquery()
        base_query = base_query.filter(~Opportunity.id.in_(ai_analyzed_subquery))

    if min_value is not None:
        # Use high estimate if available, otherwise low
        base_query = base_query.filter(
            or_(
                Opportunity.ai_estimated_value_high >= min_value,
                Opportunity.ai_estimated_value_low >= min_value,
            )
        )

    if max_value is not None:
        # Use low estimate if available, otherwise high
        base_query = base_query.filter(
            or_(
                Opportunity.ai_estimated_value_low <= max_value,
                Opportunity.ai_estimated_value_high <= max_value,
            )
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


# Simple in-memory cache for stats (5 minute TTL)
_stats_cache: Dict[str, Any] = {"data": None, "expires": 0}
STATS_CACHE_TTL = 300  # 5 minutes


@router.get("/stats")
async def get_opportunity_stats(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Get aggregated statistics about active opportunities.
    Only counts opportunities with future deadlines (not expired).

    For authenticated users with company profiles, uses personalized scores.
    For anonymous users, uses generic likelihood_score (cached for 5 min).
    """
    from app.models.company import OpportunityScore

    now = datetime.utcnow()

    # For anonymous users, return cached stats if available
    if not current_user and _stats_cache["data"] and time.time() < _stats_cache["expires"]:
        return _stats_cache["data"]

    # Base filter: active status AND (no deadline OR future deadline)
    active_filter = and_(
        Opportunity.status == "active",
        or_(
            Opportunity.response_deadline.is_(None),
            Opportunity.response_deadline >= now,
        )
    )

    # Base counts (excluding expired)
    total_active = db.query(Opportunity).filter(active_filter).count()

    new_today = db.query(Opportunity).filter(
        active_filter,
        func.date(Opportunity.created_at) == now.date(),
    ).count()

    # Score distribution - use personalized scores if user is authenticated
    if current_user:
        # Join with OpportunityScore table for personalized scores
        # Count opportunities that have personalized scores
        high_score = db.query(OpportunityScore).join(
            Opportunity, OpportunityScore.opportunity_id == Opportunity.id
        ).filter(
            OpportunityScore.user_id == current_user.id,
            active_filter,
            OpportunityScore.overall_score >= 70,
        ).count()

        medium_score = db.query(OpportunityScore).join(
            Opportunity, OpportunityScore.opportunity_id == Opportunity.id
        ).filter(
            OpportunityScore.user_id == current_user.id,
            active_filter,
            OpportunityScore.overall_score >= 40,
            OpportunityScore.overall_score < 70,
        ).count()

        low_score = db.query(OpportunityScore).join(
            Opportunity, OpportunityScore.opportunity_id == Opportunity.id
        ).filter(
            OpportunityScore.user_id == current_user.id,
            active_filter,
            OpportunityScore.overall_score < 40,
        ).count()

        # If no personalized scores exist yet, fall back to generic scores
        if high_score == 0 and medium_score == 0 and low_score == 0:
            high_score = db.query(Opportunity).filter(
                active_filter,
                Opportunity.likelihood_score >= 70,
            ).count()
            medium_score = db.query(Opportunity).filter(
                active_filter,
                Opportunity.likelihood_score >= 40,
                Opportunity.likelihood_score < 70,
            ).count()
            low_score = db.query(Opportunity).filter(
                active_filter,
                Opportunity.likelihood_score < 40,
            ).count()
    else:
        # Anonymous user - use generic likelihood_score
        high_score = db.query(Opportunity).filter(
            active_filter,
            Opportunity.likelihood_score >= 70,
        ).count()

        medium_score = db.query(Opportunity).filter(
            active_filter,
            Opportunity.likelihood_score >= 40,
            Opportunity.likelihood_score < 70,
        ).count()

        low_score = db.query(Opportunity).filter(
            active_filter,
            Opportunity.likelihood_score < 40,
        ).count()

    # Top agencies (excluding expired)
    top_agencies = db.query(
        Opportunity.agency_name,
        func.count(Opportunity.id).label("count"),
    ).filter(
        active_filter,
        Opportunity.agency_name.isnot(None),
    ).group_by(
        Opportunity.agency_name
    ).order_by(
        func.count(Opportunity.id).desc()
    ).limit(10).all()

    # Top NAICS codes (excluding expired)
    top_naics = db.query(
        Opportunity.naics_code,
        func.count(Opportunity.id).label("count"),
    ).filter(
        active_filter,
        Opportunity.naics_code.isnot(None),
    ).group_by(
        Opportunity.naics_code
    ).order_by(
        func.count(Opportunity.id).desc()
    ).limit(10).all()

    result = {
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

    # Cache for anonymous users
    if not current_user:
        _stats_cache["data"] = result
        _stats_cache["expires"] = time.time() + STATS_CACHE_TTL

    return result


@router.get("/export/csv")
async def export_opportunities_csv(
    # Filters (same as list_opportunities)
    query: Optional[str] = Query(None, max_length=500),
    naics_codes: Optional[List[str]] = Query(None),
    states: Optional[List[str]] = Query(None),
    agencies: Optional[List[str]] = Query(None),
    set_aside_types: Optional[List[str]] = Query(None),
    min_score: int = Query(0, ge=0, le=100),
    max_score: int = Query(100, ge=0, le=100),
    # AI Estimated Value filter
    min_value: Optional[int] = Query(None, ge=0),
    max_value: Optional[int] = Query(None, ge=0),
    has_value_estimate: Optional[bool] = Query(None),
    include_expired: bool = Query(False, description="Include opportunities with past deadlines"),
    db: Session = Depends(get_db),
    _: User = Depends(require_starter),  # Requires Starter or Pro tier
):
    """
    Export opportunities as CSV file.

    Requires Starter or Pro subscription tier.
    Supports the same filters as the list endpoint.
    Returns up to 10,000 records.
    By default, excludes opportunities with past deadlines.
    """
    now = datetime.utcnow()

    # Base query - only active opportunities
    base_query = db.query(Opportunity).filter(Opportunity.status == "active")

    # Exclude expired opportunities by default
    if not include_expired:
        base_query = base_query.filter(
            or_(
                Opportunity.response_deadline.is_(None),
                Opportunity.response_deadline >= now,
            )
        )

    # Text search - FTS5 for SQLite, ilike fallback for PostgreSQL
    if query:
        used_fts = False
        if _USE_FTS:
            matching_ids = _fts_search_ids(db, query)
            if matching_ids is not None:
                base_query = base_query.filter(Opportunity.id.in_(matching_ids))
                used_fts = True
        if not used_fts:
            search_filter = or_(
                Opportunity.title.ilike(f"%{query}%"),
                Opportunity.description.ilike(f"%{query}%"),
                Opportunity.solicitation_number.ilike(f"%{query}%"),
            )
            base_query = base_query.filter(search_filter)

    # NAICS filter
    if naics_codes:
        naics_conditions = [Opportunity.naics_code.like(f"{code}%") for code in naics_codes]
        base_query = base_query.filter(or_(*naics_conditions))

    # State filter
    if states:
        base_query = base_query.filter(Opportunity.pop_state.in_(states))

    # Agency filter
    if agencies:
        agency_conditions = [Opportunity.agency_name.ilike(f"%{agency}%") for agency in agencies]
        base_query = base_query.filter(or_(*agency_conditions))

    # Set-aside filter
    if set_aside_types:
        base_query = base_query.filter(Opportunity.set_aside_type.in_(set_aside_types))

    # Score filter
    base_query = base_query.filter(
        Opportunity.likelihood_score >= min_score,
        Opportunity.likelihood_score <= max_score,
    )

    # AI Estimated Value filter
    if has_value_estimate is True:
        base_query = base_query.filter(
            or_(
                Opportunity.ai_estimated_value_low.isnot(None),
                Opportunity.ai_estimated_value_high.isnot(None),
            )
        )
    elif has_value_estimate is False:
        base_query = base_query.filter(
            Opportunity.ai_estimated_value_low.is_(None),
            Opportunity.ai_estimated_value_high.is_(None),
        )

    if min_value is not None:
        base_query = base_query.filter(
            or_(
                Opportunity.ai_estimated_value_high >= min_value,
                Opportunity.ai_estimated_value_low >= min_value,
            )
        )

    if max_value is not None:
        base_query = base_query.filter(
            or_(
                Opportunity.ai_estimated_value_low <= max_value,
                Opportunity.ai_estimated_value_high <= max_value,
            )
        )

    # Get up to 10,000 opportunities
    opportunities = base_query.order_by(Opportunity.response_deadline.asc()).limit(10000).all()

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "Title",
        "Solicitation Number",
        "Agency",
        "NAICS Code",
        "Set-Aside Type",
        "Posted Date",
        "Response Deadline",
        "State",
        "City",
        "Score",
        "Type",
        "SAM.gov URL",
    ])

    # Data rows
    for opp in opportunities:
        sam_url = f"https://sam.gov/opp/{opp.notice_id}/view" if opp.notice_id else ""
        writer.writerow([
            opp.title or "",
            opp.solicitation_number or "",
            opp.agency_name or "",
            opp.naics_code or "",
            opp.set_aside_type or "",
            opp.posted_date.strftime("%Y-%m-%d") if opp.posted_date else "",
            opp.response_deadline.strftime("%Y-%m-%d") if opp.response_deadline else "",
            opp.pop_state or "",
            opp.pop_city or "",
            opp.likelihood_score or 0,
            opp.notice_type or "",
            sam_url,
        ])

    output.seek(0)

    # Generate filename with date
    filename = f"bidking_opportunities_{datetime.utcnow().strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# =============================================================================
# PERSONALIZED SCORING ENDPOINTS
# These MUST be defined BEFORE /{opportunity_id} to avoid route conflicts
# =============================================================================

@router.get("/scores")
async def get_user_opportunity_scores(
    opportunity_ids: Optional[List[str]] = Query(None, description="Optional list of opportunity IDs to filter"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get personalized opportunity scores for the current user.

    Returns scores for all scored opportunities, or filter by specific IDs.
    """
    # Check if any scores are stale — if so, recalculate all before returning
    stale_count = db.query(OpportunityScore).filter(
        OpportunityScore.user_id == current_user.id,
        OpportunityScore.is_stale == True,
    ).count()

    if stale_count > 0:
        try:
            print(f"[SCORING] Auto-recalculating {stale_count} stale scores for user {current_user.id}")
            calculate_all_scores_for_user(db, str(current_user.id))
        except Exception as e:
            print(f"[SCORING] Auto-recalculation failed: {e}")

    query = db.query(OpportunityScore).filter(
        OpportunityScore.user_id == current_user.id
    )

    if opportunity_ids:
        query = query.filter(OpportunityScore.opportunity_id.in_(opportunity_ids))

    # Order by overall score descending
    query = query.order_by(OpportunityScore.overall_score.desc())

    total = query.count()

    # Pagination
    offset = (page - 1) * page_size
    scores = query.offset(offset).limit(page_size).all()

    return {
        "items": [
            {
                "opportunity_id": str(score.opportunity_id),
                "overall_score": score.overall_score,
                "capability_score": score.capability_score,
                "capability_breakdown": score.capability_breakdown,
                "eligibility_score": score.eligibility_score,
                "eligibility_breakdown": score.eligibility_breakdown,
                "scale_score": score.scale_score,
                "scale_breakdown": score.scale_breakdown,
                "clearance_score": score.win_probability_score,
                "clearance_breakdown": score.win_probability_breakdown,
                "contract_type_score": score.strategic_score,
                "contract_type_breakdown": score.strategic_breakdown,
                "timeline_score": score.timeline_score,
                "timeline_breakdown": score.timeline_breakdown,
                "workforce_score": score.workforce_score,
                "workforce_breakdown": score.workforce_breakdown,
                "is_stale": score.is_stale,
                "calculated_at": score.calculated_at.isoformat() if score.calculated_at else None,
            }
            for score in scores
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/scores/{opportunity_id}")
async def get_opportunity_score(
    opportunity_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get personalized score for a specific opportunity.
    """
    score = db.query(OpportunityScore).filter(
        OpportunityScore.user_id == current_user.id,
        OpportunityScore.opportunity_id == opportunity_id,
    ).first()

    if not score:
        return {
            "opportunity_id": str(opportunity_id),
            "has_score": False,
            "message": "No score calculated for this opportunity. Complete company setup to enable scoring.",
        }

    # Auto-recalculate if stale
    if score.is_stale:
        try:
            print(f"[SCORING] Auto-recalculating stale score for user {current_user.id}, opp {opportunity_id}")
            calculate_all_scores_for_user(db, str(current_user.id))
            db.refresh(score)
        except Exception as e:
            print(f"[SCORING] Auto-recalculation failed: {e}")

    return {
        "opportunity_id": str(opportunity_id),
        "has_score": True,
        "overall_score": score.overall_score,
        "capability_score": score.capability_score,
        "capability_breakdown": score.capability_breakdown,
        "eligibility_score": score.eligibility_score,
        "eligibility_breakdown": score.eligibility_breakdown,
        "scale_score": score.scale_score,
        "scale_breakdown": score.scale_breakdown,
        "clearance_score": score.win_probability_score,
        "clearance_breakdown": score.win_probability_breakdown,
        "contract_type_score": score.strategic_score,
        "contract_type_breakdown": score.strategic_breakdown,
        "timeline_score": score.timeline_score,
        "timeline_breakdown": score.timeline_breakdown,
        "workforce_score": score.workforce_score,
        "workforce_breakdown": score.workforce_breakdown,
        "is_stale": score.is_stale,
        "stale_reason": score.stale_reason,
        "calculated_at": score.calculated_at.isoformat() if score.calculated_at else None,
    }


@router.get("/{opportunity_id}/win-probability")
async def get_win_probability(
    opportunity_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get personalized win probability for a specific opportunity.

    Calculates probability (0-100) of winning based on:
    - Set-aside match with user's certifications
    - NAICS code experience level
    - Historical competition levels
    - Incumbent presence (for recompetes)
    - Contract size fit
    - Past performance relevance
    - Timeline feasibility

    Returns:
        probability: 0-100 score
        confidence: low/medium/high
        factors: List of scoring factors with impact and details
        recommendation: Human-readable recommendation

    Requires authentication and completed company profile with NAICS codes.
    """
    from app.services.win_probability import get_win_probability_for_opportunity

    result = get_win_probability_for_opportunity(
        db,
        str(opportunity_id),
        str(current_user.id)
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    # Check for errors (incomplete profile)
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", result.get("error")),
        )

    return result


# =============================================================================
# SINGLE OPPORTUNITY ENDPOINTS
# =============================================================================

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

    # Load attachments - filter out failed extractions (broken URLs)
    # Show: extracted, pending, skipped (might still be valid)
    # Hide: failed with no text content (definitely broken)
    all_attachments = db.query(OpportunityAttachment).filter(
        OpportunityAttachment.opportunity_id == opportunity.id
    ).all()
    opportunity.attachments = [
        a for a in all_attachments
        if a.extraction_status != "failed" or a.text_content is not None
    ]

    # Load history (ordered by date desc)
    opportunity.history = db.query(OpportunityHistory).filter(
        OpportunityHistory.opportunity_id == opportunity.id
    ).order_by(OpportunityHistory.changed_at.desc()).all()

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


@router.get("/{opportunity_id}/competition")
async def get_competition_analysis(
    opportunity_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get competition analysis for an opportunity.

    Returns competition score (0-100, lower = less competition) based on:
    - Set-aside type (sole source, small business, etc.)
    - Notice type (Sources Sought = early stage, less competition)
    - NAICS code historical competition patterns
    - Contract characteristics

    Public endpoint - no auth required.
    """
    from app.services.competition import calculate_competition_score, get_historical_competition
    from app.services.scoring import calculate_combined_score, is_underserved_opportunity

    opportunity = db.query(Opportunity).filter(
        Opportunity.id == opportunity_id
    ).first()

    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    # Build opportunity data dict for scoring
    opp_data = {
        "notice_id": opportunity.notice_id,
        "title": opportunity.title,
        "description": opportunity.description,
        "naics_code": opportunity.naics_code,
        "set_aside_type": opportunity.set_aside_type,
        "notice_type": opportunity.notice_type,
        "agency_name": opportunity.agency_name,
    }

    # Get competition analysis
    competition = calculate_competition_score(opp_data, db)

    # Get combined score (likelihood + competition)
    combined = calculate_combined_score(opp_data)

    # Check if underserved
    underserved = is_underserved_opportunity(opp_data)

    # Get historical market data for this NAICS/agency
    historical = None
    if opportunity.naics_code:
        historical = get_historical_competition(
            db,
            naics_code=opportunity.naics_code,
            agency_name=opportunity.agency_name,
            lookback_days=365,
        )

    return {
        "opportunity_id": str(opportunity.id),
        "title": opportunity.title,
        "competition": {
            "score": competition["score"],
            "level": competition["level"],
            "level_label": competition["level_label"],
            "factors": competition["factors"],
            "recommendations": competition["recommendations"],
        },
        "combined_analysis": {
            "likelihood_score": combined["likelihood_score"],
            "competition_score": combined["competition_score"],
            "combined_score": combined["combined_score"],
            "priority": combined["priority"],
            "recommendation": combined["recommendation"],
        },
        "underserved": underserved,
        "historical_data": historical,
    }


@router.get("/{opportunity_id}/ai-summary")
async def get_opportunity_ai_summary(
    opportunity_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get AI-generated summary for an opportunity based on PDF attachments.

    Returns structured data extracted from SOW/RFP documents including:
    - Summary of what's being requested
    - Estimated contract value
    - Period of performance
    - Required technologies and certifications
    - Labor categories
    - Security clearance requirements
    """
    from app.services.ai_summarization import get_opportunity_summary

    # Verify opportunity exists
    opportunity = db.query(Opportunity).filter(
        Opportunity.id == opportunity_id
    ).first()

    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    # Get the AI summary (merges summaries from all analyzed attachments)
    summary = get_opportunity_summary(str(opportunity_id), generate_if_missing=True)

    if not summary:
        return {
            "opportunity_id": str(opportunity_id),
            "has_summary": False,
            "message": "No AI analysis available. Attachments may not have been processed yet.",
        }

    return {
        "opportunity_id": str(opportunity_id),
        "has_summary": True,
        "summary": summary,
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
    from app.config import SUBSCRIPTION_TIERS

    # Check saved opportunities limit (in features, not limits)
    tier_config = SUBSCRIPTION_TIERS.get(
        current_user.subscription_tier or "free",
        SUBSCRIPTION_TIERS["free"]
    )
    saved_limit = tier_config["features"].get("saved_opportunities", 10)

    current_saved_count = db.query(SavedOpportunity).filter(
        SavedOpportunity.user_id == current_user.id
    ).count()

    if current_saved_count >= saved_limit:
        tier_name = current_user.subscription_tier or "free"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Saved opportunities limit reached ({saved_limit}). Upgrade your plan for more.",
        )

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


@router.patch("/saved/{saved_id}", response_model=SavedOpportunityResponse)
async def update_saved_opportunity(
    saved_id: UUID,
    data: SavedOpportunityUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update a saved opportunity (status, notes, priority, reminder).
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

    # Track if status changed
    old_status = saved.status

    # Update fields if provided
    if data.status is not None:
        if data.status.lower() not in VALID_PIPELINE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {VALID_PIPELINE_STATUSES}",
            )
        saved.status = data.status.lower()

    if data.notes is not None:
        saved.notes = data.notes

    if data.priority is not None:
        saved.priority = data.priority

    if data.reminder_date is not None:
        saved.reminder_date = data.reminder_date

    if data.proposal_draft is not None:
        saved.proposal_draft = data.proposal_draft

    # Update stage_changed_at if status changed
    if saved.status != old_status:
        saved.stage_changed_at = datetime.utcnow()

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


@router.get("/saved/stats")
async def get_pipeline_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get pipeline statistics for current user.
    """
    # Count by status
    status_counts = db.query(
        SavedOpportunity.status,
        func.count(SavedOpportunity.id).label("count")
    ).filter(
        SavedOpportunity.user_id == current_user.id
    ).group_by(SavedOpportunity.status).all()

    stats = {status: 0 for status in VALID_PIPELINE_STATUSES}
    for status_name, count in status_counts:
        stats[status_name] = count

    # Get opportunities with upcoming deadlines
    upcoming_deadlines = db.query(SavedOpportunity).join(
        Opportunity
    ).filter(
        SavedOpportunity.user_id == current_user.id,
        SavedOpportunity.status.in_(["watching", "researching", "preparing"]),
        Opportunity.response_deadline >= datetime.utcnow(),
        Opportunity.response_deadline <= datetime.utcnow() + timedelta(days=7),
    ).count()

    return {
        "by_status": stats,
        "total": sum(stats.values()),
        "upcoming_deadlines_7_days": upcoming_deadlines,
    }


@router.get("/saved/export/csv")
async def export_saved_opportunities_csv(
    status_filter: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: User = Depends(require_starter),  # Requires Starter or Pro tier
):
    """
    Export user's saved opportunities (pipeline) as CSV file.

    Optionally filter by status. Requires Starter tier or higher.
    """
    query = db.query(SavedOpportunity).filter(
        SavedOpportunity.user_id == current_user.id
    ).options(joinedload(SavedOpportunity.opportunity))

    if status_filter:
        query = query.filter(SavedOpportunity.status == status_filter)

    saved_list = query.order_by(SavedOpportunity.updated_at.desc()).all()

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "Title",
        "Solicitation Number",
        "Agency",
        "Pipeline Status",
        "Priority",
        "Notes",
        "Reminder Date",
        "Response Deadline",
        "NAICS Code",
        "Set-Aside Type",
        "Added Date",
        "Stage Changed",
        "SAM.gov URL",
    ])

    # Data rows
    for saved in saved_list:
        opp = saved.opportunity
        sam_url = f"https://sam.gov/opp/{opp.notice_id}/view" if opp and opp.notice_id else ""

        priority_labels = {1: "Critical", 2: "High", 3: "Medium", 4: "Low", 5: "Someday"}
        priority_text = priority_labels.get(saved.priority, "Medium")

        writer.writerow([
            opp.title if opp else "",
            opp.solicitation_number if opp else "",
            opp.agency_name if opp else "",
            saved.status or "",
            priority_text,
            saved.notes or "",
            saved.reminder_date.strftime("%Y-%m-%d") if saved.reminder_date else "",
            opp.response_deadline.strftime("%Y-%m-%d") if opp and opp.response_deadline else "",
            opp.naics_code if opp else "",
            opp.set_aside_type if opp else "",
            saved.created_at.strftime("%Y-%m-%d") if saved.created_at else "",
            saved.stage_changed_at.strftime("%Y-%m-%d") if saved.stage_changed_at else "",
            sam_url,
        ])

    output.seek(0)

    # Generate filename with date
    filename = f"bidking_pipeline_{datetime.utcnow().strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/attachments/{attachment_id}/download")
async def download_attachment(
    attachment_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Proxy endpoint to download attachments from SAM.gov.

    SAM.gov's direct file URLs return 404. We need to:
    1. Get the zip download URL for the opportunity
    2. Fetch the zip which returns JSON with S3 signed URL
    3. Download from S3 and extract the specific file
    4. Stream it back to the user
    """
    import httpx
    import zipfile
    import io

    # Find the attachment
    attachment = db.query(OpportunityAttachment).filter(
        OpportunityAttachment.id == attachment_id
    ).first()

    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    # Get the opportunity to find the notice_id
    opportunity = db.query(Opportunity).filter(
        Opportunity.id == attachment.opportunity_id
    ).first()

    if not opportunity or not opportunity.notice_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    try:
        # SAM.gov zip download endpoint
        zip_url = f"https://sam.gov/api/prod/opps/v3/opportunities/{opportunity.notice_id}/resources/download/zip"

        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            # First request gets JSON with S3 signed URL
            response = client.get(zip_url)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"SAM.gov returned {response.status_code}",
                )

            content_type = response.headers.get("content-type", "")

            # SAM.gov returns JSON with S3 URL
            if "application/json" in content_type:
                location_data = response.json()
                s3_url = location_data.get("location")

                if not s3_url:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="SAM.gov did not provide download URL",
                    )

                # Download actual zip from S3
                zip_response = client.get(s3_url)
                if zip_response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"S3 download failed: {zip_response.status_code}",
                    )
                zip_content = zip_response.content
            else:
                # Direct zip content (unlikely but handle it)
                zip_content = response.content

            # Extract the specific file from the zip
            zip_file = io.BytesIO(zip_content)

            try:
                with zipfile.ZipFile(zip_file, 'r') as zf:
                    # Find the file matching our attachment name
                    target_file = None
                    for file_info in zf.namelist():
                        # Match by filename (attachment.name might have path prefix)
                        if attachment.name and attachment.name.lower() in file_info.lower():
                            target_file = file_info
                            break
                        # Also try matching just the basename
                        if attachment.name:
                            import os
                            if os.path.basename(file_info).lower() == attachment.name.lower():
                                target_file = file_info
                                break

                    if not target_file:
                        # If exact match fails, just get first file with matching extension
                        ext = attachment.name.split('.')[-1].lower() if attachment.name else None
                        for file_info in zf.namelist():
                            if ext and file_info.lower().endswith(f".{ext}"):
                                target_file = file_info
                                break

                    if not target_file and len(zf.namelist()) == 1:
                        # Only one file in zip, use it
                        target_file = zf.namelist()[0]

                    if not target_file:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"File not found in SAM.gov archive. Available: {zf.namelist()[:5]}",
                        )

                    file_content = zf.read(target_file)

            except zipfile.BadZipFile:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Invalid archive from SAM.gov",
                )

        # Determine content type
        content_type = "application/octet-stream"
        if attachment.file_type:
            content_type = attachment.file_type
        elif attachment.name:
            name_lower = attachment.name.lower()
            if name_lower.endswith('.pdf'):
                content_type = "application/pdf"
            elif name_lower.endswith('.doc'):
                content_type = "application/msword"
            elif name_lower.endswith('.docx'):
                content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            elif name_lower.endswith('.xls'):
                content_type = "application/vnd.ms-excel"
            elif name_lower.endswith('.xlsx'):
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        # Clean filename for Content-Disposition
        safe_filename = attachment.name or "attachment"
        safe_filename = safe_filename.replace('"', "'").replace('\n', ' ').replace('\r', '')

        return StreamingResponse(
            iter([file_content]),
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{safe_filename}"',
                "Content-Length": str(len(file_content)),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to download from SAM.gov: {str(e)}",
        )
