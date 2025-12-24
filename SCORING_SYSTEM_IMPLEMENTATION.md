# BidKing Opportunity Scoring System Implementation

## Overview
A personalized opportunity scoring system that helps users identify the best-fit federal contracting opportunities based on their company profile, capabilities, certifications, and past performance.

**Start Date**: December 13, 2025
**Status**: Phase 1 In Progress - Database, API, and Onboarding UI Complete

---

## Table of Contents
1. [Feature Summary](#feature-summary)
2. [User Journey](#user-journey)
3. [Database Schema](#database-schema)
4. [API Endpoints](#api-endpoints)
5. [Frontend Components](#frontend-components)
6. [Scoring Algorithm](#scoring-algorithm)
7. [Implementation Phases](#implementation-phases)
8. [Progress Tracking](#progress-tracking)

---

## Feature Summary

### Goals
1. **Personalized Scoring**: Every opportunity gets a 0-100 fit score based on user's profile
2. **Onboarding Flow**: Guide new users to complete their profile immediately after signup
3. **Past Performance Tracking**: Let users log past contracts to improve scoring accuracy
4. **Capability Statement Analysis**: Upload and analyze capability statements for semantic matching
5. **Learning Loop**: Track bid decisions to improve scoring over time

### Scoring Dimensions

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Capability Match | 25% | NAICS alignment, skills/tech overlap, semantic similarity |
| Eligibility | 20% | Set-aside qualification, certifications, clearance match |
| Scale Fit | 15% | Contract size vs company capacity (inferred from signals) |
| Win Probability | 20% | Incumbent analysis, agency history, competition level |
| Strategic Fit | 10% | Contract type preference, agency targets, growth potential |
| Timeline | 10% | Deadline feasibility, current pipeline load |

### Additional Scoring Elements (Added Dec 13, 2025)

#### Scale Fit - Inferring Contract Size
Since SAM.gov opportunities rarely include dollar values, we infer contract scale from text signals and compare against user's demonstrated capacity.

#### Security Clearance Match
Critical eligibility filter - many federal contracts require specific clearance levels that users must hold.

#### Contract Type Preference
Different contract types (FFP, T&M, Cost-Plus) have different risk profiles that users may prefer or avoid.

---

## Scalability & Concurrency Architecture

### Design Principles
The scoring system must efficiently support concurrent users without redundant processing.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           REQUEST FLOW                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         API LAYER (FastAPI)                                  │
│  • Authentication (Supabase JWT)                                            │
│  • Rate limiting (100 requests/minute per user)                             │
│  • Request validation                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
            │   Profile   │ │   Scoring   │ │  Metadata   │
            │   Service   │ │   Service   │ │   Service   │
            └─────────────┘ └─────────────┘ └─────────────┘
                    │               │               │
                    └───────────────┼───────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CACHING LAYER                                       │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Layer 1: Opportunity Metadata (Permanent until opportunity changes)  │   │
│  │ • Estimated scale (min/max/likely)                                   │   │
│  │ • Required clearance level                                           │   │
│  │ • Contract type                                                      │   │
│  │ • Extracted keywords                                                 │   │
│  │ • Complexity signals                                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Layer 2: User Scores (TTL-based, invalidate on profile change)       │   │
│  │ • Cached in opportunity_scores table                                 │   │
│  │ • expires_at timestamp for automatic refresh                         │   │
│  │ • Invalidate when user updates profile                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Layer 3: In-Memory (Per-request)                                     │   │
│  │ • User profile loaded once per request                               │   │
│  │ • Opportunity data for current view                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATA LAYER                                          │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │  User Data       │  │  Opportunities   │  │  Cached Scores   │          │
│  │  • Profile       │  │  • SAM.gov       │  │  • Per user      │          │
│  │  • NAICS         │  │  • Recompetes    │  │  • TTL-based     │          │
│  │  • Certs         │  │  • Metadata      │  │  • Invalidation  │          │
│  │  • Past Perf     │  │    (pre-processed│  │    tracking      │          │
│  │  • Clearances    │  │     for speed)   │  │                  │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     BACKGROUND JOB QUEUE                                     │
│                                                                              │
│  • Opportunity metadata extraction (on sync)                                │
│  • Capability statement processing (on upload)                              │
│  • Batch score recalculation (on profile update)                            │
│  • USAspending import (on user request)                                     │
│  • Score refresh for expiring entries                                        │
│                                                                              │
│  Implementation: Python asyncio + database-backed job queue                 │
│  (Can upgrade to Celery/Redis if scale demands)                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Opportunity Metadata Pre-Processing

To avoid re-parsing opportunity text for every user, we pre-process and cache metadata when opportunities are synced.

```sql
-- Add to existing opportunities/recompetes tables OR create new table
CREATE TABLE opportunity_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id TEXT NOT NULL,
    opportunity_type TEXT NOT NULL,  -- 'sam' or 'recompete'

    -- Scale estimation
    estimated_scale_min DECIMAL,
    estimated_scale_max DECIMAL,
    estimated_scale_likely DECIMAL,
    scale_confidence TEXT,  -- 'high', 'medium', 'low'
    scale_signals TEXT[],   -- Reasons for estimate

    -- Security clearance
    required_clearance TEXT,  -- 'none', 'public_trust', 'secret', 'top_secret', 'ts_sci'
    clearance_signals TEXT[], -- Text that indicated requirement

    -- Contract type
    contract_type TEXT,  -- 'ffp', 'time_materials', 'cost_plus', 'idiq', 'bpa', 'unknown'
    contract_type_confidence TEXT,

    -- Extracted keywords for matching
    extracted_keywords TEXT[],
    extracted_technologies TEXT[],

    -- Complexity indicators
    estimated_fte_count INTEGER,
    is_multi_location BOOLEAN DEFAULT false,
    is_enterprise_scale BOOLEAN DEFAULT false,
    requires_certifications TEXT[],  -- 'cmmi', 'iso', 'fedramp', etc.

    -- Processing tracking
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    source_hash TEXT,  -- Hash of source text to detect changes

    UNIQUE(opportunity_id, opportunity_type)
);

CREATE INDEX idx_opp_metadata_lookup ON opportunity_metadata(opportunity_id, opportunity_type);
CREATE INDEX idx_opp_metadata_clearance ON opportunity_metadata(required_clearance);
CREATE INDEX idx_opp_metadata_scale ON opportunity_metadata(estimated_scale_likely);
```

### Score Calculation Strategy

```
WHEN TO CALCULATE SCORES:

1. On-Demand (Lazy)
   - User views opportunity list → Calculate/retrieve scores for visible page
   - User views opportunity detail → Calculate if not cached
   - Pros: No wasted computation
   - Cons: Slight delay on first view

2. Batch (Eager)
   - User updates profile → Queue job to recalculate top N opportunities
   - New opportunities synced → Queue job to calculate for active users
   - Pros: Instant display
   - Cons: More computation, many scores never viewed

3. Hybrid (RECOMMENDED)
   - On-demand for list views with efficient batch queries
   - Pre-calculate on profile update for user's saved/pipeline items
   - Background refresh for expiring scores during low-traffic periods
```

### Score Invalidation Rules

```python
INVALIDATION_TRIGGERS = {
    # User profile changes
    'profile.naics.add': ['capability', 'eligibility'],
    'profile.naics.remove': ['capability', 'eligibility'],
    'profile.certifications.add': ['eligibility'],
    'profile.certifications.remove': ['eligibility'],
    'profile.clearances.change': ['eligibility'],
    'profile.past_performance.add': ['win_probability', 'scale_fit'],
    'profile.past_performance.remove': ['win_probability', 'scale_fit'],
    'profile.preferences.change': ['strategic'],
    'profile.company.employee_count': ['scale_fit'],
    'profile.company.annual_revenue': ['scale_fit'],
    'profile.capability_statement.update': ['capability'],

    # Opportunity changes
    'opportunity.deadline.change': ['timeline'],
    'opportunity.description.change': ['capability', 'scale_fit'],
    'opportunity.set_aside.change': ['eligibility'],
}

# Invalidation approach:
# - On trigger, mark affected scores as expired (set expires_at = NOW())
# - Don't delete - allows showing stale score with "updating..." indicator
# - Background job picks up expired scores and recalculates
# - Or recalculate on next user request (lazy)
```

### Database Indexes for Performance

```sql
-- Fast score lookups by user
CREATE INDEX idx_scores_user_type_score
ON opportunity_scores(company_id, opportunity_type, overall_score DESC);

-- Find expired scores for background refresh
CREATE INDEX idx_scores_expired
ON opportunity_scores(expires_at)
WHERE expires_at IS NOT NULL AND expires_at < NOW();

-- Fast profile lookups
CREATE INDEX idx_company_profiles_user
ON company_profiles(user_id);

-- Fast NAICS matching
CREATE INDEX idx_company_naics_lookup
ON company_naics(company_id, naics_code);

-- Fast past performance by agency (for win probability)
CREATE INDEX idx_past_perf_agency
ON past_performance(company_id, agency_name);

-- Fast past performance by value (for scale fit)
CREATE INDEX idx_past_perf_value
ON past_performance(company_id, contract_value DESC);
```

### API Design for Efficiency

```python
# Batch scoring endpoint - single query for list views
POST /api/v1/scoring/batch
{
    "opportunity_type": "sam",  # or "recompete"
    "opportunity_ids": ["id1", "id2", ...],  # Up to 100
    "include_breakdown": false  # Only include if user expands
}

Response:
{
    "scores": {
        "id1": {"overall": 85, "eligible": true},
        "id2": {"overall": 62, "eligible": true},
        "id3": {"overall": 0, "eligible": false, "reason": "Requires TS/SCI"}
    },
    "cache_status": "partial",  # 'full', 'partial', 'none'
    "calculated_count": 45,     # How many were calculated fresh
    "cached_count": 55          # How many came from cache
}

# List endpoint with embedded scores
GET /api/v1/opportunities?page=1&page_size=20&include_scores=true

Response includes scores inline - one query instead of N+1
```

### Connection Pooling & Rate Limits

```python
# Database connection pool (Supabase handles this, but document settings)
POOL_SIZE = 20              # Concurrent connections
POOL_OVERFLOW = 10          # Burst capacity
POOL_TIMEOUT = 30           # Seconds to wait for connection

# API rate limits
RATE_LIMITS = {
    'scoring.single': '60/minute',      # Individual score requests
    'scoring.batch': '20/minute',       # Batch score requests (up to 100 each)
    'scoring.refresh': '5/hour',        # Full profile refresh
    'profile.update': '30/minute',      # Profile updates
    'capability.upload': '10/hour',     # Capability statement uploads
}
```

---

## Scale Fit Scoring (Contract Size Inference)

### The Problem
SAM.gov opportunities rarely include dollar values. A $50K micro-purchase and a $500M enterprise contract can look similar in the listing. We need to infer scale from text signals.

### Scale Inference Algorithm

```python
# app/services/scale_estimator.py

import re
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

class ContractScaleEstimator:
    """
    Infer contract scale from opportunity text when no dollar value provided.
    """

    # Keywords indicating large scale
    ENTERPRISE_KEYWORDS = [
        'enterprise', 'agency-wide', 'department-wide', 'nationwide',
        'global', 'transformation', 'modernization', 'full lifecycle',
        'end-to-end', 'comprehensive', 'integrated', 'centralized'
    ]

    # Keywords indicating small scale
    SMALL_KEYWORDS = [
        'sources sought', 'rfi', 'request for information', 'market research',
        'study', 'assessment', 'analysis', 'one-time', 'single', 'pilot',
        'prototype', 'proof of concept', 'limited', 'minor'
    ]

    # Contract vehicles typically with large ceilings
    LARGE_VEHICLE_KEYWORDS = [
        'idiq', 'indefinite delivery', 'indefinite quantity',
        'bpa', 'blanket purchase', 'mac', 'multiple award',
        'gwac', 'governmentwide'
    ]

    def estimate_scale(self, opportunity: dict) -> dict:
        """
        Estimate contract scale from text signals.

        Returns:
            {
                'min': Decimal,
                'max': Decimal,
                'likely': Decimal,
                'confidence': 'high' | 'medium' | 'low',
                'signals': List[str],
                'is_enterprise': bool,
                'estimated_fte': Optional[int]
            }
        """
        title = (opportunity.get('title') or '').lower()
        description = (opportunity.get('description') or '').lower()
        full_text = f"{title} {description}"

        # Start with base estimate
        result = {
            'min': Decimal('50000'),
            'max': Decimal('500000'),
            'likely': Decimal('150000'),
            'confidence': 'low',
            'signals': [],
            'is_enterprise': False,
            'estimated_fte': None
        }

        # === EXPLICIT DOLLAR AMOUNTS (highest confidence) ===
        dollar_match = self._extract_dollar_amounts(full_text)
        if dollar_match:
            result['min'] = dollar_match['min']
            result['max'] = dollar_match['max']
            result['likely'] = dollar_match['likely']
            result['confidence'] = 'high'
            result['signals'].append(f"Explicit value: ${dollar_match['likely']:,.0f}")
            return result

        # === FTE/PERSONNEL COUNT (high confidence) ===
        fte_count = self._extract_fte_count(full_text)
        if fte_count:
            pop_years = self._extract_pop_years(opportunity) or 1
            annual_labor = fte_count * 175000  # ~$175K fully loaded per FTE
            result['min'] = Decimal(str(annual_labor * 0.8))
            result['max'] = Decimal(str(annual_labor * pop_years * 1.5))
            result['likely'] = Decimal(str(annual_labor * pop_years))
            result['confidence'] = 'high'
            result['estimated_fte'] = fte_count
            result['signals'].append(f"Mentions ~{fte_count} FTEs")

        # === ENTERPRISE SCALE KEYWORDS ===
        enterprise_matches = [kw for kw in self.ENTERPRISE_KEYWORDS if kw in full_text]
        if enterprise_matches:
            result['min'] = max(result['min'], Decimal('5000000'))
            result['max'] = max(result['max'], Decimal('100000000'))
            result['likely'] = max(result['likely'], Decimal('20000000'))
            result['confidence'] = 'medium' if result['confidence'] == 'low' else result['confidence']
            result['is_enterprise'] = True
            result['signals'].append(f"Enterprise keywords: {', '.join(enterprise_matches[:3])}")

        # === LARGE VEHICLE TYPES ===
        vehicle_matches = [kw for kw in self.LARGE_VEHICLE_KEYWORDS if kw in full_text]
        if vehicle_matches:
            result['min'] = max(result['min'], Decimal('2000000'))
            result['max'] = max(result['max'], Decimal('50000000'))
            result['signals'].append(f"Contract vehicle: {vehicle_matches[0].upper()}")

        # === SMALL SCALE KEYWORDS ===
        small_matches = [kw for kw in self.SMALL_KEYWORDS if kw in full_text]
        if small_matches and not enterprise_matches:
            result['max'] = min(result['max'], Decimal('500000'))
            result['likely'] = min(result['likely'], Decimal('150000'))
            result['signals'].append(f"Small-scale indicators: {', '.join(small_matches[:2])}")

        # === PERIOD OF PERFORMANCE ===
        pop_years = self._extract_pop_years(opportunity)
        if pop_years:
            if pop_years >= 5:
                result['min'] = max(result['min'], Decimal('1000000'))
                result['likely'] = result['likely'] * Decimal('1.5')
                result['signals'].append(f"{pop_years}-year period suggests sustained effort")
            elif pop_years <= 1:
                result['max'] = min(result['max'], Decimal('1000000'))
                result['signals'].append("Short period suggests limited scope")

        # === MULTI-LOCATION ===
        if 'multiple locations' in full_text or 'nationwide' in full_text:
            result['likely'] = result['likely'] * Decimal('1.5')
            result['signals'].append("Multiple locations increases scope")

        # === SET-ASIDE ADJUSTMENTS ===
        set_aside = opportunity.get('set_aside_type', '').lower()
        if '8(a)' in set_aside or '8a' in set_aside:
            if 'sole source' in full_text:
                result['max'] = min(result['max'], Decimal('4500000'))
                result['signals'].append("8(a) sole source limit: $4.5M")
        if 'small business' in set_aside:
            result['likely'] = min(result['likely'], Decimal('5000000'))
            result['signals'].append("Small business set-aside - typically under $10M")

        # === MICRO-PURCHASE / SAP ===
        if 'micro-purchase' in full_text:
            result['max'] = Decimal('10000')
            result['likely'] = Decimal('5000')
            result['confidence'] = 'high'
            result['signals'].append("Micro-purchase threshold")
        elif 'simplified acquisition' in full_text:
            result['max'] = min(result['max'], Decimal('250000'))
            result['likely'] = min(result['likely'], Decimal('100000'))
            result['confidence'] = 'medium'
            result['signals'].append("Simplified acquisition threshold")

        return result

    def _extract_dollar_amounts(self, text: str) -> Optional[dict]:
        """Extract explicit dollar amounts from text."""
        amounts = []

        # Match: $5M, $5 million, $5,000,000, $5.5M
        patterns = [
            r'\$\s*([\d,.]+)\s*(?:million|mil|m)\b',
            r'\$\s*([\d,.]+)\s*(?:billion|bil|b)\b',
            r'\$\s*([\d,]+(?:,\d{3})+)',
            r'\$\s*([\d,.]+)\s*(?:thousand|k)\b',
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    value_str = match.group(1).replace(',', '')
                    value = float(value_str)

                    match_text = match.group(0).lower()
                    if 'billion' in match_text or match_text.endswith('b'):
                        value *= 1_000_000_000
                    elif 'million' in match_text or match_text.endswith('m'):
                        value *= 1_000_000
                    elif 'thousand' in match_text or match_text.endswith('k'):
                        value *= 1_000

                    if 1000 <= value <= 100_000_000_000:  # Sanity check
                        amounts.append(Decimal(str(value)))
                except:
                    continue

        if amounts:
            return {
                'min': min(amounts),
                'max': max(amounts),
                'likely': sum(amounts) / len(amounts)
            }
        return None

    def _extract_fte_count(self, text: str) -> Optional[int]:
        """Extract FTE/personnel count from text."""
        patterns = [
            r'(\d+)\s*(?:fte|full.time)',
            r'(\d+)\s*(?:contractor|personnel|staff|employees)',
            r'team of\s*(\d+)',
            r'(\d+)\s*person team',
            r'approximately\s*(\d+)\s*(?:staff|personnel)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                count = int(match.group(1))
                if 1 <= count <= 5000:  # Sanity check
                    return count
        return None

    def _extract_pop_years(self, opportunity: dict) -> Optional[int]:
        """Extract period of performance length in years."""
        # Try to parse from dates if available
        start = opportunity.get('pop_start_date') or opportunity.get('period_of_performance_start')
        end = opportunity.get('pop_end_date') or opportunity.get('period_of_performance_end')

        if start and end:
            try:
                from datetime import datetime
                if isinstance(start, str):
                    start = datetime.fromisoformat(start.replace('Z', '+00:00'))
                if isinstance(end, str):
                    end = datetime.fromisoformat(end.replace('Z', '+00:00'))
                years = (end - start).days / 365
                return max(1, round(years))
            except:
                pass

        # Try to extract from text
        text = (opportunity.get('title', '') + ' ' + opportunity.get('description', '')).lower()

        patterns = [
            r'(\d+)\s*(?:year|yr)',
            r'(\d+)\s*month',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = int(match.group(1))
                if 'month' in pattern:
                    return max(1, round(value / 12))
                return value

        return None
```

### Scale Fit Comparison

```python
def calculate_scale_fit(
    company: CompanyProfile,
    opportunity: dict,
    past_performance: List[PastPerformance],
    estimated_scale: dict
) -> dict:
    """
    Compare estimated contract scale against company capacity.

    Returns:
        {
            'score': int (0-100),
            'fit_level': 'good' | 'stretch' | 'warning' | 'mismatch',
            'reason': str,
            'recommendation': str
        }
    """
    opp_value = estimated_scale['likely']

    # Get company capacity indicators
    if past_performance:
        max_past_contract = max(
            (pp.contract_value for pp in past_performance if pp.contract_value),
            default=Decimal('0')
        )
    else:
        max_past_contract = Decimal('0')

    annual_revenue = company.annual_revenue or Decimal('0')
    employee_count = company.employee_count or 1

    # === Rule 1: Contract value vs past performance ===
    if max_past_contract > 0:
        scale_ratio = float(opp_value / max_past_contract)

        if scale_ratio > 10:
            return {
                'score': 10,
                'fit_level': 'mismatch',
                'reason': f"Contract is {scale_ratio:.0f}x larger than your largest past contract (${max_past_contract:,.0f})",
                'recommendation': "Consider as subcontractor or find teaming partner"
            }
        elif scale_ratio > 5:
            return {
                'score': 30,
                'fit_level': 'warning',
                'reason': f"Contract is {scale_ratio:.0f}x larger than your largest contract",
                'recommendation': "Teaming arrangement strongly recommended"
            }
        elif scale_ratio > 3:
            return {
                'score': 50,
                'fit_level': 'stretch',
                'reason': "Contract is larger than your typical work",
                'recommendation': "Stretch opportunity - ensure you can scale up"
            }
        elif scale_ratio > 0.5:
            return {
                'score': 90,
                'fit_level': 'good',
                'reason': "Contract size matches your demonstrated capability",
                'recommendation': None
            }
        else:
            return {
                'score': 70,
                'fit_level': 'good',
                'reason': "Contract is smaller than your typical work",
                'recommendation': "Easy win but may not be worth the effort"
            }

    # === Rule 2: Contract value vs annual revenue ===
    if annual_revenue > 0:
        revenue_ratio = float(opp_value / annual_revenue)

        if revenue_ratio > 1.0:
            return {
                'score': 20,
                'fit_level': 'mismatch',
                'reason': f"Contract (${opp_value:,.0f}) exceeds your annual revenue (${annual_revenue:,.0f})",
                'recommendation': "Significant capacity expansion required - consider teaming"
            }
        elif revenue_ratio > 0.5:
            return {
                'score': 50,
                'fit_level': 'warning',
                'reason': "Contract represents >50% of annual revenue - high concentration risk",
                'recommendation': "Ensure you can handle cash flow and resource demands"
            }

    # === Rule 3: Enterprise scale vs team size ===
    if estimated_scale.get('is_enterprise') or estimated_scale.get('estimated_fte', 0) > 20:
        if employee_count < 20:
            return {
                'score': 30,
                'fit_level': 'warning',
                'reason': f"Enterprise-scale contract may require larger team (you have {employee_count} employees)",
                'recommendation': "Build teaming arrangement or plan rapid hiring"
            }

    # === Rule 4: FTE requirement vs capacity ===
    estimated_fte = estimated_scale.get('estimated_fte', 0)
    if estimated_fte > 0:
        if estimated_fte > employee_count * 3:
            return {
                'score': 40,
                'fit_level': 'warning',
                'reason': f"May require ~{estimated_fte} FTEs, you have {employee_count} employees",
                'recommendation': "Significant hiring or subcontracting needed"
            }

    # Default: reasonable fit
    return {
        'score': 75,
        'fit_level': 'good',
        'reason': "Contract scale appears reasonable for your company",
        'recommendation': None
    }
```

---

## Security Clearance Matching

### Clearance Detection from Opportunity Text

```python
# app/services/clearance_detector.py

import re
from typing import Optional, List, Tuple

class ClearanceDetector:
    """
    Detect security clearance requirements from opportunity text.
    """

    CLEARANCE_PATTERNS = {
        'ts_sci': [
            r'ts/sci',
            r'top\s*secret/sci',
            r'ts\s*with\s*sci',
            r'sci\s*access',
            r'sensitive\s*compartmented\s*information',
        ],
        'top_secret': [
            r'top\s*secret(?!\s*/\s*sci)',
            r'\bts\b(?!\s*/\s*sci)',
            r'top-secret',
        ],
        'secret': [
            r'\bsecret\b(?!\s*clearance\s*not)',
            r'secret\s*clearance',
            r'secret\s*level',
        ],
        'public_trust': [
            r'public\s*trust',
            r'moderate\s*risk',
            r'high\s*risk\s*public\s*trust',
            r'mrpt',
            r'hrpt',
            r'naci',
            r'background\s*investigation',
        ],
        'none': [
            r'no\s*clearance\s*required',
            r'unclassified',
            r'clearance\s*not\s*required',
        ]
    }

    # Ordered from highest to lowest
    CLEARANCE_HIERARCHY = ['ts_sci', 'top_secret', 'secret', 'public_trust', 'none']

    def detect_clearance(self, opportunity: dict) -> dict:
        """
        Detect required clearance level from opportunity.

        Returns:
            {
                'required_level': str,  # 'ts_sci', 'top_secret', 'secret', 'public_trust', 'none', 'unknown'
                'confidence': str,      # 'high', 'medium', 'low'
                'signals': List[str],   # Text matches that indicated requirement
            }
        """
        title = (opportunity.get('title') or '').lower()
        description = (opportunity.get('description') or '').lower()
        full_text = f"{title} {description}"

        detected = []

        for level, patterns in self.CLEARANCE_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, full_text, re.IGNORECASE)
                if matches:
                    detected.append({
                        'level': level,
                        'pattern': pattern,
                        'matches': matches
                    })

        if not detected:
            return {
                'required_level': 'unknown',
                'confidence': 'low',
                'signals': []
            }

        # Return highest clearance level found
        for level in self.CLEARANCE_HIERARCHY:
            level_detections = [d for d in detected if d['level'] == level]
            if level_detections:
                return {
                    'required_level': level,
                    'confidence': 'high' if len(level_detections) > 1 else 'medium',
                    'signals': [d['matches'][0] for d in level_detections]
                }

        return {
            'required_level': 'unknown',
            'confidence': 'low',
            'signals': []
        }
```

### User Clearance Profile

```sql
-- Add to company_profiles table
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS
    clearance_levels TEXT[] DEFAULT '{}';
    -- Values: 'public_trust', 'secret', 'top_secret', 'ts_sci'

ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS
    clearance_capacity JSONB DEFAULT '{}';
    -- Example: {"secret": 5, "top_secret": 2, "ts_sci": 1}
    -- How many cleared staff at each level

ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS
    can_sponsor_clearances BOOLEAN DEFAULT false;
    -- Can they sponsor new clearances (facility clearance)?

ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS
    facility_clearance_level TEXT;
    -- 'secret', 'top_secret', 'ts_sci' - company facility clearance
```

### Clearance Eligibility Scoring

```python
def calculate_clearance_eligibility(
    company: CompanyProfile,
    required_clearance: str
) -> dict:
    """
    Check if company can meet clearance requirements.

    Returns:
        {
            'eligible': bool,
            'score': int (0-100),
            'reason': str,
            'recommendation': str
        }
    """
    if required_clearance == 'none' or required_clearance == 'unknown':
        return {
            'eligible': True,
            'score': 100,
            'reason': "No clearance required",
            'recommendation': None
        }

    CLEARANCE_RANK = {
        'public_trust': 1,
        'secret': 2,
        'top_secret': 3,
        'ts_sci': 4
    }

    required_rank = CLEARANCE_RANK.get(required_clearance, 0)

    # Check if company has required clearance level
    company_clearances = company.clearance_levels or []
    company_max_rank = max(
        (CLEARANCE_RANK.get(c, 0) for c in company_clearances),
        default=0
    )

    if company_max_rank >= required_rank:
        # Check capacity
        capacity = (company.clearance_capacity or {}).get(required_clearance, 0)
        if capacity > 0:
            return {
                'eligible': True,
                'score': 100,
                'reason': f"Have {capacity} staff with {required_clearance.replace('_', ' ').title()}",
                'recommendation': None
            }
        else:
            return {
                'eligible': True,
                'score': 80,
                'reason': f"Have {required_clearance.replace('_', ' ').title()} capability but limited capacity",
                'recommendation': "May need to hire cleared staff"
            }

    # Check if can sponsor
    if company.can_sponsor_clearances:
        return {
            'eligible': True,
            'score': 50,
            'reason': f"Can sponsor {required_clearance.replace('_', ' ').title()} but don't currently hold",
            'recommendation': "Factor in 6-18 month clearance processing time"
        }

    # Cannot meet requirement
    return {
        'eligible': False,
        'score': 0,
        'reason': f"Requires {required_clearance.replace('_', ' ').title()} clearance - not eligible",
        'recommendation': "Consider as subcontractor to cleared prime"
    }
```

---

## Contract Type Preference

### Contract Type Detection

```python
# app/services/contract_type_detector.py

class ContractTypeDetector:
    """
    Detect contract type from opportunity text.
    """

    CONTRACT_TYPES = {
        'ffp': {
            'patterns': [
                r'firm.fixed.price',
                r'\bffp\b',
                r'fixed.price',
                r'lump.sum',
            ],
            'description': 'Firm Fixed Price - contractor bears cost risk'
        },
        'time_materials': {
            'patterns': [
                r'time.and.materials?',
                r'\bt&m\b',
                r'\btm\b',
                r'labor.hour',
            ],
            'description': 'Time & Materials - shared risk, hourly rates'
        },
        'cost_plus': {
            'patterns': [
                r'cost.plus',
                r'cost.reimbursement',
                r'\bcpff\b',
                r'\bcpaf\b',
                r'\bcpif\b',
            ],
            'description': 'Cost Plus - government bears cost risk'
        },
        'idiq': {
            'patterns': [
                r'indefinite.delivery',
                r'indefinite.quantity',
                r'\bidiq\b',
            ],
            'description': 'IDIQ - task order based, large ceiling'
        },
        'bpa': {
            'patterns': [
                r'blanket.purchase',
                r'\bbpa\b',
            ],
            'description': 'BPA - simplified buying, repeat purchases'
        }
    }

    def detect_type(self, opportunity: dict) -> dict:
        """
        Detect contract type from opportunity.

        Returns:
            {
                'type': str,
                'confidence': str,
                'description': str
            }
        """
        full_text = (
            (opportunity.get('title') or '') + ' ' +
            (opportunity.get('description') or '')
        ).lower()

        for contract_type, info in self.CONTRACT_TYPES.items():
            for pattern in info['patterns']:
                if re.search(pattern, full_text, re.IGNORECASE):
                    return {
                        'type': contract_type,
                        'confidence': 'high',
                        'description': info['description']
                    }

        return {
            'type': 'unknown',
            'confidence': 'low',
            'description': 'Contract type not specified'
        }
```

### User Contract Type Preferences

```sql
-- Add to company_profiles table
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS
    preferred_contract_types TEXT[] DEFAULT '{}';
    -- Values: 'ffp', 'time_materials', 'cost_plus', 'idiq', 'bpa'

ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS
    avoided_contract_types TEXT[] DEFAULT '{}';
    -- Contract types user wants to avoid
```

### Contract Type Scoring

```python
def calculate_contract_type_fit(
    company: CompanyProfile,
    detected_type: str
) -> dict:
    """
    Score based on contract type preference.

    Returns:
        {
            'score': int (0-100),
            'fit': 'preferred' | 'neutral' | 'avoided',
            'reason': str
        }
    """
    if detected_type == 'unknown':
        return {
            'score': 50,
            'fit': 'neutral',
            'reason': 'Contract type not specified'
        }

    preferred = company.preferred_contract_types or []
    avoided = company.avoided_contract_types or []

    if detected_type in avoided:
        return {
            'score': 20,
            'fit': 'avoided',
            'reason': f"You've marked {detected_type.upper()} as avoided"
        }

    if detected_type in preferred:
        return {
            'score': 100,
            'fit': 'preferred',
            'reason': f"{detected_type.upper()} is your preferred contract type"
        }

    return {
        'score': 60,
        'fit': 'neutral',
        'reason': f"Contract type: {detected_type.upper()}"
    }
```

---

## User Journey

### New User Onboarding Flow
```
Signup → Email Verification → Onboarding Wizard → Dashboard

Onboarding Steps:
1. Company Basics (name, size, location, UEI)
2. NAICS Codes (primary + secondary, experience level)
3. Certifications (8(a), HUBZone, SDVOSB, etc.)
4. Capability Statement (PDF upload - optional but encouraged)
5. Past Performance (manual entry or USAspending import)
6. Preferences (contract size range, geographic preferences)
7. Complete → Dashboard with scored opportunities
```

### Returning User Experience
- See "Fit Score" on all opportunity/recompete listings
- Sort/filter by score
- Click score to see breakdown
- Update profile anytime in Settings
- Track bid decisions for improved scoring

---

## Database Schema

### Tables to Create

#### 1. company_profiles
Primary company information and preferences.

```sql
CREATE TABLE company_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Company identification
    company_name TEXT NOT NULL,
    duns_number TEXT,
    uei TEXT,  -- Unique Entity Identifier
    cage_code TEXT,
    sam_registration_status TEXT DEFAULT 'unknown',
    sam_expiration_date DATE,

    -- Size and structure
    employee_count INTEGER,
    annual_revenue DECIMAL,
    business_type TEXT,  -- 'llc', 'corporation', 's-corp', 'sole-proprietor'
    years_in_business INTEGER,
    founding_year INTEGER,

    -- Headquarters location
    hq_street TEXT,
    hq_city TEXT,
    hq_state TEXT,
    hq_zip TEXT,
    hq_country TEXT DEFAULT 'USA',

    -- Additional locations (JSONB array)
    additional_locations JSONB DEFAULT '[]',

    -- Small business status
    is_small_business BOOLEAN DEFAULT true,

    -- Preferences
    preferred_contract_min DECIMAL DEFAULT 0,
    preferred_contract_max DECIMAL DEFAULT 10000000,
    preferred_states TEXT[] DEFAULT '{}',
    preferred_agencies TEXT[] DEFAULT '{}',
    excluded_agencies TEXT[] DEFAULT '{}',
    max_travel_percent INTEGER DEFAULT 25,
    remote_work_preference TEXT DEFAULT 'flexible',  -- 'remote_only', 'hybrid', 'onsite_ok', 'flexible'

    -- Onboarding tracking
    onboarding_completed BOOLEAN DEFAULT false,
    onboarding_completed_at TIMESTAMP WITH TIME ZONE,
    onboarding_current_step INTEGER DEFAULT 1,
    profile_completeness INTEGER DEFAULT 0,  -- 0-100%

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(user_id)
);

CREATE INDEX idx_company_profiles_user_id ON company_profiles(user_id);
CREATE INDEX idx_company_profiles_uei ON company_profiles(uei);
```

#### 2. company_naics
NAICS codes associated with the company.

```sql
CREATE TABLE company_naics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES company_profiles(id) ON DELETE CASCADE,

    naics_code TEXT NOT NULL,
    naics_description TEXT,
    is_primary BOOLEAN DEFAULT false,
    experience_level TEXT DEFAULT 'capable',  -- 'expert', 'experienced', 'capable', 'learning'
    years_experience INTEGER DEFAULT 0,
    contract_count INTEGER DEFAULT 0,  -- How many contracts in this NAICS
    total_value DECIMAL DEFAULT 0,  -- Total value of contracts in this NAICS

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(company_id, naics_code)
);

CREATE INDEX idx_company_naics_company_id ON company_naics(company_id);
CREATE INDEX idx_company_naics_code ON company_naics(naics_code);
```

#### 3. company_certifications
Active certifications and set-aside qualifications.

```sql
CREATE TABLE company_certifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES company_profiles(id) ON DELETE CASCADE,

    certification_type TEXT NOT NULL,
    -- Types: '8a', 'hubzone', 'sdvosb', 'vosb', 'wosb', 'edwosb',
    --        'sdb', 'aboriginal', 'minority_owned', 'veteran_owned'

    certification_number TEXT,
    certifying_agency TEXT,  -- 'SBA', 'VA', 'state', etc.
    issue_date DATE,
    expiration_date DATE,
    is_active BOOLEAN DEFAULT true,

    -- Size standard info (for NAICS-specific size determinations)
    size_standard_naics TEXT,
    size_standard_value TEXT,  -- e.g., "$16.5M" or "500 employees"

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(company_id, certification_type)
);

CREATE INDEX idx_company_certs_company_id ON company_certifications(company_id);
CREATE INDEX idx_company_certs_type ON company_certifications(certification_type);
```

#### 4. capability_statements
Uploaded capability statements with extracted data.

```sql
CREATE TABLE capability_statements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES company_profiles(id) ON DELETE CASCADE,

    -- File info
    file_url TEXT NOT NULL,  -- Supabase storage URL
    file_name TEXT NOT NULL,
    file_size INTEGER,
    mime_type TEXT,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Extracted content
    raw_text TEXT,
    word_count INTEGER,

    -- LLM-extracted structured data
    structured_data JSONB,
    /*
    {
        "company_summary": "...",
        "core_capabilities": ["capability1", "capability2"],
        "differentiators": ["diff1", "diff2"],
        "technologies": ["Python", "AWS", "Tableau"],
        "industries": ["healthcare", "defense"],
        "contract_vehicles": ["GSA", "SEWP"],
        "key_personnel": [{"name": "...", "role": "...", "expertise": "..."}],
        "past_performance_summary": ["..."],
        "naics_mentioned": ["541511", "518210"]
    }
    */

    -- Extracted arrays for quick matching
    core_capabilities TEXT[] DEFAULT '{}',
    technologies TEXT[] DEFAULT '{}',
    differentiators TEXT[] DEFAULT '{}',
    industries TEXT[] DEFAULT '{}',

    -- Processing status
    processing_status TEXT DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    processing_error TEXT,
    processed_at TIMESTAMP WITH TIME ZONE,

    -- Version tracking (users can upload new versions)
    version INTEGER DEFAULT 1,
    is_current BOOLEAN DEFAULT true,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_capability_statements_company_id ON capability_statements(company_id);
CREATE INDEX idx_capability_statements_current ON capability_statements(company_id, is_current) WHERE is_current = true;
```

#### 5. past_performance
Historical contract performance records.

```sql
CREATE TABLE past_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES company_profiles(id) ON DELETE CASCADE,

    -- Contract identification
    contract_number TEXT,
    task_order_number TEXT,
    piid TEXT,  -- Procurement Instrument Identifier (links to USAspending)
    award_id TEXT,  -- USAspending award ID if imported

    -- Agency information
    agency_name TEXT NOT NULL,
    sub_agency TEXT,
    office_name TEXT,

    -- Contracting officer (for references)
    co_name TEXT,
    co_email TEXT,
    co_phone TEXT,

    -- Contract details
    contract_title TEXT NOT NULL,
    contract_description TEXT,
    naics_code TEXT,
    psc_code TEXT,
    contract_type TEXT,  -- 'firm_fixed_price', 'time_materials', 'cost_plus', 'idiq', 'bpa'

    -- Value
    contract_value DECIMAL,
    funded_value DECIMAL,

    -- Period of performance
    pop_start_date DATE,
    pop_end_date DATE,

    -- Place of performance
    pop_city TEXT,
    pop_state TEXT,
    pop_country TEXT DEFAULT 'USA',

    -- Role and involvement
    role TEXT DEFAULT 'prime',  -- 'prime', 'subcontractor', 'joint_venture', 'team_member'
    prime_contractor_name TEXT,  -- If subcontractor
    percent_of_work INTEGER DEFAULT 100,

    -- Team size
    peak_personnel INTEGER,

    -- Performance outcomes
    performance_rating TEXT,  -- 'exceptional', 'very_good', 'satisfactory', 'marginal', 'unsatisfactory', 'unknown'
    completed_on_time BOOLEAN,
    completed_on_budget BOOLEAN,
    received_award_fee BOOLEAN,

    -- Key accomplishments (for proposal writing)
    key_accomplishments TEXT[] DEFAULT '{}',
    technologies_used TEXT[] DEFAULT '{}',
    metrics_achieved JSONB,  -- {"cost_savings": "$2M", "efficiency_gain": "40%"}

    -- Source tracking
    source TEXT DEFAULT 'manual',  -- 'manual', 'usaspending', 'fpds', 'pipeline'
    linked_saved_opportunity_id UUID,  -- If came from our pipeline

    -- Status
    status TEXT DEFAULT 'completed',  -- 'ongoing', 'completed', 'early_termination'

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_past_performance_company_id ON past_performance(company_id);
CREATE INDEX idx_past_performance_naics ON past_performance(naics_code);
CREATE INDEX idx_past_performance_agency ON past_performance(agency_name);
CREATE INDEX idx_past_performance_value ON past_performance(contract_value);
```

#### 6. opportunity_scores
Cached scores for each user-opportunity pair.

```sql
CREATE TABLE opportunity_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES company_profiles(id) ON DELETE CASCADE,

    -- Opportunity reference
    opportunity_id TEXT NOT NULL,
    opportunity_type TEXT NOT NULL,  -- 'sam' or 'recompete'

    -- Overall score
    overall_score INTEGER NOT NULL CHECK (overall_score >= 0 AND overall_score <= 100),

    -- Component scores (all 0-100)
    capability_score INTEGER,
    eligibility_score INTEGER,
    win_probability_score INTEGER,
    strategic_score INTEGER,
    timeline_score INTEGER,

    -- Eligibility
    is_eligible BOOLEAN DEFAULT true,
    eligibility_issues TEXT[] DEFAULT '{}',

    -- Match details
    matched_naics TEXT[] DEFAULT '{}',
    matched_certifications TEXT[] DEFAULT '{}',
    matched_keywords TEXT[] DEFAULT '{}',
    matched_past_performance UUID[] DEFAULT '{}',

    -- Detailed breakdown for UI
    score_breakdown JSONB,
    /*
    {
        "capability": {
            "naics_match": {"score": 30, "reason": "Exact NAICS match: 541511"},
            "keyword_match": {"score": 25, "matched": ["Python", "AWS"]},
            "past_performance": {"score": 20, "contracts": 3}
        },
        "eligibility": {
            "set_aside": {"score": 50, "type": "8(a)", "eligible": true},
            "certifications": {"score": 25, "matched": ["8a", "sdvosb"]}
        },
        ...
    }
    */

    -- Timestamps
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,  -- When to recalculate

    UNIQUE(company_id, opportunity_id, opportunity_type)
);

CREATE INDEX idx_opportunity_scores_company ON opportunity_scores(company_id);
CREATE INDEX idx_opportunity_scores_lookup ON opportunity_scores(company_id, opportunity_type, overall_score DESC);
CREATE INDEX idx_opportunity_scores_expires ON opportunity_scores(expires_at) WHERE expires_at IS NOT NULL;
```

#### 7. opportunity_decisions
Track user decisions for ML improvement.

```sql
CREATE TABLE opportunity_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES company_profiles(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id),

    -- Opportunity reference
    opportunity_id TEXT NOT NULL,
    opportunity_type TEXT NOT NULL,
    opportunity_title TEXT,

    -- Decision
    decision TEXT NOT NULL,
    -- 'viewed', 'saved', 'analyzing', 'preparing_bid', 'submitted',
    -- 'won', 'lost', 'no_bid', 'passed', 'not_eligible'

    decision_reason TEXT,  -- Why they made this decision

    -- Capture context at time of decision
    score_at_decision INTEGER,
    score_breakdown_at_decision JSONB,

    -- Bid details (if applicable)
    bid_submitted_date DATE,
    bid_amount DECIMAL,

    -- Outcome (if bid submitted)
    outcome TEXT,  -- 'pending', 'won', 'lost', 'cancelled', 'protested'
    outcome_date DATE,
    won_amount DECIMAL,
    loss_reason TEXT,

    -- Feedback
    was_score_accurate BOOLEAN,  -- User feedback on score accuracy
    user_feedback TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_decisions_company ON opportunity_decisions(company_id);
CREATE INDEX idx_decisions_outcome ON opportunity_decisions(outcome) WHERE outcome IS NOT NULL;
```

---

## API Endpoints

### Profile Management

```
# Company Profile
POST   /api/v1/profile/company                    # Create (during onboarding)
GET    /api/v1/profile/company                    # Get current user's profile
PATCH  /api/v1/profile/company                    # Update profile
GET    /api/v1/profile/completeness               # Get profile completeness %

# Onboarding
GET    /api/v1/profile/onboarding/status          # Get current step, completion
POST   /api/v1/profile/onboarding/step/{step}     # Save step data
POST   /api/v1/profile/onboarding/complete        # Mark onboarding complete
POST   /api/v1/profile/onboarding/skip            # Skip remaining steps

# NAICS Codes
GET    /api/v1/profile/naics                      # List company NAICS
POST   /api/v1/profile/naics                      # Add NAICS code
PATCH  /api/v1/profile/naics/{id}                 # Update (experience level, primary)
DELETE /api/v1/profile/naics/{id}                 # Remove NAICS
GET    /api/v1/naics/search?q=                    # Search NAICS codes (autocomplete)

# Certifications
GET    /api/v1/profile/certifications             # List certifications
POST   /api/v1/profile/certifications             # Add certification
PATCH  /api/v1/profile/certifications/{id}        # Update
DELETE /api/v1/profile/certifications/{id}        # Remove

# Capability Statement
GET    /api/v1/profile/capability-statement       # Get current statement
POST   /api/v1/profile/capability-statement       # Upload new statement
DELETE /api/v1/profile/capability-statement/{id}  # Delete statement
POST   /api/v1/profile/capability-statement/{id}/process  # Trigger AI processing
GET    /api/v1/profile/capability-statement/{id}/status   # Check processing status

# Past Performance
GET    /api/v1/profile/past-performance           # List all
POST   /api/v1/profile/past-performance           # Add new record
GET    /api/v1/profile/past-performance/{id}      # Get one
PATCH  /api/v1/profile/past-performance/{id}      # Update
DELETE /api/v1/profile/past-performance/{id}      # Delete
POST   /api/v1/profile/past-performance/import    # Import from USAspending by UEI
```

### Scoring

```
# Scoring
GET    /api/v1/scoring/opportunity/{type}/{id}    # Get score for one opportunity
POST   /api/v1/scoring/opportunities              # Batch score (body: {ids, type})
POST   /api/v1/scoring/refresh                    # Recalculate all user's scores
GET    /api/v1/scoring/stats                      # User's scoring stats

# Deep Analysis (Premium)
POST   /api/v1/scoring/analyze/{type}/{id}        # AI deep analysis
GET    /api/v1/scoring/analysis/{id}              # Get analysis result

# Decisions
POST   /api/v1/decisions                          # Record a decision
GET    /api/v1/decisions                          # List user's decisions
PATCH  /api/v1/decisions/{id}                     # Update (e.g., add outcome)
```

---

## Frontend Components

### New Pages

```
/onboarding                           # Onboarding wizard container
/onboarding/welcome                   # Welcome screen
/onboarding/company                   # Step 1: Company basics
/onboarding/naics                     # Step 2: NAICS selection
/onboarding/certifications            # Step 3: Certifications
/onboarding/capability-statement      # Step 4: Upload capability statement
/onboarding/past-performance          # Step 5: Past performance
/onboarding/preferences               # Step 6: Preferences
/onboarding/complete                  # Success screen

/settings/company                     # Edit company profile
/settings/naics                       # Manage NAICS codes
/settings/certifications              # Manage certifications
/settings/capability-statement        # Manage capability statement
/settings/past-performance            # Manage past performance
/settings/preferences                 # Edit preferences
```

### New Components

```
src/components/onboarding/
  OnboardingWizard.tsx               # Main wizard container
  ProgressIndicator.tsx              # Step progress bar
  CompanyBasicsForm.tsx              # Step 1 form
  NAICSSelector.tsx                  # Step 2 - NAICS picker with search
  CertificationsForm.tsx             # Step 3 form
  CapabilityUploader.tsx             # Step 4 - PDF upload
  PastPerformanceForm.tsx            # Step 5 - Add/edit past performance
  PreferencesForm.tsx                # Step 6 form
  ProfileStrengthMeter.tsx           # Visual indicator of profile completeness

src/components/scoring/
  FitScoreBadge.tsx                  # Score display (0-100 with color)
  ScoreBreakdown.tsx                 # Detailed score breakdown modal
  ScoreTooltip.tsx                   # Hover tooltip with quick breakdown
  EligibilityWarning.tsx             # "Not eligible" indicator
  MatchedItems.tsx                   # Show matched NAICS, keywords, etc.

src/components/past-performance/
  PastPerformanceList.tsx            # List of past contracts
  PastPerformanceCard.tsx            # Individual contract card
  PastPerformanceModal.tsx           # Add/edit modal
  USAspendingImport.tsx              # Import from USAspending

src/components/capability/
  CapabilityStatementUpload.tsx      # Upload with drag-drop
  CapabilityPreview.tsx              # Preview extracted data
  ProcessingStatus.tsx               # Show AI processing status
```

### Updated Components

```
src/pages/Opportunities/OpportunitiesList.tsx
  - Add FitScore column
  - Add sort by score
  - Add filter by min score

src/pages/Recompetes/RecompetesList.tsx
  - Add FitScore column
  - Add sort by score
  - Add filter by min score

src/pages/Opportunities/OpportunityDetail.tsx
  - Add ScoreBreakdown section
  - Show matched past performance
  - Add "Record Decision" button

src/pages/Recompetes/RecompeteDetail.tsx
  - Add ScoreBreakdown section
  - Show matched past performance
  - Add "Record Decision" button

src/layout/AppSidebar.tsx
  - Add "Complete Profile" prompt if onboarding incomplete
  - Add profile completeness indicator

src/App.tsx
  - Add onboarding route guard (redirect to onboarding if not complete)
```

---

## Scoring Algorithm

### Detailed Implementation

```python
# app/services/scoring_service.py

from decimal import Decimal
from typing import Dict, List, Optional
import math

class ScoringService:
    """Calculate opportunity fit scores for a company."""

    # Weights for each dimension
    WEIGHTS = {
        'capability': 0.35,
        'eligibility': 0.25,
        'win_probability': 0.20,
        'strategic': 0.10,
        'timeline': 0.10
    }

    def calculate_score(
        self,
        company: CompanyProfile,
        opportunity: dict,
        past_performance: List[PastPerformance],
        capability_statement: Optional[CapabilityStatement]
    ) -> dict:
        """Calculate comprehensive fit score."""

        # 1. Eligibility (must pass or score = 0)
        eligibility_result = self._calculate_eligibility(company, opportunity)
        if not eligibility_result['is_eligible']:
            return {
                'overall_score': 0,
                'is_eligible': False,
                'eligibility_issues': eligibility_result['issues'],
                'capability_score': 0,
                'eligibility_score': 0,
                'win_probability_score': 0,
                'strategic_score': 0,
                'timeline_score': 0
            }

        # 2. Calculate each dimension
        capability_score = self._calculate_capability(
            company, opportunity, capability_statement
        )

        win_prob_score = self._calculate_win_probability(
            company, opportunity, past_performance
        )

        strategic_score = self._calculate_strategic_fit(
            company, opportunity
        )

        timeline_score = self._calculate_timeline(opportunity)

        # 3. Weighted sum
        overall = (
            capability_score * self.WEIGHTS['capability'] +
            eligibility_result['score'] * self.WEIGHTS['eligibility'] +
            win_prob_score * self.WEIGHTS['win_probability'] +
            strategic_score * self.WEIGHTS['strategic'] +
            timeline_score * self.WEIGHTS['timeline']
        )

        return {
            'overall_score': int(round(overall)),
            'is_eligible': True,
            'eligibility_issues': [],
            'capability_score': capability_score,
            'eligibility_score': eligibility_result['score'],
            'win_probability_score': win_prob_score,
            'strategic_score': strategic_score,
            'timeline_score': timeline_score,
            'matched_naics': eligibility_result.get('matched_naics', []),
            'matched_certifications': eligibility_result.get('matched_certs', []),
            'matched_past_performance': [],  # TODO: Add PP matching
            'score_breakdown': {
                'capability': capability_score_details,
                'eligibility': eligibility_result,
                'win_probability': win_prob_details,
                'strategic': strategic_details,
                'timeline': timeline_details
            }
        }

    def _calculate_eligibility(self, company: CompanyProfile, opp: dict) -> dict:
        """
        Check if company is eligible to bid.
        Returns score 0-100 and eligibility status.
        """
        score = 50  # Start neutral
        issues = []
        matched_certs = []

        set_aside = opp.get('set_aside_type', '').lower()
        opp_naics = opp.get('naics_code', '')

        # Check set-aside eligibility
        if set_aside:
            if set_aside in ['8(a)', '8a']:
                if company.has_certification('8a'):
                    score += 50
                    matched_certs.append('8(a)')
                else:
                    return {'is_eligible': False, 'issues': ['Requires 8(a) certification'], 'score': 0}

            elif set_aside in ['hubzone', 'hub zone']:
                if company.has_certification('hubzone'):
                    score += 50
                    matched_certs.append('HUBZone')
                else:
                    return {'is_eligible': False, 'issues': ['Requires HUBZone certification'], 'score': 0}

            elif set_aside in ['sdvosb', 'service-disabled veteran']:
                if company.has_certification('sdvosb'):
                    score += 50
                    matched_certs.append('SDVOSB')
                else:
                    return {'is_eligible': False, 'issues': ['Requires SDVOSB certification'], 'score': 0}

            elif set_aside in ['wosb', 'women-owned']:
                if company.has_certification('wosb') or company.has_certification('edwosb'):
                    score += 50
                    matched_certs.append('WOSB')
                else:
                    return {'is_eligible': False, 'issues': ['Requires WOSB certification'], 'score': 0}

            elif 'small business' in set_aside:
                if company.is_small_business:
                    score += 30
                else:
                    return {'is_eligible': False, 'issues': ['Requires small business status'], 'score': 0}

        else:
            # Full & open competition - anyone can bid but more competition
            score += 25

        # Check NAICS match
        matched_naics = []
        if opp_naics:
            if company.has_naics(opp_naics):
                score = min(100, score + 25)
                matched_naics.append(opp_naics)
            elif company.has_related_naics(opp_naics):
                score = min(100, score + 10)
                matched_naics.append(opp_naics + ' (related)')

        return {
            'is_eligible': True,
            'score': min(100, score),
            'issues': issues,
            'matched_certs': matched_certs,
            'matched_naics': matched_naics
        }

    def _calculate_capability(
        self,
        company: CompanyProfile,
        opp: dict,
        capability: Optional[CapabilityStatement]
    ) -> int:
        """
        Calculate capability match score.
        Uses NAICS, keywords, and semantic similarity.
        """
        score = 0

        opp_naics = opp.get('naics_code', '')
        opp_title = opp.get('title', '').lower()
        opp_desc = opp.get('description', '').lower()

        # NAICS match (0-30 points)
        if opp_naics:
            naics_match = company.get_naics_match(opp_naics)
            if naics_match:
                if naics_match['is_primary']:
                    score += 30
                elif naics_match['experience_level'] == 'expert':
                    score += 25
                elif naics_match['experience_level'] == 'experienced':
                    score += 20
                else:
                    score += 15
            elif company.has_related_naics(opp_naics):
                score += 10

        # Keyword matching (0-40 points)
        if capability and capability.technologies:
            tech_matches = 0
            for tech in capability.technologies:
                if tech.lower() in opp_title or tech.lower() in opp_desc:
                    tech_matches += 1

            tech_score = min(40, tech_matches * 8)  # 5 matches = 40 points
            score += tech_score

        # Core capability matching (0-30 points)
        if capability and capability.core_capabilities:
            cap_matches = 0
            for cap in capability.core_capabilities:
                cap_words = cap.lower().split()
                for word in cap_words:
                    if len(word) > 4 and word in opp_desc:
                        cap_matches += 1
                        break

            cap_score = min(30, cap_matches * 6)
            score += cap_score

        return min(100, score)

    def _calculate_win_probability(
        self,
        company: CompanyProfile,
        opp: dict,
        past_performance: List[PastPerformance]
    ) -> int:
        """
        Estimate probability of winning.
        Based on incumbent, competition, and past performance.
        """
        score = 50  # Start neutral

        # Check incumbent situation
        incumbent_name = opp.get('incumbent_name', '')
        if not incumbent_name:
            score += 20  # No incumbent = better chance
        elif incumbent_name.lower() == company.company_name.lower():
            score += 30  # We ARE the incumbent
        else:
            # There's another incumbent - slight disadvantage
            score -= 10

        # Agency experience
        agency_name = opp.get('agency_name', opp.get('awarding_agency_name', ''))
        if agency_name:
            agency_contracts = [
                pp for pp in past_performance
                if pp.agency_name and agency_name.lower() in pp.agency_name.lower()
            ]
            if agency_contracts:
                # Have experience with this agency
                score += min(25, len(agency_contracts) * 10)

        # Similar contract experience
        opp_value = opp.get('contract_value', opp.get('total_value', 0)) or 0
        if opp_value > 0:
            similar_value_contracts = [
                pp for pp in past_performance
                if pp.contract_value and abs(pp.contract_value - opp_value) / opp_value < 0.5
            ]
            if similar_value_contracts:
                score += 10

        # Geographic advantage
        opp_state = opp.get('pop_state', opp.get('place_of_performance_state', ''))
        if opp_state and company.hq_state:
            if opp_state.upper() == company.hq_state.upper():
                score += 15
            elif opp_state.upper() in [loc.get('state', '').upper() for loc in company.additional_locations]:
                score += 10

        return max(0, min(100, score))

    def _calculate_strategic_fit(self, company: CompanyProfile, opp: dict) -> int:
        """
        Determine if opportunity aligns with company strategy.
        """
        score = 50

        # Contract value alignment
        opp_value = opp.get('contract_value', opp.get('total_value', 0)) or 0
        if opp_value > 0:
            min_pref = company.preferred_contract_min or 0
            max_pref = company.preferred_contract_max or float('inf')

            if min_pref <= opp_value <= max_pref:
                score += 30  # In sweet spot
            elif opp_value < min_pref:
                score += 10  # Too small but doable
            else:
                score += 15  # Bigger than usual but could be good

        # Preferred agency
        agency = opp.get('agency_name', opp.get('awarding_agency_name', ''))
        if agency and company.preferred_agencies:
            if any(pref.lower() in agency.lower() for pref in company.preferred_agencies):
                score += 20

        # Excluded agency check
        if agency and company.excluded_agencies:
            if any(excl.lower() in agency.lower() for excl in company.excluded_agencies):
                score -= 30

        return max(0, min(100, score))

    def _calculate_timeline(self, opp: dict) -> int:
        """
        Assess if timeline is realistic.
        """
        from datetime import datetime, timezone

        deadline = opp.get('response_deadline')
        if not deadline:
            return 50  # Unknown deadline

        if isinstance(deadline, str):
            try:
                deadline = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
            except:
                return 50

        now = datetime.now(timezone.utc)
        days_remaining = (deadline - now).days

        if days_remaining > 30:
            return 100
        elif days_remaining > 14:
            return 80
        elif days_remaining > 7:
            return 60
        elif days_remaining > 3:
            return 40
        elif days_remaining > 0:
            return 20
        else:
            return 0  # Deadline passed
```

---

## Implementation Phases

### Phase 1: Foundation (MVP)
**Goal**: Basic profile, onboarding flow, and rule-based scoring

**Database**:
- [ ] Create company_profiles table (with clearance + contract type fields)
- [ ] Create company_naics table
- [ ] Create company_certifications table
- [ ] Create opportunity_scores table
- [ ] Create opportunity_metadata table
- [ ] Add migration endpoint
- [ ] Create all performance indexes

**Backend API**:
- [ ] POST/GET/PATCH /profile/company
- [ ] CRUD /profile/naics
- [ ] CRUD /profile/certifications
- [ ] GET /profile/onboarding/status
- [ ] POST /profile/onboarding/complete
- [ ] Basic scoring service (eligibility + NAICS match only)
- [ ] GET /scoring/opportunity/{type}/{id}
- [ ] POST /scoring/batch (for list views)

**Frontend**:
- [ ] Onboarding wizard container
- [ ] Step 1: Company basics form (name, size, location, UEI)
- [ ] Step 2: NAICS selector with search
- [ ] Step 3: Certifications checklist
- [ ] Step 4: Security clearance levels
- [ ] Step 5: Contract type preferences
- [ ] Step 6: Preferences (contract size range, agencies)
- [ ] Onboarding completion screen
- [ ] Route guard (redirect to onboarding if incomplete)
- [ ] FitScoreBadge component
- [ ] Add score column to OpportunitiesList
- [ ] Add score column to RecompetesList

**Estimated Effort**: 4-5 days

---

### Phase 1.5: Opportunity Metadata & Scale Inference
**Goal**: Pre-process opportunities for efficient scoring at scale

**Database**:
- [ ] Create opportunity_metadata table
- [ ] Add source_hash for change detection
- [ ] Create indexes for clearance and scale filtering

**Backend Services**:
- [ ] ContractScaleEstimator service
- [ ] ClearanceDetector service
- [ ] ContractTypeDetector service
- [ ] Opportunity metadata extraction job (runs on sync)
- [ ] Batch metadata processing endpoint

**Integration**:
- [ ] Hook metadata extraction into SAM.gov sync
- [ ] Hook metadata extraction into USAspending sync
- [ ] Add estimated_scale, clearance, contract_type to scoring service
- [ ] Scale fit scoring with past performance comparison

**Frontend**:
- [ ] Show scale warning badges on opportunity cards
- [ ] Show clearance requirements in listings
- [ ] Filter by clearance level
- [ ] Filter by estimated contract size range

**Estimated Effort**: 2-3 days

---

### Phase 2: Past Performance
**Goal**: Track and utilize past contracts for scale fit + win probability

**Database**:
- [ ] Create past_performance table
- [ ] Create opportunity_decisions table
- [ ] Add indexes for agency and value lookups

**Backend API**:
- [ ] CRUD /profile/past-performance
- [ ] POST /profile/past-performance/import (USAspending by UEI)
- [ ] Update scoring to use past performance
- [ ] POST /decisions
- [ ] Scale fit calculation using max past contract value

**Frontend**:
- [ ] Past performance entry form in onboarding
- [ ] Past performance list/management page
- [ ] USAspending import wizard (enter UEI, fetch contracts)
- [ ] "Record Decision" button on opportunity detail
- [ ] Updated score breakdown with PP matches
- [ ] Scale fit warnings ("10x larger than your biggest contract")

**Estimated Effort**: 3-4 days

---

### Phase 3: Capability Statement
**Goal**: Upload and extract data from capability statements

**Database**:
- [ ] Create capability_statements table
- [ ] Set up Supabase Storage bucket

**Backend API**:
- [ ] POST /profile/capability-statement (upload)
- [ ] PDF text extraction
- [ ] LLM-powered structured extraction
- [ ] Update scoring with keyword matching

**Frontend**:
- [ ] Step 4: Capability statement uploader
- [ ] Processing status indicator
- [ ] Preview extracted data
- [ ] Capability management page

**Estimated Effort**: 2-3 days

---

### Phase 4: Enhanced Scoring & UI
**Goal**: Better UX and score explanations

**Backend**:
- [ ] Batch scoring endpoint
- [ ] Score caching and invalidation
- [ ] Score refresh on profile update

**Frontend**:
- [ ] Score breakdown modal
- [ ] Matched items display
- [ ] Sort/filter by score
- [ ] Profile completeness meter
- [ ] Settings pages for all profile sections

**Estimated Effort**: 2 days

---

### Phase 5: Learning & AI (Future)
**Goal**: Improve scoring over time

**Features**:
- [ ] Track bid outcomes (won/lost)
- [ ] Analyze win patterns
- [ ] Semantic embedding matching (pgvector)
- [ ] Deep AI analysis feature
- [ ] Personalized weight adjustments

**Estimated Effort**: 3-5 days

---

## Progress Tracking

### Phase 1 Progress - Foundation

| Task | Status | Date | Notes |
|------|--------|------|-------|
| Database schema design | ✅ Complete | Dec 13, 2025 | Includes clearance, contract type, scale fields |
| Scalability architecture design | ✅ Complete | Dec 13, 2025 | 3-layer caching, batch scoring, invalidation rules |
| Create company_profiles table | ✅ Complete | Dec 13, 2025 | app/models/company.py - CompanyProfile model |
| Create company_naics table | ✅ Complete | Dec 13, 2025 | app/models/company.py - CompanyNAICS model |
| Create company_certifications table | ✅ Complete | Dec 13, 2025 | app/models/company.py - CompanyCertification model |
| Create opportunity_scores table | ✅ Complete | Dec 13, 2025 | app/models/company.py - OpportunityScore model |
| Create opportunity_metadata table | ✅ Complete | Dec 13, 2025 | app/models/company.py - OpportunityMetadata model |
| Create performance indexes | ⬜ Not Started | | Will add during performance optimization |
| Profile API endpoints | ✅ Complete | Dec 13, 2025 | app/api/profile.py - Full CRUD |
| NAICS API endpoints | ✅ Complete | Dec 13, 2025 | app/api/profile.py - Add/List/Delete |
| Certifications API endpoints | ✅ Complete | Dec 13, 2025 | app/api/profile.py - Add/List/Delete |
| Batch scoring endpoint | ⬜ Not Started | | |
| Basic scoring service | ⬜ Not Started | | |
| Onboarding wizard container | ✅ Complete | Dec 13, 2025 | CompanyOnboardingPage.tsx - 4-step wizard |
| Company basics form | ✅ Complete | Dec 13, 2025 | Step 1 of onboarding wizard |
| NAICS selector | ✅ Complete | Dec 13, 2025 | Step 2 with common codes dropdown |
| Certifications form | ✅ Complete | Dec 13, 2025 | Step 3 with common certs dropdown |
| Clearance levels form | ✅ Complete | Dec 13, 2025 | Step 4 in preferences |
| Contract type preferences | ✅ Complete | Dec 13, 2025 | Step 4 with sliders (1-5) |
| Route guard for onboarding | ⬜ Not Started | | |
| FitScoreBadge component | ⬜ Not Started | | |
| Score column in lists | ⬜ Not Started | | |

### Phase 1.5 Progress - Metadata & Scale Inference

| Task | Status | Date | Notes |
|------|--------|------|-------|
| ContractScaleEstimator service | ✅ Complete | Dec 13, 2025 | Algorithm designed |
| ClearanceDetector service | ✅ Complete | Dec 13, 2025 | Algorithm designed |
| ContractTypeDetector service | ✅ Complete | Dec 13, 2025 | Algorithm designed |
| Scale fit comparison logic | ✅ Complete | Dec 13, 2025 | Uses past perf + revenue + FTE |
| Metadata extraction job | ⬜ Not Started | | |
| Hook into SAM.gov sync | ⬜ Not Started | | |
| Hook into USAspending sync | ⬜ Not Started | | |
| Scale warning badges UI | ⬜ Not Started | | |
| Clearance filter in lists | ⬜ Not Started | | |

### Phase 2 Progress - Past Performance

| Task | Status | Date | Notes |
|------|--------|------|-------|
| Create past_performance table | ✅ Complete | Dec 13, 2025 | app/models/company.py - PastPerformance model |
| Create opportunity_decisions table | ✅ Complete | Dec 13, 2025 | app/models/company.py - OpportunityDecision model |
| Past performance CRUD API | ✅ Complete | Dec 13, 2025 | app/api/profile.py - Add/List/Delete |
| USAspending import by UEI | ⬜ Not Started | | |
| Past performance form UI | ⬜ Not Started | | |
| Decision tracking | ⬜ Not Started | | |
| Scale fit using max past contract | ⬜ Not Started | | |

### Phase 3 Progress - Capability Statement

| Task | Status | Date | Notes |
|------|--------|------|-------|
| Create capability_statements table | ✅ Complete | Dec 13, 2025 | app/models/company.py - CapabilityStatement model |
| Supabase storage bucket | ⬜ Not Started | | |
| File upload API | ⬜ Not Started | | |
| PDF text extraction | ⬜ Not Started | | |
| LLM structured extraction | ⬜ Not Started | | |
| Capability uploader UI | ⬜ Not Started | | |

### Phase 4 Progress - Enhanced UX

| Task | Status | Date | Notes |
|------|--------|------|-------|
| Score breakdown modal | ⬜ Not Started | | |
| Sort/filter by score | ⬜ Not Started | | |
| Profile completeness meter | ⬜ Not Started | | |
| Settings pages | ⬜ Not Started | | |
| Score caching & invalidation | ⬜ Not Started | | |

### Phase 5 Progress - Learning & AI

| Task | Status | Date | Notes |
|------|--------|------|-------|
| Track bid outcomes | ⬜ Not Started | | |
| Semantic embeddings (pgvector) | ⬜ Not Started | | |
| Deep AI analysis feature | ⬜ Not Started | | |
| Personalized weight adjustments | ⬜ Not Started | | |

---

## Notes & Decisions

### Dec 13, 2025 - Implementation Progress (Session 2)
**Backend Implementation:**
- Created `app/models/company.py` with all 8 models:
  - CompanyProfile (core profile with clearance, preferences, scale settings)
  - CompanyNAICS (NAICS codes with experience levels)
  - CompanyCertification (set-aside certifications)
  - PastPerformance (historical contract data)
  - CapabilityStatement (uploaded capability statements)
  - OpportunityMetadata (pre-extracted opportunity signals)
  - OpportunityScore (cached per-user scores)
  - OpportunityDecision (bid/no-bid tracking)
- Created `app/api/profile.py` with full CRUD endpoints:
  - Company profile create/update/get
  - NAICS add/list/delete
  - Certifications add/list/delete
  - Past performance add/list/delete
  - Onboarding status/complete/skip
- Added migration endpoint `/api/v1/admin/migrate-scoring`
- Updated User model with company_profile relationship

**Frontend Implementation:**
- Created `src/api/company.ts` with API client functions
- Created `src/stores/companyStore.ts` Zustand store
- Created `src/pages/Onboarding/CompanyOnboardingPage.tsx`:
  - 4-step wizard (Company Info → NAICS → Certifications → Preferences)
  - Progress indicator with step tracking
  - Common NAICS codes dropdown (16 common federal IT codes)
  - Common certifications dropdown (8(a), HUBZone, SDVOSB, etc.)
  - Contract type preference sliders (1-5 scale)
  - Security clearance level selection
  - Scale preferences (min/max contract value)
- Added route `/company-setup` for new onboarding flow

**Files Created:**
- `/app/models/company.py` (307 lines)
- `/app/api/profile.py` (341 lines)
- `/app/schemas/company.py` (245 lines)
- `/frontend/src/api/company.ts` (166 lines)
- `/frontend/src/stores/companyStore.ts` (280 lines)
- `/frontend/src/pages/Onboarding/CompanyOnboardingPage.tsx` (540 lines)

**Next Steps:**
1. Implement basic scoring service
2. Display scores in opportunity/recompete lists
3. Add FitScoreBadge component
4. Create route guard for onboarding completion

### Dec 13, 2025 - Evening Update
- Added **Scale Fit** scoring dimension (15% weight)
  - Infers contract size from text signals (keywords, FTE mentions, $ amounts)
  - Compares against user's largest past contract, revenue, and employee count
  - Flags mismatches ("10x larger than your biggest contract")
- Added **Security Clearance** to eligibility scoring
  - Detects clearance requirements from opportunity text
  - Hard filter if user can't meet clearance requirement
  - User profile includes clearance levels held and capacity
- Added **Contract Type** preference scoring
  - Detects FFP, T&M, Cost-Plus, IDIQ, BPA from text
  - Matches against user preferences/avoidances
- Designed **scalability architecture** for concurrent users:
  - 3-layer caching (opportunity metadata, user scores, in-memory)
  - Opportunity metadata pre-processing on sync
  - Batch scoring endpoint for list views
  - Score invalidation rules by trigger type
  - Rate limiting and connection pooling

### Dec 13, 2025 - Initial Planning
- Initial planning complete
- Decided on 6-dimension scoring model (was 5, added Scale Fit)
- Phase 1 focuses on MVP without AI features
- Will use Supabase Storage for capability statements
- Past performance can be imported from USAspending via UEI

---

## Open Questions

1. **Embedding Provider**: OpenAI vs Anthropic for semantic matching?
2. **Score Caching TTL**: 24 hours? 7 days? Until profile change?
3. **Batch Processing**: On-demand with caching (recommended) vs eager pre-calculation
4. **Free vs Pro Features**: Should deep AI analysis be a paid feature?
5. **Scale Inference Confidence**: How to handle low-confidence estimates in scoring?

---

## Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Score calculation strategy | Hybrid (on-demand + pre-calc for saved) | Balances performance and computation cost |
| Opportunity metadata | Pre-process on sync | Avoid re-parsing text for every user |
| Scale without $ value | Infer from signals | Keywords, FTE, POP, set-aside limits |
| Clearance mismatch | Hard filter (score = 0) | Can't bid without required clearance |
| Contract type mismatch | Soft penalty (-40 points) | User preference, not hard requirement |
| Score invalidation | Mark expired, lazy recalc | Show stale score while updating |

---

*Last Updated: December 13, 2025 - Evening*
