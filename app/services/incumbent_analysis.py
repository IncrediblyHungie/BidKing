"""
Incumbent Vulnerability Analysis Service

Analyzes incumbents on federal contracts to identify "beatable" opportunities.
Uses USAspending contract data to calculate vulnerability scores based on:
- Agency concentration risk
- NAICS expertise/specialization
- Contract value trajectory
- Market share
- Recompete retention rate

Note: This is a data-driven heuristic model. CPARS performance ratings,
GAO protest records, and financial health data are NOT available.
"""

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_

from app.models.market_data import ContractAward, RecompeteOpportunity, Recipient


# =============================================================================
# Vulnerability Score Weights
# =============================================================================

WEIGHTS = {
    "concentration": 0.25,      # Agency concentration risk
    "expertise": 0.20,          # NAICS specialization (inverted)
    "trajectory": 0.20,         # Contract value trend
    "market_share": 0.20,       # Market dominance (inverted)
    "recompete_history": 0.15,  # Recompete loss rate
}


# =============================================================================
# Main Analysis Functions
# =============================================================================

def calculate_incumbent_vulnerability(
    db: Session,
    incumbent_uei: str,
    naics_code: Optional[str] = None,
    agency_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculate vulnerability score for an incumbent.

    Higher score (0-100) = more beatable.

    Args:
        db: Database session
        incumbent_uei: Unique Entity Identifier of incumbent
        naics_code: Optional NAICS code to contextualize analysis
        agency_name: Optional agency to contextualize analysis

    Returns:
        Dict with vulnerability_score, level, factors, and recommendation
    """

    # Get incumbent's contract history
    awards = db.query(ContractAward).filter(
        ContractAward.recipient_uei == incumbent_uei
    ).all()

    if not awards:
        # Try by name if UEI doesn't match
        # This is a fallback for data quality issues
        return {
            "incumbent_uei": incumbent_uei,
            "vulnerability_score": 50,
            "level": "Unknown",
            "factors": {},
            "recommendation": "Insufficient data to analyze this incumbent",
            "data_quality": "no_contract_history",
        }

    # Get incumbent name from first award
    incumbent_name = awards[0].recipient_name or "Unknown"

    factors = {}

    # ==========================================================================
    # Factor 1: Agency Concentration Risk (25%)
    # High concentration = vulnerable if that relationship sours
    # ==========================================================================
    concentration_score, concentration_detail = _calculate_concentration_risk(awards)
    factors["concentration"] = {
        "score": concentration_score,
        "weight": WEIGHTS["concentration"],
        "detail": concentration_detail,
    }

    # ==========================================================================
    # Factor 2: NAICS Expertise (20%)
    # Specialist in target NAICS = harder to beat (low vulnerability)
    # Generalist = easier to beat (high vulnerability)
    # ==========================================================================
    expertise_score, expertise_detail = _calculate_naics_expertise(awards, naics_code)
    factors["expertise"] = {
        "score": expertise_score,
        "weight": WEIGHTS["expertise"],
        "detail": expertise_detail,
    }

    # ==========================================================================
    # Factor 3: Contract Value Trajectory (20%)
    # Shrinking portfolio = possible problems = more vulnerable
    # ==========================================================================
    trajectory_score, trajectory_detail = _calculate_value_trajectory(awards)
    factors["trajectory"] = {
        "score": trajectory_score,
        "weight": WEIGHTS["trajectory"],
        "detail": trajectory_detail,
    }

    # ==========================================================================
    # Factor 4: Market Share (20%)
    # Market dominance = hard to beat (low vulnerability)
    # Small player = easier to beat (high vulnerability)
    # ==========================================================================
    market_score, market_detail = _calculate_market_share(db, awards, naics_code)
    factors["market_share"] = {
        "score": market_score,
        "weight": WEIGHTS["market_share"],
        "detail": market_detail,
    }

    # ==========================================================================
    # Factor 5: Recompete Retention Rate (15%)
    # High loss rate = vulnerable
    # ==========================================================================
    recompete_score, recompete_detail = _calculate_recompete_history(db, incumbent_uei, awards)
    factors["recompete_history"] = {
        "score": recompete_score,
        "weight": WEIGHTS["recompete_history"],
        "detail": recompete_detail,
    }

    # ==========================================================================
    # Calculate weighted vulnerability score
    # ==========================================================================
    vulnerability_score = (
        factors["concentration"]["score"] * WEIGHTS["concentration"] +
        factors["expertise"]["score"] * WEIGHTS["expertise"] +
        factors["trajectory"]["score"] * WEIGHTS["trajectory"] +
        factors["market_share"]["score"] * WEIGHTS["market_share"] +
        factors["recompete_history"]["score"] * WEIGHTS["recompete_history"]
    )

    # Clamp to 0-100
    vulnerability_score = max(0, min(100, int(vulnerability_score)))

    # Determine level
    if vulnerability_score >= 60:
        level = "High"
    elif vulnerability_score >= 40:
        level = "Medium"
    else:
        level = "Low"

    # Generate recommendation
    recommendation = _generate_recommendation(factors, vulnerability_score, level, incumbent_name)

    # Get summary stats
    total_awards = len(awards)
    total_value = sum(float(a.base_and_all_options_value or a.total_obligation or 0) for a in awards)

    return {
        "incumbent_name": incumbent_name,
        "incumbent_uei": incumbent_uei,
        "vulnerability_score": vulnerability_score,
        "level": level,
        "factors": factors,
        "recommendation": recommendation,
        "summary": {
            "total_contracts": total_awards,
            "total_value": total_value,
            "analysis_context": {
                "naics_code": naics_code,
                "agency": agency_name,
            },
        },
        "algorithm_version": "vulnerability_v1",
        "calculated_at": datetime.utcnow().isoformat(),
    }


# =============================================================================
# Factor Calculation Functions
# =============================================================================

def _calculate_concentration_risk(awards: List[ContractAward]) -> Tuple[float, str]:
    """
    Calculate agency concentration risk.
    High concentration = vulnerable (score closer to 100).
    """
    if not awards:
        return 50, "No contract data"

    # Count contracts by agency
    agency_counts = {}
    agency_values = {}

    for award in awards:
        agency = award.awarding_agency_name or "Unknown"
        agency_counts[agency] = agency_counts.get(agency, 0) + 1
        value = float(award.base_and_all_options_value or award.total_obligation or 0)
        agency_values[agency] = agency_values.get(agency, 0) + value

    # Calculate concentration by value (more accurate than count)
    total_value = sum(agency_values.values())
    if total_value == 0:
        # Fall back to count-based
        total = sum(agency_counts.values())
        top_agency = max(agency_counts.keys(), key=lambda x: agency_counts[x])
        top_pct = (agency_counts[top_agency] / total * 100) if total > 0 else 0
    else:
        top_agency = max(agency_values.keys(), key=lambda x: agency_values[x])
        top_pct = (agency_values[top_agency] / total_value * 100)

    # High concentration (>70%) = high vulnerability score
    # Low concentration (<30%) = low vulnerability score
    if top_pct >= 80:
        score = 90
        detail = f"Highly concentrated: {top_pct:.0f}% with {top_agency}"
    elif top_pct >= 60:
        score = 70
        detail = f"Concentrated: {top_pct:.0f}% with {top_agency}"
    elif top_pct >= 40:
        score = 50
        detail = f"Moderately diversified: {top_pct:.0f}% with {top_agency}"
    else:
        score = 30
        detail = f"Well diversified: only {top_pct:.0f}% with largest agency ({top_agency})"

    return score, detail


def _calculate_naics_expertise(
    awards: List[ContractAward],
    target_naics: Optional[str]
) -> Tuple[float, str]:
    """
    Calculate NAICS expertise score.
    Specialist in target NAICS = LOW vulnerability (hard to beat)
    Generalist = HIGH vulnerability (easier to beat)
    """
    if not awards:
        return 50, "No contract data"

    # Count contracts by NAICS
    naics_counts = {}
    naics_values = {}

    for award in awards:
        naics = award.naics_code or "Unknown"
        naics_counts[naics] = naics_counts.get(naics, 0) + 1
        value = float(award.base_and_all_options_value or award.total_obligation or 0)
        naics_values[naics] = naics_values.get(naics, 0) + value

    total_contracts = sum(naics_counts.values())
    total_value = sum(naics_values.values())

    # If target NAICS specified, calculate expertise in that specific area
    if target_naics and target_naics in naics_counts:
        # How much of their work is in target NAICS?
        if total_value > 0:
            target_pct = (naics_values.get(target_naics, 0) / total_value * 100)
        else:
            target_pct = (naics_counts.get(target_naics, 0) / total_contracts * 100) if total_contracts > 0 else 0

        # HIGH percentage in target NAICS = specialist = LOW vulnerability
        if target_pct >= 50:
            score = 20  # Hard to beat - specialist
            detail = f"Specialist: {target_pct:.0f}% of work in {target_naics}"
        elif target_pct >= 25:
            score = 40
            detail = f"Experienced: {target_pct:.0f}% of work in {target_naics}"
        elif target_pct >= 10:
            score = 60
            detail = f"Some experience: {target_pct:.0f}% in {target_naics}"
        else:
            score = 80  # Easy to beat - not specialized here
            detail = f"Generalist: only {target_pct:.0f}% in {target_naics}"
    else:
        # No target NAICS - just look at overall diversity
        unique_naics = len([n for n in naics_counts.keys() if n != "Unknown"])

        if unique_naics <= 2:
            score = 25  # Very focused = hard to beat
            detail = f"Highly focused: works in only {unique_naics} NAICS codes"
        elif unique_naics <= 5:
            score = 40
            detail = f"Focused: works in {unique_naics} NAICS codes"
        elif unique_naics <= 10:
            score = 60
            detail = f"Diversified: works in {unique_naics} NAICS codes"
        else:
            score = 75  # Very diversified = potentially spread thin
            detail = f"Highly diversified: works in {unique_naics}+ NAICS codes"

    return score, detail


def _calculate_value_trajectory(awards: List[ContractAward]) -> Tuple[float, str]:
    """
    Calculate contract value trajectory over last 24 months.
    Declining = HIGH vulnerability
    Growing = LOW vulnerability
    """
    if not awards:
        return 50, "No contract data"

    today = date.today()
    cutoff_12mo = today - timedelta(days=365)
    cutoff_24mo = today - timedelta(days=730)

    # Calculate value in each period
    value_12mo = 0
    value_prior = 0  # 12-24 months ago

    for award in awards:
        award_date = award.award_date or award.period_of_performance_start
        if not award_date:
            continue

        value = float(award.base_and_all_options_value or award.total_obligation or 0)

        if award_date >= cutoff_12mo:
            value_12mo += value
        elif award_date >= cutoff_24mo:
            value_prior += value

    # Calculate trend
    if value_prior == 0 and value_12mo == 0:
        return 50, "Insufficient timeline data"

    if value_prior == 0:
        # New contractor - use neutral score
        return 50, f"New activity: ${value_12mo:,.0f} in last 12mo"

    change_pct = ((value_12mo - value_prior) / value_prior) * 100

    # Declining = vulnerable
    if change_pct <= -30:
        score = 80
        detail = f"Declining rapidly: {change_pct:+.0f}% over 24mo"
    elif change_pct <= -10:
        score = 65
        detail = f"Declining: {change_pct:+.0f}% over 24mo"
    elif change_pct <= 10:
        score = 50
        detail = f"Stable: {change_pct:+.0f}% over 24mo"
    elif change_pct <= 30:
        score = 35
        detail = f"Growing: {change_pct:+.0f}% over 24mo"
    else:
        score = 20
        detail = f"Growing rapidly: {change_pct:+.0f}% over 24mo"

    return score, detail


def _calculate_market_share(
    db: Session,
    awards: List[ContractAward],
    naics_code: Optional[str]
) -> Tuple[float, str]:
    """
    Calculate market share in target NAICS.
    High market share = LOW vulnerability (dominant player)
    Low market share = HIGH vulnerability (small player)
    """
    if not naics_code:
        return 50, "No NAICS context provided"

    # Get incumbent's value in this NAICS
    incumbent_value = sum(
        float(a.base_and_all_options_value or a.total_obligation or 0)
        for a in awards
        if a.naics_code == naics_code
    )

    if incumbent_value == 0:
        return 70, f"No contracts in NAICS {naics_code}"

    # Get total market value in this NAICS (last 2 years)
    cutoff = date.today() - timedelta(days=730)

    market_total = db.query(
        func.sum(ContractAward.base_and_all_options_value).label("total")
    ).filter(
        ContractAward.naics_code == naics_code,
        ContractAward.award_date >= cutoff,
    ).scalar() or 0

    market_total = float(market_total)

    if market_total == 0:
        return 50, "Insufficient market data"

    market_share_pct = (incumbent_value / market_total) * 100

    # High market share = hard to beat
    if market_share_pct >= 20:
        score = 15
        detail = f"Market leader: {market_share_pct:.1f}% share in {naics_code}"
    elif market_share_pct >= 10:
        score = 30
        detail = f"Major player: {market_share_pct:.1f}% share in {naics_code}"
    elif market_share_pct >= 5:
        score = 50
        detail = f"Established player: {market_share_pct:.1f}% share in {naics_code}"
    elif market_share_pct >= 1:
        score = 70
        detail = f"Small player: {market_share_pct:.1f}% share in {naics_code}"
    else:
        score = 85
        detail = f"Minor player: {market_share_pct:.1f}% share in {naics_code}"

    return score, detail


def _calculate_recompete_history(
    db: Session,
    incumbent_uei: str,
    awards: List[ContractAward]
) -> Tuple[float, str]:
    """
    Calculate recompete retention rate.
    High loss rate = HIGH vulnerability
    """
    if not awards:
        return 50, "No contract data"

    # Look for PIIDs that appear multiple times (recompetes)
    # If incumbent won the earlier one but not the later one, they lost the recompete

    # Group awards by base PIID
    piid_groups = {}
    for award in awards:
        if not award.piid:
            continue
        # Get base PIID (strip modification numbers)
        base_piid = award.piid.split("-")[0].split("_")[0]
        if base_piid not in piid_groups:
            piid_groups[base_piid] = []
        piid_groups[base_piid].append(award)

    # Find contracts with multiple awards (potential recompetes)
    potential_recompetes = [g for g in piid_groups.values() if len(g) >= 2]

    if not potential_recompetes:
        # Check RecompeteOpportunity table for explicit data
        recompete_count = db.query(RecompeteOpportunity).filter(
            RecompeteOpportunity.incumbent_uei == incumbent_uei,
        ).count()

        if recompete_count == 0:
            return 50, "No recompete history available"

        # Have some recompetes but can't calculate loss rate
        return 50, f"{recompete_count} active/upcoming recompetes"

    # For now, estimate based on contract continuity
    # This is a simplified heuristic without full recompete tracking
    total_piids = len(piid_groups)
    expired_piids = 0
    today = date.today()

    for piid, group in piid_groups.items():
        latest = max(group, key=lambda x: x.period_of_performance_end or date.min)
        if latest.period_of_performance_end and latest.period_of_performance_end < today:
            expired_piids += 1

    if expired_piids == 0:
        return 35, f"All {total_piids} contracts still active"

    # Rough estimate: expired contracts might indicate lost recompetes
    # This is imperfect without tracking who won the follow-on
    loss_estimate_pct = (expired_piids / total_piids) * 100 if total_piids > 0 else 0

    if loss_estimate_pct >= 50:
        score = 70
        detail = f"High turnover: {expired_piids}/{total_piids} contracts expired"
    elif loss_estimate_pct >= 25:
        score = 55
        detail = f"Moderate turnover: {expired_piids}/{total_piids} contracts expired"
    else:
        score = 40
        detail = f"Good retention: {expired_piids}/{total_piids} contracts expired"

    return score, detail


def _generate_recommendation(
    factors: Dict,
    score: int,
    level: str,
    incumbent_name: str
) -> str:
    """Generate human-readable recommendation based on vulnerability analysis."""

    key_vulnerabilities = []
    key_strengths = []

    for name, factor in factors.items():
        if factor["score"] >= 70:
            key_vulnerabilities.append(name.replace("_", " "))
        elif factor["score"] <= 30:
            key_strengths.append(name.replace("_", " "))

    if level == "High":
        if key_vulnerabilities:
            return f"High vulnerability - weaknesses include: {', '.join(key_vulnerabilities)}. Strong competitive opportunity."
        return "High vulnerability - multiple factors suggest this incumbent is beatable."

    elif level == "Medium":
        parts = []
        if key_vulnerabilities:
            parts.append(f"vulnerabilities: {', '.join(key_vulnerabilities)}")
        if key_strengths:
            parts.append(f"strengths: {', '.join(key_strengths)}")
        detail = "; ".join(parts) if parts else "mixed factors"
        return f"Medium difficulty - {detail}. Competitive with strong proposal."

    else:  # Low vulnerability
        if key_strengths:
            return f"Low vulnerability - strong incumbent with: {', '.join(key_strengths)}. Consider teaming or differentiation strategy."
        return f"Low vulnerability - {incumbent_name} appears to be a strong incumbent. Carefully evaluate before competing."


# =============================================================================
# Public API Functions
# =============================================================================

def get_incumbent_vulnerability(
    db: Session,
    uei: Optional[str] = None,
    company_name: Optional[str] = None,
    naics_code: Optional[str] = None,
    agency_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Get vulnerability analysis for an incumbent by UEI or company name.

    Args:
        db: Database session
        uei: Unique Entity Identifier (preferred)
        company_name: Company name (fallback if UEI not available)
        naics_code: Optional NAICS code for context
        agency_name: Optional agency for context

    Returns:
        Vulnerability analysis dict or None if not found
    """
    # Try UEI first
    if uei:
        return calculate_incumbent_vulnerability(db, uei, naics_code, agency_name)

    # Fall back to company name search
    if company_name:
        # Find UEI from contract awards
        award = db.query(ContractAward).filter(
            ContractAward.recipient_name.ilike(f"%{company_name}%"),
            ContractAward.recipient_uei.isnot(None),
        ).first()

        if award and award.recipient_uei:
            return calculate_incumbent_vulnerability(
                db, award.recipient_uei, naics_code, agency_name
            )

    return None


def get_vulnerability_for_recompete(
    db: Session,
    recompete_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Get vulnerability analysis for a recompete opportunity's incumbent.

    Args:
        db: Database session
        recompete_id: ID of the recompete opportunity

    Returns:
        Vulnerability analysis contextualized to the recompete
    """
    from uuid import UUID

    # Get recompete
    recompete = db.query(RecompeteOpportunity).filter(
        RecompeteOpportunity.id == UUID(recompete_id)
    ).first()

    if not recompete:
        return None

    if not recompete.incumbent_uei:
        # Try to find by name
        if recompete.incumbent_name:
            return get_incumbent_vulnerability(
                db,
                company_name=recompete.incumbent_name,
                naics_code=recompete.naics_code,
                agency_name=recompete.awarding_agency_name,
            )
        return {
            "error": "No incumbent information available",
            "recompete_id": str(recompete_id),
        }

    # Get vulnerability analysis with recompete context
    result = calculate_incumbent_vulnerability(
        db,
        recompete.incumbent_uei,
        recompete.naics_code,
        recompete.awarding_agency_name,
    )

    # Add recompete context
    result["recompete"] = {
        "id": str(recompete.id),
        "piid": recompete.piid,
        "expires": recompete.period_of_performance_end.isoformat() if recompete.period_of_performance_end else None,
        "total_value": float(recompete.total_value) if recompete.total_value else None,
        "agency": recompete.awarding_agency_name,
        "naics_code": recompete.naics_code,
    }

    return result
