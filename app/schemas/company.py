"""Company Profile and Scoring Pydantic schemas."""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Company Profile Schemas
# =============================================================================

class CompanyProfileCreate(BaseModel):
    """Schema for creating a company profile during onboarding."""

    company_name: str = Field(..., min_length=1, max_length=255)
    uei: Optional[str] = Field(None, max_length=12)
    duns_number: Optional[str] = Field(None, max_length=13)
    cage_code: Optional[str] = Field(None, max_length=5)

    # Business info
    business_size: Optional[str] = Field(None, pattern="^(small|large|other)$")
    employee_count: Optional[int] = Field(None, ge=1)
    annual_revenue: Optional[Decimal] = Field(None, ge=0)

    # Scale preferences
    min_contract_value: Optional[Decimal] = Field(None, ge=0)
    max_contract_value: Optional[Decimal] = Field(None, ge=0)
    typical_contract_size: Optional[str] = Field(None, pattern="^(micro|small|medium|large|enterprise)$")

    # Security clearances
    facility_clearance: Optional[str] = Field(None, pattern="^(None|Confidential|Secret|Top Secret)$")
    has_sci_capability: bool = False

    # Contract type preferences (1-5)
    pref_firm_fixed_price: int = Field(default=3, ge=1, le=5)
    pref_time_materials: int = Field(default=3, ge=1, le=5)
    pref_cost_plus: int = Field(default=3, ge=1, le=5)
    pref_idiq: int = Field(default=3, ge=1, le=5)
    pref_sole_source: int = Field(default=5, ge=1, le=5)

    # Geographic preferences
    headquarters_state: Optional[str] = Field(None, max_length=2)
    geographic_preference: str = Field(default="national", pattern="^(local|regional|national|international)$")
    preferred_states: Optional[List[str]] = None
    willing_to_travel: bool = True

    # Timeline preferences
    min_days_to_respond: int = Field(default=7, ge=1)
    can_rush_proposals: bool = False


class CompanyProfileUpdate(BaseModel):
    """Schema for updating a company profile."""

    company_name: Optional[str] = Field(None, min_length=1, max_length=255)
    uei: Optional[str] = Field(None, max_length=12)
    duns_number: Optional[str] = Field(None, max_length=13)
    cage_code: Optional[str] = Field(None, max_length=5)

    business_size: Optional[str] = Field(None, pattern="^(small|large|other)$")
    employee_count: Optional[int] = Field(None, ge=1)
    annual_revenue: Optional[Decimal] = Field(None, ge=0)

    min_contract_value: Optional[Decimal] = Field(None, ge=0)
    max_contract_value: Optional[Decimal] = Field(None, ge=0)
    typical_contract_size: Optional[str] = Field(None, pattern="^(micro|small|medium|large|enterprise)$")

    facility_clearance: Optional[str] = Field(None, pattern="^(None|Confidential|Secret|Top Secret)$")
    has_sci_capability: Optional[bool] = None

    pref_firm_fixed_price: Optional[int] = Field(None, ge=1, le=5)
    pref_time_materials: Optional[int] = Field(None, ge=1, le=5)
    pref_cost_plus: Optional[int] = Field(None, ge=1, le=5)
    pref_idiq: Optional[int] = Field(None, ge=1, le=5)
    pref_sole_source: Optional[int] = Field(None, ge=1, le=5)

    headquarters_state: Optional[str] = Field(None, max_length=2)
    geographic_preference: Optional[str] = Field(None, pattern="^(local|regional|national|international)$")
    preferred_states: Optional[List[str]] = None
    willing_to_travel: Optional[bool] = None

    min_days_to_respond: Optional[int] = Field(None, ge=1)
    can_rush_proposals: Optional[bool] = None


class CompanyProfileResponse(BaseModel):
    """Schema for company profile response."""

    id: UUID
    user_id: UUID
    company_name: str
    uei: Optional[str]
    duns_number: Optional[str]
    cage_code: Optional[str]

    business_size: Optional[str]
    employee_count: Optional[int]
    annual_revenue: Optional[Decimal]

    min_contract_value: Optional[Decimal]
    max_contract_value: Optional[Decimal]
    typical_contract_size: Optional[str]

    facility_clearance: Optional[str]
    has_sci_capability: bool

    pref_firm_fixed_price: int
    pref_time_materials: int
    pref_cost_plus: int
    pref_idiq: int
    pref_sole_source: int

    headquarters_state: Optional[str]
    geographic_preference: str
    preferred_states: Optional[List[str]]
    willing_to_travel: bool

    min_days_to_respond: int
    can_rush_proposals: bool

    onboarding_completed: bool
    onboarding_step: int
    profile_completeness: int

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# NAICS Code Schemas
# =============================================================================

class CompanyNAICSCreate(BaseModel):
    """Schema for adding a NAICS code to company profile."""

    naics_code: str = Field(..., min_length=2, max_length=6)
    naics_description: Optional[str] = Field(None, max_length=255)
    experience_level: str = Field(default="moderate", pattern="^(none|limited|moderate|extensive|expert)$")
    is_primary: bool = False
    years_experience: Optional[int] = Field(None, ge=0)
    contracts_won: int = Field(default=0, ge=0)


class CompanyNAICSResponse(BaseModel):
    """Schema for NAICS code response."""

    id: UUID
    naics_code: str
    naics_description: Optional[str]
    experience_level: str
    is_primary: bool
    years_experience: Optional[int]
    contracts_won: int
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Certification Schemas
# =============================================================================

class CompanyCertificationCreate(BaseModel):
    """Schema for adding a certification."""

    certification_type: str = Field(..., max_length=100)
    # Common types: 8(a), HUBZone, WOSB, EDWOSB, SDVOSB, VOSB, SDB
    certification_number: Optional[str] = Field(None, max_length=100)
    certifying_agency: Optional[str] = Field(None, max_length=255)
    issue_date: Optional[date] = None
    expiration_date: Optional[date] = None
    is_active: bool = True


class CompanyCertificationResponse(BaseModel):
    """Schema for certification response."""

    id: UUID
    certification_type: str
    certification_number: Optional[str]
    certifying_agency: Optional[str]
    issue_date: Optional[date]
    expiration_date: Optional[date]
    is_active: bool
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Past Performance Schemas
# =============================================================================

class PastPerformanceCreate(BaseModel):
    """Schema for adding past performance record."""

    contract_title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None

    contract_number: Optional[str] = Field(None, max_length=100)
    task_order_number: Optional[str] = Field(None, max_length=100)
    piid: Optional[str] = Field(None, max_length=100)

    agency_name: Optional[str] = Field(None, max_length=255)
    contracting_officer: Optional[str] = Field(None, max_length=255)
    contracting_officer_email: Optional[str] = Field(None, max_length=255)

    naics_code: Optional[str] = Field(None, max_length=6)
    psc_code: Optional[str] = Field(None, max_length=10)

    contract_value: Optional[Decimal] = Field(None, ge=0)
    period_of_performance_months: Optional[int] = Field(None, ge=1)

    start_date: Optional[date] = None
    end_date: Optional[date] = None

    role: str = Field(default="prime", pattern="^(prime|subcontractor|team_member)$")
    performance_rating: Optional[str] = Field(None, pattern="^(exceptional|very_good|satisfactory|marginal|unsatisfactory)$")
    cpars_rating: Optional[str] = None

    contract_type: Optional[str] = Field(None, max_length=50)
    set_aside_type: Optional[str] = Field(None, max_length=100)


class PastPerformanceResponse(BaseModel):
    """Schema for past performance response."""

    id: UUID
    contract_title: str
    description: Optional[str]

    contract_number: Optional[str]
    task_order_number: Optional[str]
    piid: Optional[str]

    agency_name: Optional[str]
    naics_code: Optional[str]

    contract_value: Optional[Decimal]
    period_of_performance_months: Optional[int]

    start_date: Optional[date]
    end_date: Optional[date]

    role: str
    performance_rating: Optional[str]
    contract_type: Optional[str]
    set_aside_type: Optional[str]

    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Onboarding Schemas
# =============================================================================

class OnboardingStepUpdate(BaseModel):
    """Schema for updating onboarding progress."""

    step: int = Field(..., ge=0, le=5)
    # Steps: 0=not started, 1=basic info, 2=naics, 3=certifications, 4=preferences, 5=complete


class OnboardingStatusResponse(BaseModel):
    """Schema for onboarding status response."""

    onboarding_completed: bool
    onboarding_step: int
    profile_completeness: int
    has_profile: bool
    has_naics: bool
    has_certifications: bool


# =============================================================================
# Opportunity Score Schemas
# =============================================================================

class OpportunityScoreResponse(BaseModel):
    """Schema for opportunity score response."""

    opportunity_id: UUID
    overall_score: int

    capability_score: int
    capability_breakdown: Optional[dict]

    eligibility_score: int
    eligibility_breakdown: Optional[dict]

    scale_score: int
    scale_breakdown: Optional[dict]

    win_probability_score: int
    win_probability_breakdown: Optional[dict]

    strategic_score: int
    strategic_breakdown: Optional[dict]

    timeline_score: int
    timeline_breakdown: Optional[dict]

    calculated_at: datetime

    class Config:
        from_attributes = True


class BatchScoreRequest(BaseModel):
    """Schema for batch scoring request."""

    opportunity_ids: List[UUID] = Field(..., min_length=1, max_length=100)


class BatchScoreResponse(BaseModel):
    """Schema for batch scoring response."""

    scores: dict  # {opportunity_id: overall_score}
    count: int


# =============================================================================
# Capability Statement Schemas
# =============================================================================

class CapabilityStatementCreate(BaseModel):
    """Schema for creating a capability statement (manual entry)."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    full_text: Optional[str] = None
    core_competencies: Optional[List[str]] = None
    differentiators: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    target_naics_codes: Optional[List[str]] = None
    target_agencies: Optional[List[str]] = None
    is_default: bool = False


class CapabilityStatementResponse(BaseModel):
    """Schema for capability statement response."""

    id: UUID
    name: str
    description: Optional[str]
    core_competencies: Optional[List[str]]
    differentiators: Optional[List[str]]
    keywords: Optional[List[str]]
    target_naics_codes: Optional[List[str]]
    target_agencies: Optional[List[str]]
    file_url: Optional[str]
    file_name: Optional[str]
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CapabilityStatementAnalysis(BaseModel):
    """Schema for AI-analyzed capability statement data."""

    company_name: Optional[str] = None
    core_competencies: Optional[List[str]] = None
    differentiators: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    target_naics_codes: Optional[List[str]] = None
    target_agencies: Optional[List[str]] = None
    technologies: Optional[List[str]] = None
    certifications_mentioned: Optional[List[str]] = None
    past_performance_summary: Optional[str] = None
    contact_info: Optional[dict] = None
    status: str  # "analyzed", "failed", "skipped"
    error: Optional[str] = None
