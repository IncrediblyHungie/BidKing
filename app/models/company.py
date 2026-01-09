"""
Company Profile & Scoring Models

Models for user company profiles, certifications, past performance,
and opportunity scoring for the personalized scoring system.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Text, Numeric, Date, Float
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.uuid_type import GUID, JSONArray, JSONDict


class CompanyProfile(Base):
    """
    Company profile for personalized opportunity scoring.
    Created during onboarding, updated via settings.
    """

    __tablename__ = "company_profiles"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Link to user (one-to-one)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # ==========================================================================
    # Basic Company Info
    # ==========================================================================

    company_name = Column(String(255), nullable=False)
    duns_number = Column(String(13), nullable=True)  # D-U-N-S number
    uei = Column(String(12), nullable=True, index=True)  # Unique Entity Identifier
    cage_code = Column(String(5), nullable=True)  # Commercial and Government Entity Code

    # ==========================================================================
    # Business Size & Type
    # ==========================================================================

    business_size = Column(String(50), nullable=True)  # small, large, other
    employee_count = Column(Integer, nullable=True)  # Number of employees
    annual_revenue = Column(Numeric(15, 2), nullable=True)  # Annual revenue in dollars

    # ==========================================================================
    # Scale Preferences (for Scale Fit scoring)
    # ==========================================================================

    min_contract_value = Column(Numeric(15, 2), nullable=True)  # Minimum contract value willing to pursue
    max_contract_value = Column(Numeric(15, 2), nullable=True)  # Maximum contract value capable of handling
    typical_contract_size = Column(String(50), nullable=True)  # micro, small, medium, large, enterprise

    # ==========================================================================
    # Security Clearances
    # ==========================================================================

    facility_clearance = Column(String(50), nullable=True)  # None, Confidential, Secret, Top Secret
    has_sci_capability = Column(Boolean, default=False)  # Sensitive Compartmented Information
    clearance_notes = Column(Text, nullable=True)  # Additional clearance details

    # ==========================================================================
    # Contract Type Preferences (1-5 rating, 5 = most preferred)
    # ==========================================================================

    pref_firm_fixed_price = Column(Integer, default=3)  # FFP preference
    pref_time_materials = Column(Integer, default=3)  # T&M preference
    pref_cost_plus = Column(Integer, default=3)  # Cost-Plus preference
    pref_idiq = Column(Integer, default=3)  # IDIQ/BPA preference
    pref_sole_source = Column(Integer, default=5)  # Sole source preference

    # ==========================================================================
    # Geographic Preferences
    # ==========================================================================

    headquarters_state = Column(String(2), nullable=True)  # HQ state code
    geographic_preference = Column(String(50), default="national")  # local, regional, national, international
    preferred_states = Column(JSONArray(), nullable=True)  # List of preferred states
    willing_to_travel = Column(Boolean, default=True)

    # ==========================================================================
    # Timeline Preferences
    # ==========================================================================

    min_days_to_respond = Column(Integer, default=7)  # Minimum days needed to prepare proposal
    can_rush_proposals = Column(Boolean, default=False)  # Can handle short deadlines
    preferred_start_date_buffer = Column(Integer, default=30)  # Days buffer before contract start

    # ==========================================================================
    # Onboarding Progress
    # ==========================================================================

    onboarding_completed = Column(Boolean, default=False)
    onboarding_step = Column(Integer, default=0)  # Current step in onboarding wizard
    profile_completeness = Column(Integer, default=0)  # 0-100 percentage

    # ==========================================================================
    # Timestamps
    # ==========================================================================

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ==========================================================================
    # Relationships
    # ==========================================================================

    user = relationship("User", back_populates="company_profile")
    naics_codes = relationship("CompanyNAICS", back_populates="company_profile", cascade="all, delete-orphan")
    certifications = relationship("CompanyCertification", back_populates="company_profile", cascade="all, delete-orphan")
    past_performances = relationship("PastPerformance", back_populates="company_profile", cascade="all, delete-orphan")
    capability_statements = relationship("CapabilityStatement", back_populates="company_profile", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CompanyProfile {self.company_name}>"

    def calculate_completeness(self) -> int:
        """Calculate profile completeness percentage."""
        fields = [
            self.company_name,
            self.uei,
            self.business_size,
            self.employee_count,
            self.headquarters_state,
            self.facility_clearance,
            self.typical_contract_size,
        ]
        filled = sum(1 for f in fields if f is not None)

        # Check relationships
        has_naics = len(self.naics_codes) > 0 if self.naics_codes else False
        has_certs = len(self.certifications) > 0 if self.certifications else False

        total_items = len(fields) + 2  # +2 for naics and certs
        filled_items = filled + (1 if has_naics else 0) + (1 if has_certs else 0)

        return int((filled_items / total_items) * 100)


class CompanyNAICS(Base):
    """
    NAICS codes associated with a company profile.
    Includes experience level and preference.
    """

    __tablename__ = "company_naics"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Link to company profile
    company_profile_id = Column(GUID(), ForeignKey("company_profiles.id", ondelete="CASCADE"), nullable=False, index=True)

    # NAICS code info
    naics_code = Column(String(6), nullable=False, index=True)
    naics_description = Column(String(255), nullable=True)

    # Experience and preference
    experience_level = Column(String(50), default="moderate")  # none, limited, moderate, extensive, expert
    is_primary = Column(Boolean, default=False)  # Primary NAICS code
    years_experience = Column(Integer, nullable=True)  # Years of experience in this NAICS
    contracts_won = Column(Integer, default=0)  # Number of contracts won in this NAICS

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    company_profile = relationship("CompanyProfile", back_populates="naics_codes")

    def __repr__(self):
        return f"<CompanyNAICS {self.naics_code}>"


class CompanyCertification(Base):
    """
    Certifications and set-aside eligibilities for a company.
    """

    __tablename__ = "company_certifications"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Link to company profile
    company_profile_id = Column(GUID(), ForeignKey("company_profiles.id", ondelete="CASCADE"), nullable=False, index=True)

    # Certification info
    certification_type = Column(String(100), nullable=False, index=True)
    # Types: 8(a), HUBZone, WOSB, EDWOSB, SDVOSB, VOSB, SDB, etc.

    certification_number = Column(String(100), nullable=True)
    certifying_agency = Column(String(255), nullable=True)  # SBA, VA, etc.

    # Dates
    issue_date = Column(Date, nullable=True)
    expiration_date = Column(Date, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)  # Verified via SAM.gov API

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    company_profile = relationship("CompanyProfile", back_populates="certifications")

    def __repr__(self):
        return f"<CompanyCertification {self.certification_type}>"


class PastPerformance(Base):
    """
    Past performance records for scale fit and win probability scoring.
    """

    __tablename__ = "past_performances"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Link to company profile
    company_profile_id = Column(GUID(), ForeignKey("company_profiles.id", ondelete="CASCADE"), nullable=False, index=True)

    # Contract identification
    contract_number = Column(String(100), nullable=True)
    task_order_number = Column(String(100), nullable=True)
    piid = Column(String(100), nullable=True, index=True)  # Procurement Instrument Identifier

    # Contract details
    contract_title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)

    # Client info
    agency_name = Column(String(255), nullable=True, index=True)
    contracting_officer = Column(String(255), nullable=True)
    contracting_officer_email = Column(String(255), nullable=True)

    # Classification
    naics_code = Column(String(6), nullable=True, index=True)
    psc_code = Column(String(10), nullable=True)

    # Value and duration
    contract_value = Column(Numeric(15, 2), nullable=True)  # Total contract value
    period_of_performance_months = Column(Integer, nullable=True)  # Duration in months

    # Dates
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    # Performance
    role = Column(String(50), default="prime")  # prime, subcontractor, team_member
    performance_rating = Column(String(50), nullable=True)  # exceptional, very_good, satisfactory, marginal, unsatisfactory
    cpars_rating = Column(String(50), nullable=True)  # CPARS rating if available

    # Contract type
    contract_type = Column(String(50), nullable=True)  # FFP, T&M, Cost-Plus, IDIQ, etc.
    set_aside_type = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    company_profile = relationship("CompanyProfile", back_populates="past_performances")

    def __repr__(self):
        return f"<PastPerformance {self.contract_title[:50]}>"


class CapabilityStatement(Base):
    """
    Stored capability statements for text matching.
    """

    __tablename__ = "capability_statements"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Link to company profile
    company_profile_id = Column(GUID(), ForeignKey("company_profiles.id", ondelete="CASCADE"), nullable=False, index=True)

    # Statement info
    name = Column(String(255), nullable=False)  # e.g., "General IT Services", "Cybersecurity Focus"
    description = Column(Text, nullable=True)

    # Content
    full_text = Column(Text, nullable=True)  # Full capability statement text
    core_competencies = Column(JSONArray(), nullable=True)  # List of core competencies
    differentiators = Column(JSONArray(), nullable=True)  # List of differentiators
    keywords = Column(JSONArray(), nullable=True)  # Extracted keywords for matching

    # Target focus
    target_naics_codes = Column(JSONArray(), nullable=True)  # NAICS codes this statement targets
    target_agencies = Column(JSONArray(), nullable=True)  # Agencies this statement targets

    # File storage
    file_url = Column(Text, nullable=True)  # URL to uploaded PDF
    file_name = Column(String(255), nullable=True)

    # Status
    is_default = Column(Boolean, default=False)  # Default statement for matching
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    company_profile = relationship("CompanyProfile", back_populates="capability_statements")

    def __repr__(self):
        return f"<CapabilityStatement {self.name}>"


class OpportunityMetadata(Base):
    """
    Pre-extracted metadata from opportunities for efficient scoring.
    Populated during opportunity sync, not per-user.
    """

    __tablename__ = "opportunity_metadata"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Link to opportunity
    opportunity_id = Column(GUID(), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # ==========================================================================
    # Inferred Scale (since SAM.gov doesn't provide dollar values)
    # ==========================================================================

    inferred_scale = Column(String(50), nullable=True)  # micro, small, medium, large, enterprise
    scale_confidence = Column(Float, default=0.5)  # 0-1 confidence in scale inference
    scale_signals = Column(JSONDict(), nullable=True)  # Signals used for inference
    # Example: {"enterprise_keywords": 2, "fte_count": 15, "pop_months": 60, "dollar_mentions": ["$5M"]}

    estimated_min_value = Column(Numeric(15, 2), nullable=True)  # Estimated minimum value
    estimated_max_value = Column(Numeric(15, 2), nullable=True)  # Estimated maximum value

    # ==========================================================================
    # Security Requirements
    # ==========================================================================

    requires_clearance = Column(Boolean, default=False)
    clearance_level = Column(String(50), nullable=True)  # None, Confidential, Secret, Top Secret, TS/SCI
    clearance_signals = Column(JSONArray(), nullable=True)  # Text patterns that indicated clearance
    # Example: ["SECRET clearance required", "TS/SCI"]

    # ==========================================================================
    # Contract Type Detection
    # ==========================================================================

    detected_contract_type = Column(String(50), nullable=True)  # FFP, T&M, Cost-Plus, IDIQ, etc.
    contract_type_confidence = Column(Float, default=0.5)  # 0-1 confidence
    contract_type_signals = Column(JSONArray(), nullable=True)  # Text patterns

    # ==========================================================================
    # Competition Analysis
    # ==========================================================================

    competition_level = Column(String(50), nullable=True)  # full_open, set_aside, sole_source, limited
    incumbent_advantage = Column(Boolean, default=False)  # Appears to favor incumbent
    recompete_indicator = Column(Boolean, default=False)  # Is this a recompete

    # ==========================================================================
    # Keyword Extraction
    # ==========================================================================

    extracted_keywords = Column(JSONArray(), nullable=True)  # Important keywords from description
    technology_stack = Column(JSONArray(), nullable=True)  # Detected technologies
    # Example: ["Python", "AWS", "Kubernetes", "React"]

    # ==========================================================================
    # Processing Status
    # ==========================================================================

    processed_at = Column(DateTime, nullable=True)
    processing_version = Column(Integer, default=1)  # Version of extraction algorithm

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    opportunity = relationship("Opportunity", backref="metadata")

    def __repr__(self):
        return f"<OpportunityMetadata {self.opportunity_id}>"


class OpportunityScore(Base):
    """
    Personalized opportunity scores for each user.
    Cached and invalidated based on profile/opportunity changes.
    """

    __tablename__ = "opportunity_scores"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Links
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    opportunity_id = Column(GUID(), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)

    # ==========================================================================
    # Overall Score
    # ==========================================================================

    overall_score = Column(Integer, default=50, index=True)  # 0-100

    # ==========================================================================
    # Dimension Scores (0-100 each)
    # ==========================================================================

    # Capability Match (25% weight) - NAICS + keywords + capability statement
    capability_score = Column(Integer, default=50)
    capability_breakdown = Column(JSONDict(), nullable=True)
    # Example: {"naics_match": 80, "keyword_match": 60, "capability_text_match": 40}

    # Eligibility (20% weight) - Certifications + set-asides
    eligibility_score = Column(Integer, default=50)
    eligibility_breakdown = Column(JSONDict(), nullable=True)
    # Example: {"set_aside_match": true, "certification_match": ["8(a)", "HUBZone"]}

    # Scale Fit (15% weight) - Contract size vs company capacity
    scale_score = Column(Integer, default=50)
    scale_breakdown = Column(JSONDict(), nullable=True)
    # Example: {"inferred_scale": "medium", "company_fit": "good", "past_performance_match": 75}

    # Win Probability (20% weight) - Competition + incumbent + past performance
    win_probability_score = Column(Integer, default=50)
    win_probability_breakdown = Column(JSONDict(), nullable=True)
    # Example: {"competition_level": "set_aside", "incumbent_advantage": false, "naics_win_rate": 0.35}

    # Strategic Fit (10% weight) - Geography + agency preference
    strategic_score = Column(Integer, default=50)
    strategic_breakdown = Column(JSONDict(), nullable=True)
    # Example: {"geographic_match": true, "agency_history": "none", "growth_area": true}

    # Timeline (10% weight) - Response deadline feasibility
    timeline_score = Column(Integer, default=50)
    timeline_breakdown = Column(JSONDict(), nullable=True)
    # Example: {"days_to_deadline": 21, "meets_minimum": true, "rush_required": false}

    # ==========================================================================
    # Score Metadata
    # ==========================================================================

    score_version = Column(Integer, default=1)  # Algorithm version used
    is_stale = Column(Boolean, default=False)  # Needs recalculation
    stale_reason = Column(String(255), nullable=True)  # Why it's stale

    # ==========================================================================
    # Timestamps
    # ==========================================================================

    calculated_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint: one score per user per opportunity
    __table_args__ = (
        # Create composite index for efficient lookups
        # Index('ix_opportunity_scores_user_opp', 'user_id', 'opportunity_id'),
    )

    def __repr__(self):
        return f"<OpportunityScore user={self.user_id} opp={self.opportunity_id} score={self.overall_score}>"


class OpportunityDecision(Base):
    """
    User decisions on opportunities - for improving scoring over time.
    """

    __tablename__ = "opportunity_decisions"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Links
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    opportunity_id = Column(GUID(), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)

    # Decision
    decision = Column(String(50), nullable=False, index=True)
    # Values: pursuing, watching, not_interested, bid_submitted, won, lost, no_bid

    # Feedback
    decision_reason = Column(Text, nullable=True)  # Why they made this decision
    score_feedback = Column(String(50), nullable=True)  # too_high, accurate, too_low

    # Score at time of decision (for tracking accuracy)
    score_at_decision = Column(Integer, nullable=True)

    # Timestamps
    decided_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<OpportunityDecision {self.decision}>"
