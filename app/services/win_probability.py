"""
Win Probability Service

Calculates personalized win probability for opportunities based on:
- User's company profile (NAICS experience, certifications)
- Opportunity characteristics (set-aside, competition type, incumbent)
- Historical patterns (competition levels, market data)

This is a heuristic-based model (v1). Future versions will train
on OpportunityDecision feedback data when available.
"""

from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.opportunity import Opportunity
from app.models.company import (
    CompanyProfile,
    CompanyNAICS,
    CompanyCertification,
    PastPerformance,
)
from app.models.market_data import ContractAward, RecompeteOpportunity


# =============================================================================
# Constants & Mappings
# =============================================================================

# Set-aside types that have less competition (bonus for matching)
LOW_COMPETITION_SET_ASIDES = [
    "8(a)",
    "8A",
    "HUBZone",
    "HZC",
    "SDVOSB",
    "SDVOSBC",
    "EDWOSB",
]

# Set-aside to certification mapping (what cert qualifies for what set-aside)
SET_ASIDE_CERT_MAP = {
    "8A": "8(a)",
    "8(a)": "8(a)",
    "SBA": "8(a)",
    "HZC": "HUBZone",
    "HUBZONE": "HUBZone",
    "HUBZone": "HUBZone",
    "SDVOSBC": "SDVOSB",
    "SDVOSB": "SDVOSB",
    "VOSB": "VOSB",
    "VSB": "VOSB",
    "WOSB": "WOSB",
    "EDWOSB": "EDWOSB",
    "SDB": "SDB",
    "SBP": "small_business",
    "Small Business": "small_business",
    "Total Small Business Set-Aside": "small_business",
}

# Experience level to score mapping
EXPERIENCE_SCORES = {
    "expert": 25,
    "extensive": 20,
    "moderate": 10,
    "limited": 5,
    "none": 0,
}


# =============================================================================
# Win Probability Calculation
# =============================================================================

def calculate_win_probability(
    db: Session,
    opportunity: Opportunity,
    profile: CompanyProfile,
    naics_codes: List[CompanyNAICS],
    certifications: List[CompanyCertification],
    past_performances: Optional[List[PastPerformance]] = None,
) -> Dict[str, Any]:
    """
    Calculate win probability for a specific opportunity.

    Returns a score 0-100 with factor breakdowns and recommendation.

    Scoring factors:
    - Set-aside match: +20 to +35
    - NAICS experience: +0 to +25
    - Competition level: -10 to +15
    - Incumbent presence: -15 to 0
    - Contract size fit: -10 to +10
    - Past performance: +0 to +15
    - Timeline pressure: -10 to +5

    Base score starts at 50 (neutral).
    """
    score = 50  # Start neutral
    factors = []

    # ==========================================================================
    # Factor 1: Set-Aside Match (+20 to +35)
    # ==========================================================================
    set_aside_impact, set_aside_detail = _calculate_set_aside_factor(
        opportunity.set_aside_type,
        certifications,
        profile.business_size
    )
    score += set_aside_impact
    if set_aside_impact != 0:
        factors.append({
            "name": "Set-Aside Match",
            "impact": set_aside_impact,
            "detail": set_aside_detail,
        })

    # ==========================================================================
    # Factor 2: NAICS Experience (+0 to +25)
    # ==========================================================================
    naics_impact, naics_detail = _calculate_naics_experience_factor(
        opportunity.naics_code,
        naics_codes
    )
    score += naics_impact
    if naics_impact != 0:
        factors.append({
            "name": "NAICS Experience",
            "impact": naics_impact,
            "detail": naics_detail,
        })

    # ==========================================================================
    # Factor 3: Competition Level (-10 to +15)
    # ==========================================================================
    competition_impact, competition_detail = _calculate_competition_factor(
        db,
        opportunity.naics_code,
        opportunity.set_aside_type
    )
    score += competition_impact
    factors.append({
        "name": "Competition Level",
        "impact": competition_impact,
        "detail": competition_detail,
    })

    # ==========================================================================
    # Factor 4: Incumbent Presence (-15 to 0)
    # ==========================================================================
    incumbent_impact, incumbent_detail = _calculate_incumbent_factor(
        db,
        opportunity
    )
    score += incumbent_impact
    if incumbent_impact != 0:
        factors.append({
            "name": "Incumbent Presence",
            "impact": incumbent_impact,
            "detail": incumbent_detail,
        })

    # ==========================================================================
    # Factor 5: Contract Size Fit (-10 to +10)
    # ==========================================================================
    size_impact, size_detail = _calculate_size_fit_factor(
        opportunity,
        profile
    )
    score += size_impact
    if size_impact != 0:
        factors.append({
            "name": "Contract Size Fit",
            "impact": size_impact,
            "detail": size_detail,
        })

    # ==========================================================================
    # Factor 6: Past Performance (+0 to +15)
    # ==========================================================================
    if past_performances:
        pp_impact, pp_detail = _calculate_past_performance_factor(
            opportunity,
            past_performances
        )
        score += pp_impact
        if pp_impact != 0:
            factors.append({
                "name": "Past Performance",
                "impact": pp_impact,
                "detail": pp_detail,
            })

    # ==========================================================================
    # Factor 7: Timeline Pressure (-10 to +5)
    # ==========================================================================
    timeline_impact, timeline_detail = _calculate_timeline_factor(
        opportunity.response_deadline,
        profile.min_days_to_respond or 7
    )
    score += timeline_impact
    if timeline_impact != 0:
        factors.append({
            "name": "Timeline",
            "impact": timeline_impact,
            "detail": timeline_detail,
        })

    # Clamp score to 0-100
    score = max(0, min(100, score))

    # Determine confidence level
    confidence = _calculate_confidence(factors, profile)

    # Generate recommendation
    recommendation = _generate_recommendation(score, factors)

    return {
        "probability": score,
        "confidence": confidence,
        "factors": factors,
        "recommendation": recommendation,
        "algorithm_version": "heuristic_v1",
        "calculated_at": datetime.utcnow().isoformat(),
    }


# =============================================================================
# Factor Calculation Functions
# =============================================================================

def _calculate_set_aside_factor(
    set_aside_type: Optional[str],
    certifications: List[CompanyCertification],
    business_size: Optional[str]
) -> Tuple[int, str]:
    """Calculate set-aside match impact."""

    # No set-aside = full and open (more competition)
    if not set_aside_type or set_aside_type.lower() in ["none", "full and open", ""]:
        return 0, "Full and open competition - no advantage"

    # Normalize set-aside type
    normalized = set_aside_type.upper().replace(" ", "").replace("-", "")

    # Find required certification
    required_cert = None
    for key, cert in SET_ASIDE_CERT_MAP.items():
        if key.upper().replace(" ", "").replace("-", "") == normalized or \
           key.upper() in normalized or normalized in key.upper():
            required_cert = cert
            break

    if not required_cert:
        return 0, f"Unknown set-aside type: {set_aside_type}"

    # Check if user has matching certification
    user_certs = [c.certification_type for c in certifications if c.is_active]

    # Special case: small business
    if required_cert == "small_business":
        if business_size == "small":
            # Check if this is a low-competition set-aside
            if any(sa in set_aside_type.upper() for sa in ["8(A)", "8A", "HUBZONE", "SDVOSB"]):
                return 35, f"Small business + {set_aside_type} = very limited competition"
            return 20, f"Small business eligible for {set_aside_type}"
        return -20, f"Not eligible: {set_aside_type} requires small business"

    # Check certification match
    if required_cert in user_certs:
        # Low competition set-asides get extra bonus
        if any(lc in set_aside_type.upper() for lc in ["8(A)", "8A", "HUBZONE", "SDVOSB", "EDWOSB"]):
            return 35, f"{required_cert} certification matches {set_aside_type} - very limited competition"
        return 20, f"{required_cert} certification matches {set_aside_type}"

    # Has set-aside but user doesn't qualify
    return -30, f"Not eligible: {set_aside_type} requires {required_cert}"


def _calculate_naics_experience_factor(
    opp_naics: Optional[str],
    user_naics: List[CompanyNAICS]
) -> Tuple[int, str]:
    """Calculate NAICS experience impact."""

    if not opp_naics or not user_naics:
        return 0, "No NAICS data available"

    # Find exact match first
    for naics in user_naics:
        if naics.naics_code == opp_naics:
            level = naics.experience_level or "moderate"
            impact = EXPERIENCE_SCORES.get(level, 10)

            # Add bonus for contracts won
            if naics.contracts_won and naics.contracts_won > 0:
                impact += min(5, naics.contracts_won)  # Up to +5 for past wins

            years = naics.years_experience or 0
            detail = f"{level.capitalize()} experience in {opp_naics}"
            if naics.contracts_won:
                detail += f" ({naics.contracts_won} contracts won)"
            if years:
                detail += f" ({years} years)"
            return impact, detail

    # Check for 4-digit match (industry group)
    opp_4digit = opp_naics[:4] if len(opp_naics) >= 4 else opp_naics
    for naics in user_naics:
        if naics.naics_code[:4] == opp_4digit:
            return 5, f"Related experience in {naics.naics_code} (same industry group)"

    # Check for 2-digit match (sector)
    opp_2digit = opp_naics[:2] if len(opp_naics) >= 2 else opp_naics
    for naics in user_naics:
        if naics.naics_code[:2] == opp_2digit:
            return 2, f"Related experience in {naics.naics_code} (same sector)"

    # No match
    return -5, f"No experience in NAICS {opp_naics}"


def _calculate_competition_factor(
    db: Session,
    naics_code: Optional[str],
    set_aside_type: Optional[str]
) -> Tuple[int, str]:
    """Calculate competition level impact based on historical data."""

    # Default: assume moderate competition
    if not naics_code:
        return 0, "Unknown competition level"

    # Query average number of offers for this NAICS from ContractAward
    try:
        result = db.query(
            func.avg(ContractAward.number_of_offers).label("avg_offers"),
            func.count(ContractAward.award_id).label("contract_count")
        ).filter(
            ContractAward.naics_code == naics_code,
            ContractAward.number_of_offers.isnot(None),
            ContractAward.number_of_offers > 0,
        ).first()

        if result and result.contract_count and result.contract_count >= 10:
            avg_offers = float(result.avg_offers or 5)

            if avg_offers < 3:
                return 15, f"Low competition: ~{avg_offers:.1f} avg bids in {naics_code}"
            elif avg_offers < 5:
                return 5, f"Moderate competition: ~{avg_offers:.1f} avg bids in {naics_code}"
            elif avg_offers < 10:
                return -5, f"Competitive: ~{avg_offers:.1f} avg bids in {naics_code}"
            else:
                return -10, f"Highly competitive: ~{avg_offers:.1f} avg bids in {naics_code}"
    except:
        pass

    # Fallback: use set-aside to estimate competition
    if set_aside_type:
        normalized = set_aside_type.upper()
        if any(sa in normalized for sa in ["8(A)", "8A", "HUBZONE", "SDVOSB"]):
            return 10, f"Limited competition: {set_aside_type} set-aside"
        elif "SMALL BUSINESS" in normalized:
            return 5, f"Moderate competition: Small business set-aside"

    return 0, "Unknown competition level"


def _calculate_incumbent_factor(
    db: Session,
    opportunity: Opportunity
) -> Tuple[int, str]:
    """Calculate incumbent advantage impact."""

    # Check if this is a recompete
    # Look for indicators in title/description
    title = (opportunity.title or "").lower()
    desc = (opportunity.description or "").lower()

    recompete_indicators = ["recompete", "follow-on", "successor", "incumbent", "continuation"]
    is_recompete = any(ind in title or ind in desc for ind in recompete_indicators)

    if not is_recompete:
        # Check if related to an existing contract
        if opportunity.related_notice_id:
            is_recompete = True

    if not is_recompete:
        return 0, "New requirement - no incumbent advantage"

    # This is a recompete - try to find incumbent
    incumbent_name = None

    # Try to extract incumbent from AI summary or description
    # Look for patterns like "Current contractor:", "Incumbent:", etc.
    import re
    incumbent_patterns = [
        r"incumbent[:\s]+([A-Za-z0-9\s,]+?)(?:\.|,|\n)",
        r"current contractor[:\s]+([A-Za-z0-9\s,]+?)(?:\.|,|\n)",
        r"held by[:\s]+([A-Za-z0-9\s,]+?)(?:\.|,|\n)",
    ]

    for pattern in incumbent_patterns:
        match = re.search(pattern, desc, re.IGNORECASE)
        if match:
            incumbent_name = match.group(1).strip()[:100]  # Limit length
            break

    if incumbent_name:
        return -15, f"Recompete with incumbent: {incumbent_name}"
    else:
        return -10, "Recompete - incumbent has advantage"


def _calculate_size_fit_factor(
    opportunity: Opportunity,
    profile: CompanyProfile
) -> Tuple[int, str]:
    """Calculate contract size fit impact."""

    # Get estimated value from AI analysis
    estimated_value = opportunity.ai_estimated_value_high or opportunity.ai_estimated_value_low

    if not estimated_value:
        return 0, "Contract value unknown"

    value = float(estimated_value)

    # Get user preferences
    min_val = float(profile.min_contract_value) if profile.min_contract_value else 0
    max_val = float(profile.max_contract_value) if profile.max_contract_value else None

    # No preferences set - assume flexible
    if not min_val and not max_val:
        return 0, f"Estimated value: ${value:,.0f} (no preferences set)"

    # Perfect fit
    if min_val <= value and (max_val is None or value <= max_val):
        return 10, f"${value:,.0f} - perfect fit for your company size"

    # Too small
    if value < min_val:
        ratio = value / min_val if min_val > 0 else 0
        if ratio >= 0.5:
            return -5, f"${value:,.0f} - slightly below your minimum (${min_val:,.0f})"
        return -10, f"${value:,.0f} - significantly below your minimum (${min_val:,.0f})"

    # Too large
    if max_val and value > max_val:
        ratio = max_val / value if value > 0 else 0
        if ratio >= 0.5:
            return -5, f"${value:,.0f} - slightly above your maximum (${max_val:,.0f})"
        return -10, f"${value:,.0f} - significantly above your capacity (${max_val:,.0f})"

    return 0, f"Estimated value: ${value:,.0f}"


def _calculate_past_performance_factor(
    opportunity: Opportunity,
    past_performances: List[PastPerformance]
) -> Tuple[int, str]:
    """Calculate past performance impact."""

    if not past_performances:
        return 0, "No past performance records"

    # Check for matching agency
    opp_agency = (opportunity.agency_name or "").lower()
    agency_match = None
    for pp in past_performances:
        if pp.agency_name and pp.agency_name.lower() in opp_agency or opp_agency in pp.agency_name.lower():
            agency_match = pp
            break

    if agency_match:
        rating = agency_match.performance_rating or agency_match.cpars_rating
        if rating in ["exceptional", "very_good"]:
            return 15, f"Excellent past performance with {agency_match.agency_name}"
        elif rating == "satisfactory":
            return 10, f"Good past performance with {agency_match.agency_name}"
        return 5, f"Past performance with {agency_match.agency_name}"

    # Check for matching NAICS
    opp_naics = opportunity.naics_code
    naics_match = None
    for pp in past_performances:
        if pp.naics_code == opp_naics:
            naics_match = pp
            break

    if naics_match:
        return 5, f"Past performance in NAICS {opp_naics}"

    # General past performance
    if len(past_performances) >= 3:
        return 3, f"{len(past_performances)} past performance records"

    return 0, "Limited past performance"


def _calculate_timeline_factor(
    response_deadline: Optional[datetime],
    min_days_to_respond: int
) -> Tuple[int, str]:
    """Calculate timeline pressure impact."""

    if not response_deadline:
        return 0, "No deadline specified"

    now = datetime.utcnow()
    days_remaining = (response_deadline - now).days

    if days_remaining < 0:
        return -20, "Deadline has passed"

    if days_remaining < min_days_to_respond:
        return -10, f"Only {days_remaining} days - very tight timeline"

    if days_remaining < min_days_to_respond * 1.5:
        return -5, f"{days_remaining} days - tight timeline"

    if days_remaining >= min_days_to_respond * 3:
        return 5, f"{days_remaining} days - plenty of time to prepare"

    return 0, f"{days_remaining} days to respond"


# =============================================================================
# Helper Functions
# =============================================================================

def _calculate_confidence(factors: List[Dict], profile: CompanyProfile) -> str:
    """Calculate confidence level in the prediction."""

    # More factors = more confidence
    factor_count = len(factors)

    # Profile completeness affects confidence
    completeness = profile.profile_completeness or 0

    # Calculate confidence
    if factor_count >= 5 and completeness >= 70:
        return "high"
    elif factor_count >= 3 and completeness >= 40:
        return "medium"
    else:
        return "low"


def _generate_recommendation(score: int, factors: List[Dict]) -> str:
    """Generate a human-readable recommendation."""

    if score >= 75:
        return "Strong fit - highly recommend pursuing this opportunity"
    elif score >= 60:
        return "Good fit - consider bidding if capacity allows"
    elif score >= 45:
        return "Moderate fit - evaluate against other opportunities"
    elif score >= 30:
        return "Weak fit - significant challenges to winning"
    else:
        return "Poor fit - not recommended unless strategically important"


# =============================================================================
# Public API Functions
# =============================================================================

def get_win_probability_for_opportunity(
    db: Session,
    opportunity_id: str,
    user_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get win probability for a specific opportunity and user.

    Requires user to have a company profile with:
    - At least one NAICS code
    - Business size specified

    Returns None if profile is incomplete.
    """
    from uuid import UUID

    # Get opportunity
    opportunity = db.query(Opportunity).filter(
        Opportunity.id == UUID(opportunity_id)
    ).first()

    if not opportunity:
        return None

    # Get user's company profile
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == UUID(user_id)
    ).first()

    if not profile:
        return {
            "error": "No company profile found",
            "message": "Please complete your company profile to see win probability"
        }

    # Get NAICS codes
    naics_codes = db.query(CompanyNAICS).filter(
        CompanyNAICS.company_profile_id == profile.id
    ).all()

    if not naics_codes:
        return {
            "error": "No NAICS codes configured",
            "message": "Please add NAICS codes to your company profile"
        }

    # Get certifications
    certifications = db.query(CompanyCertification).filter(
        CompanyCertification.company_profile_id == profile.id
    ).all()

    # Get past performances
    past_performances = db.query(PastPerformance).filter(
        PastPerformance.company_profile_id == profile.id
    ).all()

    # Calculate win probability
    result = calculate_win_probability(
        db,
        opportunity,
        profile,
        naics_codes,
        certifications,
        past_performances
    )

    # Add opportunity context
    result["opportunity"] = {
        "id": str(opportunity.id),
        "notice_id": opportunity.notice_id,
        "title": opportunity.title,
        "naics_code": opportunity.naics_code,
        "set_aside_type": opportunity.set_aside_type,
        "agency": opportunity.agency_name,
    }

    return result
