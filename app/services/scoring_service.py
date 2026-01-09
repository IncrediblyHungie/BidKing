"""
Opportunity Scoring Service

Calculates personalized 6-dimension scores for opportunities based on
user's company profile, NAICS codes, certifications, and preferences.

Enhanced with text mining from attachments and capability statement matching.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.opportunity import Opportunity, OpportunityAttachment
from app.models.company import (
    CompanyProfile,
    CompanyNAICS,
    CompanyCertification,
    OpportunityScore,
    CapabilityStatement,
)
from app.services.text_mining_service import (
    extract_clearance_level,
    extract_dollar_amounts,
    extract_keywords,
    calculate_keyword_match_score,
    extract_all_from_opportunity,
)


# Set-aside type to certification mapping
SET_ASIDE_CERT_MAP = {
    # SBA 8(a)
    "8A": ["8(a)"],
    "8(a)": ["8(a)"],
    "SBA": ["8(a)"],
    # HUBZone
    "HZC": ["HUBZone"],
    "HUBZONE": ["HUBZone"],
    "HUBZone": ["HUBZone"],
    # Service-Disabled Veteran
    "SDVOSBC": ["SDVOSB"],
    "SDVOSB": ["SDVOSB"],
    "Service-Disabled Veteran-Owned Small Business": ["SDVOSB"],
    # Veteran-Owned
    "VOSB": ["VOSB", "SDVOSB"],
    "VSB": ["VOSB", "SDVOSB"],
    # Women-Owned
    "WOSB": ["WOSB", "EDWOSB"],
    "EDWOSB": ["EDWOSB"],
    "Women-Owned Small Business": ["WOSB", "EDWOSB"],
    # Small Disadvantaged Business
    "SDB": ["SDB", "8(a)"],
    # Small Business
    "SBP": ["small_business"],  # Any small business qualifies
    "Small Business": ["small_business"],
    "Total Small Business Set-Aside": ["small_business"],
}

# Clearance level hierarchy (higher index = higher clearance)
CLEARANCE_LEVELS = ["None", "Confidential", "Secret", "Top Secret", "TS/SCI"]


def calculate_naics_score(
    opportunity_naics: Optional[str],
    user_naics_codes: List[CompanyNAICS]
) -> tuple[int, Dict[str, Any]]:
    """
    Calculate NAICS match score.

    Returns:
        Tuple of (score 0-100, breakdown dict)
    """
    if not opportunity_naics or not user_naics_codes:
        return 50, {"reason": "no_naics_data", "match_type": None}

    user_codes = [n.naics_code for n in user_naics_codes]
    primary_codes = [n.naics_code for n in user_naics_codes if n.is_primary]

    # Exact match with primary NAICS
    if opportunity_naics in primary_codes:
        return 100, {"reason": "exact_primary_match", "match_type": "primary", "matched_code": opportunity_naics}

    # Exact match with any NAICS
    if opportunity_naics in user_codes:
        return 90, {"reason": "exact_match", "match_type": "exact", "matched_code": opportunity_naics}

    # Check 4-digit match (same industry group)
    opp_4digit = opportunity_naics[:4] if len(opportunity_naics) >= 4 else opportunity_naics
    for code in user_codes:
        if code[:4] == opp_4digit:
            return 70, {"reason": "industry_group_match", "match_type": "4digit", "matched_code": code}

    # Check 2-digit match (same sector)
    opp_2digit = opportunity_naics[:2] if len(opportunity_naics) >= 2 else opportunity_naics
    for code in user_codes:
        if code[:2] == opp_2digit:
            return 40, {"reason": "sector_match", "match_type": "2digit", "matched_code": code}

    # No match
    return 10, {"reason": "no_match", "match_type": None, "opportunity_naics": opportunity_naics}


def calculate_eligibility_score(
    set_aside_type: Optional[str],
    user_certifications: List[CompanyCertification],
    business_size: Optional[str]
) -> tuple[int, Dict[str, Any]]:
    """
    Calculate set-aside eligibility score.

    Returns:
        Tuple of (score 0-100, breakdown dict)
    """
    # No set-aside = full and open competition
    if not set_aside_type or set_aside_type.lower() in ["none", "full and open", ""]:
        return 100, {"reason": "full_and_open", "set_aside": None, "eligible": True}

    # Get user's active certifications
    user_certs = [c.certification_type for c in user_certifications if c.is_active]

    # Normalize set-aside type
    normalized_set_aside = set_aside_type.upper().replace(" ", "").replace("-", "")

    # Check if user has matching certification
    required_certs = None
    for key, certs in SET_ASIDE_CERT_MAP.items():
        if key.upper().replace(" ", "").replace("-", "") == normalized_set_aside or \
           key.upper() in normalized_set_aside or normalized_set_aside in key.upper():
            required_certs = certs
            break

    if required_certs:
        # Check for small_business special case
        if "small_business" in required_certs:
            if business_size == "small":
                return 100, {"reason": "small_business_eligible", "set_aside": set_aside_type, "eligible": True}
            else:
                return 20, {"reason": "not_small_business", "set_aside": set_aside_type, "eligible": False}

        # Check if user has any of the required certs
        for cert in required_certs:
            if cert in user_certs:
                return 100, {"reason": "certification_match", "set_aside": set_aside_type, "matched_cert": cert, "eligible": True}

        # Has set-aside but user doesn't have cert
        return 0, {"reason": "missing_certification", "set_aside": set_aside_type, "required_certs": required_certs, "eligible": False}

    # Unknown set-aside type - assume partial eligibility
    return 50, {"reason": "unknown_set_aside", "set_aside": set_aside_type, "eligible": "unknown"}


def calculate_scale_score(
    estimated_value: Optional[Decimal],
    min_contract_value: Optional[Decimal],
    max_contract_value: Optional[Decimal],
    typical_size: Optional[str]
) -> tuple[int, Dict[str, Any]]:
    """
    Calculate contract size fit score.

    Returns:
        Tuple of (score 0-100, breakdown dict)
    """
    # If no estimated value, use typical size matching
    if not estimated_value:
        # Default to neutral score
        return 50, {"reason": "no_value_estimate", "fit": "unknown"}

    # If user hasn't set preferences, assume they're flexible
    if not min_contract_value and not max_contract_value:
        return 70, {"reason": "no_preferences_set", "estimated_value": float(estimated_value), "fit": "assumed_fit"}

    value = float(estimated_value)
    min_val = float(min_contract_value) if min_contract_value else 0
    # Use None for no max (open-ended) and handle comparison separately
    max_val = float(max_contract_value) if max_contract_value else None

    # Perfect fit - within range (if no max, any value above min is fine)
    if min_val <= value and (max_val is None or value <= max_val):
        return 100, {"reason": "within_range", "estimated_value": value, "min": min_val, "max": max_val, "fit": "perfect"}

    # Slightly under min (within 50%)
    if value < min_val:
        ratio = value / min_val if min_val > 0 else 0
        if ratio >= 0.5:
            score = int(50 + (ratio * 50))
            return score, {"reason": "below_min", "estimated_value": value, "min": min_val, "ratio": ratio, "fit": "undersized"}
        return 30, {"reason": "too_small", "estimated_value": value, "min": min_val, "fit": "too_small"}

    # Over max (only if max_val is set)
    if max_val is not None and value > max_val:
        ratio = max_val / value if value > 0 else 0
        if ratio >= 0.5:
            score = int(50 + (ratio * 50))
            return score, {"reason": "above_max", "estimated_value": value, "max": max_val, "ratio": ratio, "fit": "oversized"}
        return 20, {"reason": "too_large", "estimated_value": value, "max": max_val, "fit": "too_large"}

    return 50, {"reason": "calculation_error", "fit": "unknown"}


def calculate_clearance_score(
    required_clearance: Optional[str],
    user_clearance: Optional[str],
    has_sci: bool
) -> tuple[int, Dict[str, Any]]:
    """
    Calculate security clearance compatibility score.

    Returns:
        Tuple of (score 0-100, breakdown dict)
    """
    # No clearance required
    if not required_clearance or required_clearance.lower() in ["none", "unclassified", ""]:
        return 100, {"reason": "no_clearance_required", "required": None, "user_level": user_clearance, "compatible": True}

    # User has no clearance but one is required
    if not user_clearance or user_clearance.lower() == "none":
        return 0, {"reason": "clearance_required_but_none", "required": required_clearance, "user_level": None, "compatible": False}

    # Check SCI requirement
    if "SCI" in required_clearance.upper():
        if has_sci:
            return 100, {"reason": "sci_capable", "required": required_clearance, "compatible": True}
        return 0, {"reason": "sci_required_but_not_capable", "required": required_clearance, "compatible": False}

    # Compare clearance levels
    try:
        required_level = next((i for i, level in enumerate(CLEARANCE_LEVELS) if level.lower() in required_clearance.lower()), -1)
        user_level = next((i for i, level in enumerate(CLEARANCE_LEVELS) if level.lower() in user_clearance.lower()), -1)

        if user_level >= required_level:
            return 100, {"reason": "clearance_meets_requirement", "required": required_clearance, "user_level": user_clearance, "compatible": True}
        else:
            # Partial score if close
            if required_level - user_level == 1:
                return 30, {"reason": "clearance_one_level_below", "required": required_clearance, "user_level": user_clearance, "compatible": False}
            return 0, {"reason": "insufficient_clearance", "required": required_clearance, "user_level": user_clearance, "compatible": False}
    except:
        return 50, {"reason": "clearance_comparison_error", "required": required_clearance, "user_level": user_clearance, "compatible": "unknown"}


def calculate_contract_type_score(
    contract_type: Optional[str],
    pref_ffp: int,
    pref_tm: int,
    pref_cost_plus: int,
    pref_idiq: int
) -> tuple[int, Dict[str, Any]]:
    """
    Calculate contract type preference score.

    Returns:
        Tuple of (score 0-100, breakdown dict)
    """
    if not contract_type:
        return 60, {"reason": "no_contract_type", "type": None, "preference": None}

    contract_type_lower = contract_type.lower()

    # Map contract types to preferences
    preference = 3  # Default neutral
    matched_type = None

    if "firm" in contract_type_lower and "fixed" in contract_type_lower or "ffp" in contract_type_lower:
        preference = pref_ffp
        matched_type = "FFP"
    elif "time" in contract_type_lower and "material" in contract_type_lower or "t&m" in contract_type_lower:
        preference = pref_tm
        matched_type = "T&M"
    elif "cost" in contract_type_lower and "plus" in contract_type_lower or "cpff" in contract_type_lower or "cpaf" in contract_type_lower:
        preference = pref_cost_plus
        matched_type = "Cost-Plus"
    elif "idiq" in contract_type_lower or "indefinite" in contract_type_lower or "bpa" in contract_type_lower:
        preference = pref_idiq
        matched_type = "IDIQ"

    # Convert 1-5 preference to 0-100 score
    score = (preference - 1) * 25  # 1=0, 2=25, 3=50, 4=75, 5=100

    return score, {"reason": "preference_match", "type": contract_type, "matched_type": matched_type, "preference_level": preference}


def calculate_timeline_score(
    response_deadline: Optional[datetime],
    min_days_to_respond: int,
    can_rush: bool
) -> tuple[int, Dict[str, Any]]:
    """
    Calculate timeline feasibility score.

    Returns:
        Tuple of (score 0-100, breakdown dict)
    """
    if not response_deadline:
        return 50, {"reason": "no_deadline", "days_remaining": None, "feasible": "unknown"}

    now = datetime.utcnow()
    days_remaining = (response_deadline - now).days

    # Already past deadline
    if days_remaining < 0:
        return 0, {"reason": "past_deadline", "days_remaining": days_remaining, "feasible": False}

    # Plenty of time (2x minimum)
    if days_remaining >= min_days_to_respond * 2:
        return 100, {"reason": "plenty_of_time", "days_remaining": days_remaining, "min_required": min_days_to_respond, "feasible": True}

    # Within comfortable range
    if days_remaining >= min_days_to_respond:
        # Scale from 70-100 based on buffer
        buffer_ratio = (days_remaining - min_days_to_respond) / min_days_to_respond
        score = int(70 + (buffer_ratio * 30))
        return score, {"reason": "adequate_time", "days_remaining": days_remaining, "min_required": min_days_to_respond, "feasible": True}

    # Tight deadline
    if can_rush:
        # User can rush - give partial score
        ratio = days_remaining / min_days_to_respond
        score = int(30 + (ratio * 40))  # 30-70 range
        return score, {"reason": "rush_possible", "days_remaining": days_remaining, "min_required": min_days_to_respond, "rush_required": True, "feasible": True}

    # Can't rush and deadline is tight
    ratio = days_remaining / min_days_to_respond
    score = int(ratio * 30)  # 0-30 range
    return score, {"reason": "insufficient_time", "days_remaining": days_remaining, "min_required": min_days_to_respond, "feasible": False}


def calculate_overall_score(
    capability: int,
    eligibility: int,
    scale: int,
    clearance: int,
    contract_type: int,
    timeline: int
) -> int:
    """
    Calculate weighted overall score.

    Weights:
    - Capability (NAICS): 25%
    - Eligibility (Set-aside): 20%
    - Scale Fit: 15%
    - Clearance: 15%
    - Contract Type: 10%
    - Timeline: 15%
    """
    weighted = (
        capability * 0.25 +
        eligibility * 0.20 +
        scale * 0.15 +
        clearance * 0.15 +
        contract_type * 0.10 +
        timeline * 0.15
    )
    return int(round(weighted))


def score_opportunity_for_user(
    db: Session,
    opportunity: Opportunity,
    profile: CompanyProfile,
    naics_codes: List[CompanyNAICS],
    certifications: List[CompanyCertification]
) -> OpportunityScore:
    """
    Calculate and return scores for a single opportunity for a user.

    Enhanced with text mining from attachments for:
    - Clearance requirements
    - Dollar amounts (contract value)
    - Keyword matching against capability statements
    """
    # Get attachment text for text mining
    attachments = db.query(OpportunityAttachment).filter(
        OpportunityAttachment.opportunity_id == opportunity.id
    ).all()
    attachment_texts = [att.text_content for att in attachments if att.text_content]

    # Extract structured data from description + attachments
    all_text = opportunity.description or ""
    for att_text in attachment_texts:
        all_text += "\n\n" + att_text

    # Extract clearance level from text
    extracted_clearance, clearance_extraction_info = extract_clearance_level(all_text)

    # Extract dollar amounts from text
    extracted_min_value, extracted_max_value, value_extraction_info = extract_dollar_amounts(all_text)

    # Extract keywords for capability matching
    opp_keywords, keyword_extraction_info = extract_keywords(all_text)

    # Get user's capability statement keywords
    capability_statements = db.query(CapabilityStatement).filter(
        CapabilityStatement.company_profile_id == profile.id
    ).all()

    user_keywords = []
    user_capability_text = ""
    for cap in capability_statements:
        if cap.keywords:
            user_keywords.extend(cap.keywords)
        if cap.full_text:
            user_capability_text += cap.full_text + "\n"

    # Calculate NAICS score (base capability)
    naics_score, naics_breakdown = calculate_naics_score(
        opportunity.naics_code,
        naics_codes
    )

    # Calculate keyword match score
    keyword_score, keyword_breakdown = calculate_keyword_match_score(
        opp_keywords,
        user_keywords,
        user_capability_text
    )

    # Combined capability score: 70% NAICS + 30% keyword match
    capability_score = int(naics_score * 0.7 + keyword_score * 0.3)
    capability_breakdown = {
        "naics_score": naics_score,
        "naics_breakdown": naics_breakdown,
        "keyword_score": keyword_score,
        "keyword_breakdown": keyword_breakdown,
        "combined_method": "70% NAICS + 30% keywords",
    }

    eligibility_score, eligibility_breakdown = calculate_eligibility_score(
        opportunity.set_aside_type,
        certifications,
        profile.business_size
    )

    # Scale Fit - now using extracted dollar amounts!
    estimated_value = extracted_max_value or extracted_min_value
    scale_score, scale_breakdown = calculate_scale_score(
        estimated_value,
        profile.min_contract_value,
        profile.max_contract_value,
        profile.typical_contract_size
    )
    scale_breakdown["extraction_info"] = value_extraction_info

    # Clearance - now using extracted clearance level!
    clearance_score, clearance_breakdown = calculate_clearance_score(
        extracted_clearance,
        profile.facility_clearance,
        profile.has_sci_capability
    )
    clearance_breakdown["extraction_info"] = clearance_extraction_info

    contract_type_score, contract_type_breakdown = calculate_contract_type_score(
        opportunity.contract_type,
        profile.pref_firm_fixed_price,
        profile.pref_time_materials,
        profile.pref_cost_plus,
        profile.pref_idiq
    )

    timeline_score, timeline_breakdown = calculate_timeline_score(
        opportunity.response_deadline,
        profile.min_days_to_respond or 7,
        profile.can_rush_proposals or False
    )

    # Calculate overall
    overall = calculate_overall_score(
        capability_score,
        eligibility_score,
        scale_score,
        clearance_score,
        contract_type_score,
        timeline_score
    )

    # Create or update score record
    existing_score = db.query(OpportunityScore).filter(
        and_(
            OpportunityScore.user_id == profile.user_id,
            OpportunityScore.opportunity_id == opportunity.id
        )
    ).first()

    if existing_score:
        score = existing_score
    else:
        score = OpportunityScore(
            id=uuid.uuid4(),
            user_id=profile.user_id,
            opportunity_id=opportunity.id
        )

    # Update scores
    score.overall_score = overall
    score.capability_score = capability_score
    score.capability_breakdown = capability_breakdown
    score.eligibility_score = eligibility_score
    score.eligibility_breakdown = eligibility_breakdown
    score.scale_score = scale_score
    score.scale_breakdown = scale_breakdown
    score.win_probability_score = clearance_score  # Using clearance as proxy for now
    score.win_probability_breakdown = clearance_breakdown
    score.strategic_score = contract_type_score
    score.strategic_breakdown = contract_type_breakdown
    score.timeline_score = timeline_score
    score.timeline_breakdown = timeline_breakdown
    score.is_stale = False
    score.stale_reason = None
    score.calculated_at = datetime.utcnow()

    if not existing_score:
        db.add(score)

    return score


def calculate_all_scores_for_user(
    db: Session,
    user_id: str
) -> Dict[str, Any]:
    """
    Calculate scores for all active opportunities for a user.

    Returns:
        Dict with status, count, and any errors
    """
    # Get user's company profile
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == user_id
    ).first()

    if not profile:
        return {
            "status": "error",
            "message": "No company profile found. Please complete company setup first.",
            "scored": 0
        }

    # Get user's NAICS codes
    naics_codes = db.query(CompanyNAICS).filter(
        CompanyNAICS.company_profile_id == profile.id
    ).all()

    # Get user's certifications
    certifications = db.query(CompanyCertification).filter(
        CompanyCertification.company_profile_id == profile.id
    ).all()

    # Get all active opportunities
    opportunities = db.query(Opportunity).filter(
        Opportunity.status == "active"
    ).all()

    scored_count = 0
    errors = []
    score_summary = {
        "high_scores": 0,  # >= 70
        "medium_scores": 0,  # 40-69
        "low_scores": 0,  # < 40
    }

    # Debug info
    user_naics_list = [n.naics_code for n in naics_codes]
    user_certs_list = [c.certification_type for c in certifications]
    print(f"[SCORING] User {user_id}: NAICS={user_naics_list}, Certs={user_certs_list}, Business Size={profile.business_size}")
    print(f"[SCORING] Total opportunities to score: {len(opportunities)}")

    # Log first 3 opportunities for debugging
    debug_count = 0

    for opp in opportunities:
        try:
            score = score_opportunity_for_user(
                db, opp, profile, naics_codes, certifications
            )
            scored_count += 1

            # Debug: log first 3 opportunities
            if debug_count < 3:
                print(f"[SCORING DEBUG] Opp {opp.notice_id[:20]}...: overall={score.overall_score}, "
                      f"capability={score.capability_score}, eligibility={score.eligibility_score}, "
                      f"scale={score.scale_score}, timeline={score.timeline_score} | "
                      f"opp_naics={opp.naics_code}, set_aside={opp.set_aside_type}")
                debug_count += 1

            # Track score distribution
            if score.overall_score >= 70:
                score_summary["high_scores"] += 1
            elif score.overall_score >= 40:
                score_summary["medium_scores"] += 1
            else:
                score_summary["low_scores"] += 1

        except Exception as e:
            errors.append({
                "opportunity_id": str(opp.id),
                "notice_id": opp.notice_id,
                "error": str(e)
            })

    db.commit()

    return {
        "status": "completed",
        "message": f"Scored {scored_count} opportunities",
        "scored": scored_count,
        "total_opportunities": len(opportunities),
        "score_distribution": score_summary,
        "errors": errors if errors else None,
        "profile_completeness": profile.profile_completeness,
        "naics_count": len(naics_codes),
        "naics_codes": user_naics_list,
        "cert_count": len(certifications),
        "certifications": user_certs_list,
        "business_size": profile.business_size,
    }


def mark_scores_stale_for_user(db: Session, user_id: str, reason: str) -> int:
    """
    Mark all scores for a user as stale (needs recalculation).

    Returns:
        Number of scores marked stale
    """
    result = db.query(OpportunityScore).filter(
        OpportunityScore.user_id == user_id
    ).update({
        "is_stale": True,
        "stale_reason": reason
    })
    db.commit()
    return result
