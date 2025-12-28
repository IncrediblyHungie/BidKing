"""
Competition Analysis Service for BidKing

Provides competition indicators for federal contracting opportunities.
Since SAM.gov doesn't provide bid count data, we infer competition levels from:
1. Historical USAspending data (award patterns in NAICS/agency)
2. Set-aside designations (small business set-asides have less competition)
3. Notice types (early-stage = less competition)
4. Contract characteristics (simplified acquisition = less competition)
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

logger = logging.getLogger(__name__)

# Competition level thresholds
COMPETITION_LEVELS = {
    "very_low": {"min": 0, "max": 20, "label": "Very Low Competition", "color": "green"},
    "low": {"min": 21, "max": 40, "label": "Low Competition", "color": "lime"},
    "moderate": {"min": 41, "max": 60, "label": "Moderate Competition", "color": "yellow"},
    "high": {"min": 61, "max": 80, "label": "High Competition", "color": "orange"},
    "very_high": {"min": 81, "max": 100, "label": "Very High Competition", "color": "red"},
}

# Set-aside types and their competition modifiers (lower = less competition)
SET_ASIDE_COMPETITION = {
    # Sole source / limited competition
    "8(a) Sole Source": 10,
    "HUBZone Sole Source": 15,
    "SDVOSB Sole Source": 15,
    "WOSB Sole Source": 15,
    "EDWOSB Sole Source": 15,
    # Set-asides (limited pool)
    "8(a)": 30,
    "8A": 30,
    "HUBZone": 35,
    "SDVOSB": 35,
    "SDVOSBC": 35,
    "Service-Disabled Veteran-Owned Small Business": 35,
    "WOSB": 35,
    "EDWOSB": 35,
    "Women-Owned Small Business": 35,
    "SBA": 40,
    "Small Business": 45,
    "SB": 45,
    "Small Business Set-Aside": 45,
    "Partial Small Business": 55,
    # Full and open (maximum competition)
    "Full and Open": 90,
    "Unrestricted": 90,
    None: 70,  # No set-aside specified = assume moderate-high
}

# Notice types and their competition modifiers
NOTICE_TYPE_COMPETITION = {
    # Early stage = less competition (fewer bidders aware)
    "Sources Sought": 25,
    "Request for Information": 20,
    "RFI": 20,
    "Special Notice": 30,
    "Presolicitation": 40,
    # Active solicitations = more competition
    "Combined Synopsis/Solicitation": 65,
    "Solicitation": 70,
    "Amendment": 70,
    # Awards (already competed)
    "Award Notice": 100,
    "Intent to Bundle": 60,
    None: 60,  # Default
}

# NAICS codes with historically low competition (FY2024 data)
# Format: naics_code -> (avg_bids, competition_score)
LOW_COMPETITION_NAICS = {
    "531190": (1.0, 15),   # Lessors of Other Real Estate
    "424320": (1.0, 15),   # Clothing Wholesalers
    "621610": (1.0, 15),   # Home Health Care Services
    "333997": (1.0, 15),   # Scale Manufacturing
    "334614": (1.0, 15),   # Software Media Manufacturing
    "453210": (1.01, 18),  # Office Supplies
    "532283": (1.05, 20),  # Health Equipment Rental
    "623110": (1.05, 20),  # Nursing Care Facilities
    "624310": (1.06, 22),  # Vocational Rehabilitation
    "621991": (1.07, 24),  # Blood/Organ Banks
    # Adjacent markets (estimated based on FY2024 SB trends)
    "541611": (2.5, 45),   # Management Consulting
    "519190": (1.8, 35),   # Other Information Services
    "611430": (2.0, 40),   # Professional Training
    "541910": (2.2, 42),   # Marketing Research
    "541618": (2.3, 44),   # Other Management Consulting
}

# High competition NAICS codes (IT services)
HIGH_COMPETITION_NAICS = {
    "541511": (4.5, 75),   # Custom Programming
    "541512": (4.2, 72),   # Systems Design
    "541519": (3.8, 68),   # Other Computer Services
    "518210": (3.5, 65),   # Data Processing/Hosting
    "541690": (3.2, 62),   # Technical Consulting
}


def calculate_competition_score(
    opportunity: Dict[str, Any],
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Calculate a competition score for an opportunity.

    The score estimates how competitive the bidding will be (0-100).
    Lower scores = less competition = better chance of winning.

    Args:
        opportunity: Opportunity data dict with fields like naics_code, set_aside_type, etc.
        db: Optional database session for historical analysis

    Returns:
        Dict with:
        - score: 0-100 competition score
        - level: Competition level label
        - factors: List of contributing factors
        - recommendations: Actionable advice
    """
    factors = []
    score_components = []

    # ========================================
    # 1. Set-Aside Analysis (weight: 35%)
    # ========================================
    set_aside = opportunity.get("set_aside_type") or opportunity.get("typeOfSetAside")
    set_aside_score = SET_ASIDE_COMPETITION.get(set_aside, 70)
    score_components.append(("set_aside", set_aside_score, 0.35))

    if set_aside and "sole source" in set_aside.lower():
        factors.append(f"✅ Sole source designation ({set_aside}) - minimal competition")
    elif set_aside and any(x in set_aside.upper() for x in ["8(A)", "8A", "SDVOSB", "HUBZONE", "WOSB"]):
        factors.append(f"✅ Set-aside: {set_aside} - limited competition pool")
    elif set_aside and "small business" in set_aside.lower():
        factors.append(f"⚠️ Small business set-aside - moderate competition")
    elif set_aside in ["Full and Open", "Unrestricted"]:
        factors.append(f"⚠️ {set_aside} competition - expect many bidders")
    else:
        factors.append("ℹ️ No set-aside specified - competition level unclear")

    # ========================================
    # 2. Notice Type Analysis (weight: 25%)
    # ========================================
    notice_type = opportunity.get("notice_type") or opportunity.get("type")
    notice_score = NOTICE_TYPE_COMPETITION.get(notice_type, 60)
    score_components.append(("notice_type", notice_score, 0.25))

    if notice_type in ["Sources Sought", "Request for Information", "RFI"]:
        factors.append(f"✅ Early-stage notice ({notice_type}) - position yourself before competition")
    elif notice_type == "Presolicitation":
        factors.append("✅ Presolicitation - still early, limited awareness")
    elif notice_type in ["Solicitation", "Combined Synopsis/Solicitation"]:
        factors.append(f"⚠️ Active {notice_type} - competition already building")

    # ========================================
    # 3. NAICS Competition History (weight: 25%)
    # ========================================
    naics_code = opportunity.get("naics_code") or opportunity.get("naicsCode") or ""
    naics_code = str(naics_code)[:6]  # Normalize to 6 digits

    if naics_code in LOW_COMPETITION_NAICS:
        avg_bids, naics_score = LOW_COMPETITION_NAICS[naics_code]
        factors.append(f"✅ NAICS {naics_code} averages {avg_bids:.1f} bids/solicitation - low competition")
    elif naics_code in HIGH_COMPETITION_NAICS:
        avg_bids, naics_score = HIGH_COMPETITION_NAICS[naics_code]
        factors.append(f"⚠️ NAICS {naics_code} averages {avg_bids:.1f} bids/solicitation - competitive")
    else:
        # Default for unknown NAICS
        naics_score = 55
        factors.append(f"ℹ️ NAICS {naics_code} - competition level unknown")

    score_components.append(("naics", naics_score, 0.25))

    # ========================================
    # 4. Contract Characteristics (weight: 15%)
    # ========================================
    title = (opportunity.get("title") or "").lower()
    description = (opportunity.get("description") or "").lower()
    combined_text = f"{title} {description}"

    char_score = 50  # Start neutral

    # Simplified acquisition = less competition
    if any(term in combined_text for term in ["simplified acquisition", "sap", "micropurchase", "under $25,000"]):
        char_score -= 25
        factors.append("✅ Simplified acquisition - fewer competitors")

    # Short duration = less attractive to large contractors
    if any(term in combined_text for term in ["6 month", "90 day", "one-time", "single delivery"]):
        char_score -= 15
        factors.append("✅ Short duration - less attractive to large primes")

    # Remote/specific location = fewer eligible bidders
    if any(term in combined_text for term in ["remote work", "100% remote", "telework"]):
        char_score -= 10
        factors.append("✅ Remote work option - wider bidder pool but often missed")

    # Large enterprise = high competition
    if any(term in combined_text for term in ["enterprise", "agency-wide", "department-wide", "nationwide"]):
        char_score += 20
        factors.append("⚠️ Enterprise scope - expect major contractor competition")

    # IDIQ = attracts many bidders
    if any(term in combined_text for term in ["idiq", "indefinite delivery"]):
        char_score += 15
        factors.append("⚠️ IDIQ vehicle - typically high competition")

    char_score = max(10, min(90, char_score))  # Clamp
    score_components.append(("characteristics", char_score, 0.15))

    # ========================================
    # Calculate Weighted Final Score
    # ========================================
    final_score = sum(score * weight for _, score, weight in score_components)
    final_score = int(max(0, min(100, final_score)))

    # Determine competition level
    level = "moderate"
    for level_name, level_data in COMPETITION_LEVELS.items():
        if level_data["min"] <= final_score <= level_data["max"]:
            level = level_name
            break

    level_info = COMPETITION_LEVELS[level]

    # Generate recommendations
    recommendations = _generate_recommendations(
        final_score, set_aside, notice_type, naics_code, factors
    )

    return {
        "score": final_score,
        "level": level,
        "level_label": level_info["label"],
        "level_color": level_info["color"],
        "factors": factors,
        "recommendations": recommendations,
        "components": {
            name: {"score": score, "weight": f"{weight*100:.0f}%"}
            for name, score, weight in score_components
        },
    }


def _generate_recommendations(
    score: int,
    set_aside: Optional[str],
    notice_type: Optional[str],
    naics_code: str,
    factors: List[str],
) -> List[str]:
    """Generate actionable recommendations based on competition analysis."""
    recommendations = []

    if score <= 30:
        recommendations.append("🎯 Excellent opportunity - prioritize this bid")
        if notice_type in ["Sources Sought", "RFI"]:
            recommendations.append("📝 Respond to shape requirements in your favor")

    elif score <= 50:
        recommendations.append("✅ Good opportunity with manageable competition")
        if not set_aside or set_aside in ["Full and Open", "Unrestricted"]:
            recommendations.append("💡 Consider teaming with set-aside eligible partners")

    elif score <= 70:
        recommendations.append("⚠️ Moderate competition - ensure strong differentiators")
        recommendations.append("📊 Research incumbent and past awards before bidding")

    else:
        recommendations.append("🔴 High competition - carefully assess bid/no-bid decision")
        recommendations.append("🤝 Consider subcontracting role vs. prime pursuit")
        if naics_code in HIGH_COMPETITION_NAICS:
            recommendations.append("💡 Look for adjacent NAICS codes with less competition")

    return recommendations


def get_historical_competition(
    db: Session,
    naics_code: str,
    agency_name: Optional[str] = None,
    lookback_days: int = 365,
) -> Dict[str, Any]:
    """
    Analyze historical competition for a NAICS/agency combination.

    Uses USAspending award data to estimate competition patterns.
    """
    from app.models import ContractAward, RecompeteOpportunity

    cutoff_date = datetime.utcnow().date() - timedelta(days=lookback_days)

    # Query historical awards
    query = db.query(ContractAward).filter(
        ContractAward.naics_code == naics_code,
        ContractAward.award_date >= cutoff_date,
    )

    if agency_name:
        query = query.filter(
            ContractAward.awarding_agency_name.ilike(f"%{agency_name}%")
        )

    awards = query.all()

    if not awards:
        return {
            "has_history": False,
            "message": f"No historical data for NAICS {naics_code}",
        }

    # Analyze patterns
    total_awards = len(awards)
    unique_recipients = len(set(a.recipient_uei for a in awards if a.recipient_uei))
    total_value = sum(float(a.total_obligation or 0) for a in awards)
    avg_value = total_value / total_awards if total_awards else 0

    # Incumbent concentration (how much goes to repeat winners)
    from collections import Counter
    recipient_counts = Counter(a.recipient_name for a in awards if a.recipient_name)
    top_3_share = sum(c for _, c in recipient_counts.most_common(3)) / total_awards if total_awards else 0

    # Competition indicator based on concentration
    if top_3_share > 0.8:
        competition_indicator = "Low (concentrated market)"
        estimated_bidders = 1.5
    elif top_3_share > 0.6:
        competition_indicator = "Moderate (some incumbents)"
        estimated_bidders = 2.5
    else:
        competition_indicator = "High (diverse market)"
        estimated_bidders = 4.0

    return {
        "has_history": True,
        "naics_code": naics_code,
        "agency": agency_name,
        "period_days": lookback_days,
        "total_awards": total_awards,
        "unique_recipients": unique_recipients,
        "total_value": total_value,
        "avg_value": avg_value,
        "top_3_share": round(top_3_share * 100, 1),
        "competition_indicator": competition_indicator,
        "estimated_bidders": estimated_bidders,
        "top_recipients": [
            {"name": name, "awards": count}
            for name, count in recipient_counts.most_common(5)
        ],
    }
