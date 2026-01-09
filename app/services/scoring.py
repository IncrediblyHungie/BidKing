"""
Opportunity Scoring Service

Calculates likelihood scores for federal contract opportunities
to estimate probability of being under $100K.

Also provides competition scoring to identify underserved opportunities.

Score range: 0-100
- Likelihood Score: Higher = more likely to be a smaller, accessible contract
- Competition Score: Lower = less competition, better chance of winning
"""

import re
from typing import Optional, Dict, Any, List


def calculate_likelihood_score(opportunity: dict) -> int:
    """
    Calculate likelihood score for an opportunity.

    The score estimates how likely the contract is to be under $100K
    and suitable for small businesses.

    Args:
        opportunity: Raw opportunity data from SAM.gov API

    Returns:
        Score from 0-100 (higher = more likely small contract)
    """
    score = 50  # Start neutral

    title = (opportunity.get("title") or "").lower()
    description = (opportunity.get("description") or "").lower()
    combined_text = f"{title} {description}"

    opp_type = opportunity.get("type", "")
    set_aside = opportunity.get("typeOfSetAside", "")
    set_aside_desc = (opportunity.get("typeOfSetAsideDescription") or "").lower()

    # ============================================
    # POSITIVE INDICATORS (likely small contract)
    # ============================================

    # Small business set-asides are strong indicators
    if set_aside:
        if any(term in set_aside_desc for term in [
            "small business", "8(a)", "hubzone", "sdvosb",
            "wosb", "edwosb", "sba", "small disadvantaged"
        ]):
            score += 15

    # Notice types that suggest smaller contracts
    if opp_type:
        opp_type_lower = opp_type.lower()
        if any(t in opp_type_lower for t in ["sources sought", "special notice", "presolicitation"]):
            score += 10
        if "combined synopsis" in opp_type_lower:
            score += 5

    # Title keywords suggesting smaller scope
    small_keywords = [
        "micro", "small", "support", "maintenance", "repair",
        "training", "study", "assessment", "review", "analysis",
        "consultation", "advisory", "task order", "delivery order",
        "license", "subscription", "renewal", "modification"
    ]
    for keyword in small_keywords:
        if keyword in title:
            score += 5
            break  # Only count once

    # Description patterns for small contracts
    if any(term in combined_text for term in [
        "simplified acquisition", "sap", "micropurchase",
        "under $250,000", "under $150,000", "under $100,000",
        "not to exceed", "ceiling of"
    ]):
        score += 15

    # Duration patterns (shorter = likely smaller)
    if any(term in combined_text for term in [
        "6 month", "6-month", "three month", "90 day",
        "one time", "one-time", "single delivery"
    ]):
        score += 10

    # Maintenance and licensing work often under $100K
    if any(term in combined_text for term in [
        "annual maintenance", "software license", "subscription renewal",
        "support services", "help desk", "tier 1", "tier 2"
    ]):
        score += 10

    # Specific small dollar mentions
    dollar_pattern = r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:thousand|k)?'
    matches = re.findall(dollar_pattern, combined_text)
    for match in matches:
        try:
            amount = float(match.replace(",", ""))
            if amount <= 100000:
                score += 15
                break
            elif amount <= 250000:
                score += 10
                break
        except ValueError:
            continue

    # ============================================
    # NEGATIVE INDICATORS (likely large contract)
    # ============================================

    # Enterprise-scale keywords in title
    large_keywords = [
        "enterprise", "system-wide", "global", "nationwide",
        "agency-wide", "department-wide", "comprehensive",
        "full and open", "unrestricted", "multi-year", "idiq",
        "indefinite delivery", "blanket purchase"
    ]
    for keyword in large_keywords:
        if keyword in title:
            score -= 15
            break

    # IDIQ and BPA contracts are usually large
    if any(term in combined_text for term in ["idiq", "indefinite delivery indefinite quantity", "bpa", "blanket purchase"]):
        score -= 10

    # Certification requirements suggest larger contracts
    if any(term in combined_text for term in [
        "cmmi", "iso 9001", "iso 27001", "fedramp", "fisma high",
        "secret clearance", "top secret", "sci", "ts/sci",
        "facility clearance"
    ]):
        score -= 15

    # Large dollar mentions
    for match in matches:
        try:
            amount = float(match.replace(",", ""))
            if amount >= 1000000:
                score -= 20
                break
            elif amount >= 500000:
                score -= 15
                break
            elif amount >= 250000:
                score -= 5
                break
        except ValueError:
            continue

    # Multiple years of performance
    if any(term in combined_text for term in [
        "five year", "5-year", "5 year", "four year", "4-year",
        "multi-year base", "with options"
    ]):
        score -= 10

    # Large team requirements
    if any(term in combined_text for term in [
        "minimum staff", "team of", "ftes required",
        "100 personnel", "50 personnel", "large team"
    ]):
        score -= 10

    # ============================================
    # NAICS-BASED ADJUSTMENTS
    # ============================================
    naics = opportunity.get("naicsCode") or ""

    # IT services NAICS codes often have smaller contracts
    small_friendly_naics = ["541511", "541512", "541519", "518210"]
    if naics[:6] in small_friendly_naics:
        score += 5

    # Construction and large systems NAICS less likely small
    large_naics_prefixes = ["23", "336", "333"]  # Construction, aerospace, machinery
    if any(naics.startswith(prefix) for prefix in large_naics_prefixes):
        score -= 5

    # ============================================
    # AGENCY-BASED ADJUSTMENTS
    # ============================================
    agency = (opportunity.get("departmentName") or opportunity.get("fullParentPathName") or "").lower()

    # Some agencies have more small contracts
    small_friendly_agencies = [
        "small business administration",
        "general services administration",
    ]
    if any(a in agency for a in small_friendly_agencies):
        score += 5

    # DoD tends to have larger contracts
    if any(term in agency for term in ["defense", "army", "navy", "air force", "dod"]):
        score -= 5

    # ============================================
    # ENSURE SCORE IS IN VALID RANGE
    # ============================================
    return max(0, min(100, score))


def get_score_category(score: int) -> str:
    """
    Get human-readable category for a score.

    Args:
        score: Likelihood score (0-100)

    Returns:
        Category string
    """
    if score >= 80:
        return "Very Likely Small"
    elif score >= 60:
        return "Likely Small"
    elif score >= 40:
        return "Possible"
    elif score >= 20:
        return "Unlikely Small"
    else:
        return "Likely Large"


def explain_score(opportunity: dict, score: int) -> list[str]:
    """
    Generate explanation for why a score was given.

    Args:
        opportunity: Raw opportunity data
        score: Calculated score

    Returns:
        List of explanation strings
    """
    reasons = []

    title = (opportunity.get("title") or "").lower()
    description = (opportunity.get("description") or "").lower()
    combined_text = f"{title} {description}"
    set_aside_desc = (opportunity.get("typeOfSetAsideDescription") or "").lower()

    # Check what contributed to the score
    if "small business" in set_aside_desc:
        reasons.append("Small business set-aside")

    if "sources sought" in (opportunity.get("type") or "").lower():
        reasons.append("Sources sought notice type")

    if any(term in title for term in ["support", "maintenance", "training"]):
        reasons.append("Title suggests support/maintenance work")

    if any(term in combined_text for term in ["simplified acquisition", "under $"]):
        reasons.append("References simplified acquisition or dollar threshold")

    if any(term in combined_text for term in ["idiq", "enterprise", "agency-wide"]):
        reasons.append("May be large-scale contract (IDIQ/enterprise)")

    if any(term in combined_text for term in ["clearance", "cmmi", "iso"]):
        reasons.append("Requires certifications/clearances")

    if not reasons:
        reasons.append("Standard scoring based on opportunity characteristics")

    return reasons


def calculate_combined_score(opportunity: dict) -> Dict[str, Any]:
    """
    Calculate a combined opportunity score considering both
    likelihood (contract size) and competition level.

    Higher combined score = better opportunity (likely small + low competition)

    Args:
        opportunity: Raw opportunity data

    Returns:
        Dict with likelihood_score, competition_score, combined_score, and analysis
    """
    from app.services.competition import calculate_competition_score

    # Get individual scores
    likelihood = calculate_likelihood_score(opportunity)
    competition_data = calculate_competition_score(opportunity)
    competition = competition_data["score"]

    # Combined score: high likelihood + low competition = high combined
    # Formula: (likelihood * 0.5) + ((100 - competition) * 0.5)
    # This gives equal weight to "likely small" and "low competition"
    inverted_competition = 100 - competition  # Invert so lower competition = higher score
    combined = int((likelihood * 0.5) + (inverted_competition * 0.5))

    # Determine overall recommendation
    if combined >= 75:
        recommendation = "🎯 High Priority - Small contract with low competition"
        priority = "high"
    elif combined >= 60:
        recommendation = "✅ Good Opportunity - Worth pursuing"
        priority = "medium-high"
    elif combined >= 45:
        recommendation = "⚠️ Moderate - Evaluate carefully"
        priority = "medium"
    elif combined >= 30:
        recommendation = "⚠️ Challenging - May be large or competitive"
        priority = "low"
    else:
        recommendation = "🔴 Difficult - Large contract or high competition"
        priority = "very-low"

    return {
        "likelihood_score": likelihood,
        "likelihood_category": get_score_category(likelihood),
        "competition_score": competition,
        "competition_level": competition_data["level_label"],
        "competition_factors": competition_data["factors"],
        "competition_recommendations": competition_data["recommendations"],
        "combined_score": combined,
        "recommendation": recommendation,
        "priority": priority,
    }


def get_early_stage_bonus(opportunity: dict) -> int:
    """
    Calculate bonus points for early-stage opportunities.

    Sources Sought and RFI notices get bonuses because:
    1. Less competition (fewer bidders aware)
    2. Ability to shape requirements
    3. More time to prepare

    Args:
        opportunity: Opportunity data

    Returns:
        Bonus points (0-20)
    """
    notice_type = (opportunity.get("notice_type") or opportunity.get("type") or "").lower()

    if "sources sought" in notice_type:
        return 20  # Best opportunity to influence requirements
    elif "rfi" in notice_type or "request for information" in notice_type:
        return 18
    elif "special notice" in notice_type:
        return 12
    elif "presolicitation" in notice_type:
        return 10
    elif "combined synopsis" in notice_type:
        return 5

    return 0


def is_underserved_opportunity(opportunity: dict) -> Dict[str, Any]:
    """
    Determine if an opportunity is in an underserved market.

    Underserved = combination of:
    - Low competition NAICS code
    - Set-aside designation
    - Early-stage notice
    - Small dollar indicators

    Args:
        opportunity: Opportunity data

    Returns:
        Dict with is_underserved flag and reasons
    """
    reasons = []
    score = 0

    naics_code = (opportunity.get("naics_code") or opportunity.get("naicsCode") or "")[:6]
    set_aside = opportunity.get("set_aside_type") or opportunity.get("typeOfSetAside") or ""
    notice_type = opportunity.get("notice_type") or opportunity.get("type") or ""
    title = (opportunity.get("title") or "").lower()
    description = (opportunity.get("description") or "").lower()

    # Low competition NAICS codes
    LOW_COMP_NAICS = {
        "541611", "519190", "611430", "541910", "541618",  # Adjacent markets
        "531190", "424320", "621610", "333997", "334614",  # FY2024 low-competition
    }
    if naics_code in LOW_COMP_NAICS:
        score += 25
        reasons.append(f"NAICS {naics_code} has historically low competition")

    # Set-aside designations
    if "sole source" in set_aside.lower():
        score += 30
        reasons.append("Sole source designation limits competition")
    elif any(x in set_aside.upper() for x in ["8(A)", "8A", "SDVOSB", "HUBZONE", "WOSB", "EDWOSB"]):
        score += 20
        reasons.append(f"Set-aside ({set_aside}) limits eligible bidders")
    elif "small business" in set_aside.lower():
        score += 10
        reasons.append("Small business set-aside")

    # Early-stage notices
    if "sources sought" in notice_type.lower():
        score += 25
        reasons.append("Sources Sought - early stage, can shape requirements")
    elif "presolicitation" in notice_type.lower():
        score += 15
        reasons.append("Presolicitation - limited awareness")

    # Small dollar indicators
    combined_text = f"{title} {description}"
    if any(term in combined_text for term in ["simplified acquisition", "micropurchase", "under $100,000"]):
        score += 15
        reasons.append("Simplified acquisition threshold")

    # Determine if underserved
    is_underserved = score >= 40

    return {
        "is_underserved": is_underserved,
        "underserved_score": score,
        "reasons": reasons,
        "recommendation": (
            "🎯 Underserved opportunity - prioritize for bid/no-bid"
            if is_underserved
            else "Standard opportunity - evaluate based on fit"
        ),
    }
