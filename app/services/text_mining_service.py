"""
Text Mining Service for BidKing

Extracts structured data from opportunity descriptions and attachments:
- Dollar amounts (contract values)
- Clearance requirements
- Keywords for capability matching
"""

import re
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal


# Clearance level patterns
CLEARANCE_PATTERNS = {
    "TS/SCI": [
        r"\bTS/SCI\b",
        r"\bTop\s*Secret/SCI\b",
        r"\bTS\s*/\s*SCI\b",
        r"\bSCI\s+access\b",
        r"\bSCI\s+eligible\b",
    ],
    "Top Secret": [
        r"\bTop\s*Secret\b",
        r"\bTS\s+clearance\b",
        r"\bTS\s+required\b",
    ],
    "Secret": [
        r"\bSecret\s+clearance\b",
        r"\bSecret\s+required\b",
        r"\bSecret\s+level\b",
        r"\brequire[sd]?\s+Secret\b",
    ],
    "Confidential": [
        r"\bConfidential\s+clearance\b",
        r"\bConfidential\s+required\b",
    ],
    "Public Trust": [
        r"\bPublic\s+Trust\b",
        r"\bMBI\b",  # Moderate Background Investigation
        r"\bNACI\b",  # National Agency Check with Inquiries
        r"\bsuitability\s+determination\b",
    ],
}

# Dollar amount patterns
DOLLAR_PATTERNS = [
    # $1,234,567.89 or $1234567
    r'\$\s*[\d,]+(?:\.\d{2})?',
    # $1.5M, $500K, $2.3B
    r'\$\s*[\d.]+\s*[KMBkmb](?:illion)?',
    # 1.5 million dollars, 500 thousand
    r'[\d.]+\s*(?:million|billion|thousand)\s*(?:dollars?)?',
    # ceiling of $X, NTE $X, not to exceed $X
    r'(?:ceiling|NTE|not\s+to\s+exceed|maximum|up\s+to|estimated|approximately|approx)\s*(?:of\s*)?\$[\d,]+(?:\.\d{2})?(?:\s*[KMBkmb](?:illion)?)?',
]

# Keywords to ignore (too common)
STOP_WORDS = {
    'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her',
    'was', 'one', 'our', 'out', 'has', 'have', 'been', 'were', 'being', 'their',
    'said', 'each', 'which', 'she', 'how', 'will', 'may', 'about', 'after',
    'government', 'contractor', 'contract', 'shall', 'must', 'should', 'would',
    'services', 'service', 'provide', 'support', 'federal', 'agency', 'work',
    'required', 'requirements', 'including', 'include', 'includes', 'this',
    'that', 'with', 'from', 'they', 'what', 'there', 'when', 'make', 'like',
}

# Technical keywords worth matching (weighted higher)
TECHNICAL_KEYWORDS = {
    # Programming languages
    'python', 'java', 'javascript', 'typescript', 'golang', 'rust', 'c++', 'c#',
    'ruby', 'php', 'scala', 'kotlin', 'swift', 'react', 'angular', 'vue',
    # Cloud/Infrastructure
    'aws', 'azure', 'gcp', 'kubernetes', 'docker', 'terraform', 'ansible',
    'cloudformation', 'jenkins', 'gitlab', 'github', 'devops', 'cicd', 'ci/cd',
    # Data/Analytics
    'machine learning', 'ml', 'artificial intelligence', 'ai', 'data science',
    'data engineering', 'etl', 'data lake', 'data warehouse', 'snowflake',
    'databricks', 'spark', 'hadoop', 'tableau', 'power bi', 'powerbi',
    'predictive', 'analytics', 'business intelligence', 'bi',
    # Databases
    'postgresql', 'mysql', 'mongodb', 'redis', 'elasticsearch', 'oracle',
    'sql server', 'dynamodb', 'cassandra', 'neo4j',
    # Security
    'cybersecurity', 'security', 'siem', 'soc', 'penetration testing',
    'vulnerability', 'compliance', 'fisma', 'fedramp', 'nist', 'rmf',
    # Methodologies
    'agile', 'scrum', 'kanban', 'devops', 'devsecops', 'waterfall', 'safe',
    # Certifications
    'pmp', 'cissp', 'cism', 'aws certified', 'azure certified', 'comptia',
    'itil', 'cmmi', 'iso 27001', 'iso27001', 'soc 2', 'soc2',
}


def extract_clearance_level(text: str) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Extract the highest clearance level mentioned in text.

    Returns:
        Tuple of (clearance_level, breakdown)
        clearance_level: "TS/SCI", "Top Secret", "Secret", "Confidential", "Public Trust", or None
        breakdown: Details about what was found
    """
    if not text:
        return None, {"reason": "no_text"}

    text_upper = text.upper()
    found_levels = []

    # Check from highest to lowest clearance
    clearance_hierarchy = ["TS/SCI", "Top Secret", "Secret", "Confidential", "Public Trust"]

    for level in clearance_hierarchy:
        patterns = CLEARANCE_PATTERNS.get(level, [])
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                found_levels.append(level)
                break  # Found this level, move to next

    if not found_levels:
        return None, {"reason": "no_clearance_found"}

    # Return highest level found
    highest = found_levels[0]  # Already sorted by hierarchy
    return highest, {
        "reason": "clearance_found",
        "highest_level": highest,
        "all_levels_found": found_levels,
    }


def extract_dollar_amounts(text: str) -> Tuple[Optional[Decimal], Optional[Decimal], Dict[str, Any]]:
    """
    Extract dollar amounts from text.

    Returns:
        Tuple of (min_value, max_value, breakdown)
        min_value: Smallest dollar amount found (or None)
        max_value: Largest dollar amount found (or None)
        breakdown: Details about extraction
    """
    if not text:
        return None, None, {"reason": "no_text"}

    amounts = []
    raw_matches = []

    for pattern in DOLLAR_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        raw_matches.extend(matches)

    for match in raw_matches:
        try:
            value = _parse_dollar_amount(match)
            if value and value > 0:
                amounts.append(value)
        except:
            continue

    if not amounts:
        return None, None, {"reason": "no_amounts_found", "raw_matches": raw_matches[:5]}

    # Filter out unrealistic amounts (less than $1K or more than $10B)
    amounts = [a for a in amounts if 1000 <= a <= 10_000_000_000]

    if not amounts:
        return None, None, {"reason": "amounts_filtered", "raw_matches": raw_matches[:5]}

    min_val = Decimal(str(min(amounts)))
    max_val = Decimal(str(max(amounts)))

    return min_val, max_val, {
        "reason": "amounts_found",
        "min": float(min_val),
        "max": float(max_val),
        "count": len(amounts),
        "all_amounts": sorted([float(a) for a in amounts])[:10],
    }


def _parse_dollar_amount(text: str) -> Optional[float]:
    """Parse a dollar amount string into a float."""
    if not text:
        return None

    # Remove $ and whitespace
    text = text.replace('$', '').replace(',', '').strip()

    # Handle K/M/B suffixes
    multiplier = 1
    text_upper = text.upper()

    if 'BILLION' in text_upper or text_upper.endswith('B'):
        multiplier = 1_000_000_000
        text = re.sub(r'[Bb](?:illion)?', '', text)
    elif 'MILLION' in text_upper or text_upper.endswith('M'):
        multiplier = 1_000_000
        text = re.sub(r'[Mm](?:illion)?', '', text)
    elif 'THOUSAND' in text_upper or text_upper.endswith('K'):
        multiplier = 1_000
        text = re.sub(r'[Kk](?:housand)?', '', text)

    # Extract the number
    match = re.search(r'[\d.]+', text)
    if match:
        try:
            return float(match.group()) * multiplier
        except:
            return None

    return None


def extract_keywords(text: str, min_length: int = 3) -> Tuple[List[str], Dict[str, Any]]:
    """
    Extract meaningful keywords from text.

    Returns:
        Tuple of (keywords, breakdown)
        keywords: List of extracted keywords (lowercase)
        breakdown: Details about extraction
    """
    if not text:
        return [], {"reason": "no_text"}

    # Convert to lowercase
    text_lower = text.lower()

    # Find technical keywords first (higher value)
    technical_found = []
    for keyword in TECHNICAL_KEYWORDS:
        if keyword in text_lower:
            technical_found.append(keyword)

    # Extract other words (2+ occurrences, not stop words)
    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9+#.-]*[a-zA-Z0-9]\b', text_lower)

    # Count word frequency
    word_counts = {}
    for word in words:
        if len(word) >= min_length and word not in STOP_WORDS:
            word_counts[word] = word_counts.get(word, 0) + 1

    # Get words that appear 2+ times
    frequent_words = [w for w, c in word_counts.items() if c >= 2]

    # Combine and deduplicate
    all_keywords = list(set(technical_found + frequent_words))

    # Sort: technical keywords first, then by frequency
    def sort_key(kw):
        is_technical = kw in TECHNICAL_KEYWORDS
        frequency = word_counts.get(kw, 0)
        return (0 if is_technical else 1, -frequency)

    all_keywords.sort(key=sort_key)

    return all_keywords[:50], {  # Limit to 50 keywords
        "reason": "keywords_extracted",
        "technical_count": len(technical_found),
        "frequent_count": len(frequent_words),
        "total": len(all_keywords),
    }


def calculate_keyword_match_score(
    opportunity_keywords: List[str],
    user_keywords: List[str],
    user_capability_text: Optional[str] = None
) -> Tuple[int, Dict[str, Any]]:
    """
    Calculate keyword match score between opportunity and user profile.

    Args:
        opportunity_keywords: Keywords from opportunity + attachments
        user_keywords: Keywords from user's capability statement
        user_capability_text: Full capability statement text for fuzzy matching

    Returns:
        Tuple of (score 0-100, breakdown)
    """
    if not opportunity_keywords:
        return 50, {"reason": "no_opportunity_keywords"}

    if not user_keywords and not user_capability_text:
        return 50, {"reason": "no_user_keywords"}

    # Normalize keywords
    opp_keywords_set = set(k.lower() for k in opportunity_keywords)
    user_keywords_set = set(k.lower() for k in (user_keywords or []))

    # Direct keyword matches
    matches = opp_keywords_set & user_keywords_set

    # Technical keyword bonus
    technical_matches = matches & TECHNICAL_KEYWORDS

    # Calculate score
    if len(opp_keywords_set) == 0:
        match_ratio = 0
    else:
        match_ratio = len(matches) / min(len(opp_keywords_set), len(user_keywords_set)) if user_keywords_set else 0

    # Base score from matches (0-70 points)
    base_score = int(match_ratio * 70)

    # Technical keyword bonus (0-30 points)
    tech_bonus = min(len(technical_matches) * 10, 30)

    score = min(base_score + tech_bonus, 100)

    return score, {
        "reason": "keyword_match_calculated",
        "total_matches": len(matches),
        "matched_keywords": list(matches)[:20],
        "technical_matches": list(technical_matches),
        "match_ratio": round(match_ratio, 2),
        "base_score": base_score,
        "tech_bonus": tech_bonus,
    }


def extract_all_from_opportunity(
    description: str,
    attachment_texts: List[str]
) -> Dict[str, Any]:
    """
    Extract all structured data from an opportunity's text content.

    Args:
        description: Opportunity description text
        attachment_texts: List of extracted text from attachments

    Returns:
        Dict containing all extracted data
    """
    # Combine all text
    all_text = description or ""
    for att_text in (attachment_texts or []):
        if att_text:
            all_text += "\n\n" + att_text

    # Extract each data type
    clearance_level, clearance_breakdown = extract_clearance_level(all_text)
    min_value, max_value, value_breakdown = extract_dollar_amounts(all_text)
    keywords, keyword_breakdown = extract_keywords(all_text)

    return {
        "clearance_level": clearance_level,
        "clearance_breakdown": clearance_breakdown,
        "estimated_min_value": min_value,
        "estimated_max_value": max_value,
        "value_breakdown": value_breakdown,
        "keywords": keywords,
        "keyword_breakdown": keyword_breakdown,
        "text_length": len(all_text),
        "has_attachments": bool(attachment_texts),
    }
