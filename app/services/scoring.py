"""
Opportunity Scoring Service

Calculates likelihood scores for federal contract opportunities
to estimate probability of being under $100K.

Score range: 0-100
- Higher scores = more likely to be a smaller, accessible contract
- Lower scores = likely large enterprise contracts
"""

import re
from typing import Optional


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
