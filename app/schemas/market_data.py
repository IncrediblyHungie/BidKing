"""Market data and intelligence Pydantic schemas."""

from datetime import datetime, date
from typing import Optional
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel, Field


class NAICSStatisticsResponse(BaseModel):
    """Schema for NAICS code statistics."""

    naics_code: str
    naics_description: Optional[str]

    # Award statistics (last 12 months)
    total_awards_12mo: int
    total_obligation_12mo: Decimal
    avg_award_amount_12mo: Decimal
    median_award_amount_12mo: Decimal
    min_award_amount_12mo: Decimal
    max_award_amount_12mo: Decimal

    # Awards by size bucket
    awards_under_25k: int
    awards_25k_to_100k: int
    awards_100k_to_250k: int
    awards_250k_to_1m: int
    awards_over_1m: int

    # Small business statistics
    small_business_awards: int
    small_business_percentage: Decimal

    # Competition statistics
    avg_offers_received: Decimal
    sole_source_percentage: Decimal

    # Top agencies and recipients
    top_agencies: list[dict]
    top_recipients: list[dict]

    # Recompete pipeline
    contracts_expiring_90_days: int
    contracts_expiring_180_days: int
    contracts_expiring_365_days: int

    calculated_at: datetime

    class Config:
        from_attributes = True


class LaborRateRequest(BaseModel):
    """Schema for labor rate lookup request."""

    job_title: str = Field(..., min_length=2, max_length=255)
    experience_min: Optional[int] = Field(None, ge=0, le=50)
    experience_max: Optional[int] = Field(None, ge=0, le=50)
    education_level: Optional[str] = None


class LaborRateResponse(BaseModel):
    """Schema for labor rate response."""

    search_query: str
    experience_range: Optional[str]
    education_level: Optional[str]

    # Rate statistics
    match_count: int
    min_rate: Optional[Decimal]
    max_rate: Optional[Decimal]
    avg_rate: Optional[Decimal]
    median_rate: Optional[Decimal]
    percentile_25: Optional[Decimal]
    percentile_75: Optional[Decimal]

    # Sample categories
    sample_categories: list[dict]

    # Cache info
    cached_at: datetime
    data_freshness: str  # e.g., "live" or "cached 2 hours ago"

    class Config:
        from_attributes = True


class CompetitorResponse(BaseModel):
    """Schema for competitor/recipient information."""

    uei: str
    name: str
    parent_name: Optional[str]

    # Location
    city: Optional[str]
    state: Optional[str]

    # Business types
    business_types: list[str]
    is_small_business: bool

    # Award statistics
    total_awards: int
    total_obligation: Decimal
    first_award_date: Optional[date]
    last_award_date: Optional[date]

    # NAICS expertise
    primary_naics_codes: list[str]

    # Top agencies worked with
    top_agencies: list[dict]

    last_updated: datetime

    class Config:
        from_attributes = True


class RecompeteResponse(BaseModel):
    """Schema for recompete opportunity."""

    id: UUID
    award_id: str
    piid: str  # Contract number

    # Expiration
    period_of_performance_end: date
    days_until_expiration: int

    # Award details
    naics_code: Optional[str]
    total_value: Optional[Decimal]
    awarding_agency_name: Optional[str]

    # Incumbent
    incumbent_name: Optional[str]
    incumbent_uei: Optional[str]

    # Tracking
    status: str
    linked_opportunity_id: Optional[str]  # SAM.gov opportunity when posted

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RecompeteListResponse(BaseModel):
    """Schema for paginated recompete list."""

    items: list[RecompeteResponse]
    total: int
    page: int
    page_size: int


class MarketOverview(BaseModel):
    """Schema for market overview dashboard."""

    # Overall statistics
    total_active_opportunities: int
    new_opportunities_today: int
    new_opportunities_week: int

    # By type
    opportunities_by_type: dict[str, int]

    # By set-aside
    opportunities_by_setaside: dict[str, int]

    # Top agencies
    top_agencies: list[dict]

    # Expiring contracts
    contracts_expiring_30_days: int
    contracts_expiring_90_days: int

    # Score distribution
    high_score_opportunities: int  # Score >= 70
    medium_score_opportunities: int  # Score 40-69
    low_score_opportunities: int  # Score < 40

    generated_at: datetime


class AgencyAnalysis(BaseModel):
    """Schema for agency analysis."""

    agency_name: str
    sub_agencies: list[str]

    # Award statistics
    total_awards_12mo: int
    total_obligation_12mo: Decimal
    avg_award_size: Decimal

    # Small business
    small_business_percentage: Decimal

    # Active opportunities
    active_opportunities: int

    # Top NAICS codes
    top_naics: list[dict]

    # Top contractors
    top_contractors: list[dict]

    # Upcoming recompetes
    upcoming_recompetes: int
