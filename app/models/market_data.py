"""
Market Data Models

USAspending awards, NAICS statistics, labor rates, and competitor data.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, Numeric, Date

from app.database import Base
from app.utils.uuid_type import GUID, JSONArray, JSONDict


class ContractAward(Base):
    """Contract award data from USAspending.gov."""

    __tablename__ = "contract_awards"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Award identification
    award_id = Column(String(100), unique=True, nullable=False, index=True)
    piid = Column(String(50), nullable=True, index=True)  # Contract number
    parent_piid = Column(String(50), nullable=True)
    fain = Column(String(50), nullable=True)  # Federal Award ID (grants)

    # Award details
    award_type = Column(String(20), nullable=False)  # contract, grant, loan
    award_type_description = Column(String(100), nullable=True)
    total_obligation = Column(Numeric(15, 2), nullable=True)
    base_and_all_options_value = Column(Numeric(15, 2), nullable=True)
    award_date = Column(Date, nullable=True, index=True)
    period_of_performance_start = Column(Date, nullable=True)
    period_of_performance_end = Column(Date, nullable=True, index=True)

    # Classification
    naics_code = Column(String(6), nullable=True, index=True)
    naics_description = Column(String(255), nullable=True)
    psc_code = Column(String(10), nullable=True, index=True)
    psc_description = Column(String(255), nullable=True)

    # Awarding agency
    awarding_agency_code = Column(String(10), nullable=True)
    awarding_agency_name = Column(String(255), nullable=True, index=True)
    awarding_sub_agency_code = Column(String(10), nullable=True)
    awarding_sub_agency_name = Column(String(255), nullable=True)
    awarding_office_code = Column(String(20), nullable=True)
    awarding_office_name = Column(String(255), nullable=True)

    # Funding agency
    funding_agency_code = Column(String(10), nullable=True)
    funding_agency_name = Column(String(255), nullable=True)

    # Recipient (winner)
    recipient_uei = Column(String(12), nullable=True, index=True)
    recipient_name = Column(String(255), nullable=True)
    recipient_parent_uei = Column(String(12), nullable=True)
    recipient_parent_name = Column(String(255), nullable=True)
    recipient_city = Column(String(100), nullable=True)
    recipient_state = Column(String(2), nullable=True)
    recipient_zip = Column(String(10), nullable=True)
    recipient_country = Column(String(3), nullable=True)

    # Business characteristics
    business_types = Column(JSONArray(), nullable=True)

    # Place of performance
    pop_city = Column(String(100), nullable=True)
    pop_state = Column(String(2), nullable=True, index=True)
    pop_zip = Column(String(10), nullable=True)
    pop_country = Column(String(3), nullable=True)
    pop_congressional_district = Column(String(5), nullable=True)

    # Competition info
    competition_type = Column(String(50), nullable=True)
    number_of_offers = Column(Integer, nullable=True)
    set_aside_type = Column(String(50), nullable=True)

    # Metadata
    last_modified_date = Column(DateTime, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    # Raw data
    raw_data = Column(JSONDict(), nullable=True)

    def __repr__(self):
        return f"<ContractAward {self.award_id}>"


class NAICSStatistics(Base):
    """Aggregated statistics for NAICS codes."""

    __tablename__ = "naics_statistics"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # NAICS identification
    naics_code = Column(String(6), unique=True, nullable=False, index=True)
    naics_description = Column(String(255), nullable=True)

    # Award statistics (last 12 months)
    total_awards_12mo = Column(Integer, default=0)
    total_obligation_12mo = Column(Numeric(15, 2), default=0)
    avg_award_amount_12mo = Column(Numeric(15, 2), default=0)
    median_award_amount_12mo = Column(Numeric(15, 2), default=0)
    min_award_amount_12mo = Column(Numeric(15, 2), default=0)
    max_award_amount_12mo = Column(Numeric(15, 2), default=0)

    # Awards by size bucket
    awards_under_25k = Column(Integer, default=0)
    awards_25k_to_100k = Column(Integer, default=0)
    awards_100k_to_250k = Column(Integer, default=0)
    awards_250k_to_1m = Column(Integer, default=0)
    awards_over_1m = Column(Integer, default=0)

    # Small business statistics
    small_business_awards = Column(Integer, default=0)
    small_business_percentage = Column(Numeric(5, 2), default=0)

    # Competition statistics
    avg_offers_received = Column(Numeric(4, 1), default=0)
    sole_source_percentage = Column(Numeric(5, 2), default=0)

    # Top data (JSON arrays)
    top_agencies = Column(JSONDict(), nullable=True)
    top_recipients = Column(JSONDict(), nullable=True)

    # Recompete pipeline
    contracts_expiring_90_days = Column(Integer, default=0)
    contracts_expiring_180_days = Column(Integer, default=0)
    contracts_expiring_365_days = Column(Integer, default=0)

    # Metadata
    calculated_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<NAICSStatistics {self.naics_code}>"


class Recipient(Base):
    """Contractor/recipient profiles."""

    __tablename__ = "recipients"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Identification
    uei = Column(String(12), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)

    # Parent company
    parent_uei = Column(String(12), nullable=True)
    parent_name = Column(String(255), nullable=True)

    # Location
    city = Column(String(100), nullable=True)
    state = Column(String(2), nullable=True, index=True)
    zip = Column(String(10), nullable=True)
    country = Column(String(3), default="USA")

    # Business types
    business_types = Column(JSONArray(), nullable=True)
    is_small_business = Column(Boolean, default=False)

    # Award statistics
    total_awards = Column(Integer, default=0)
    total_obligation = Column(Numeric(15, 2), default=0)
    first_award_date = Column(Date, nullable=True)
    last_award_date = Column(Date, nullable=True)

    # NAICS expertise
    primary_naics_codes = Column(JSONArray(), nullable=True)

    # Top agencies
    top_agencies = Column(JSONDict(), nullable=True)

    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Recipient {self.name}>"


class RecompeteOpportunity(Base):
    """Contracts expiring soon (recompete opportunities)."""

    __tablename__ = "recompete_opportunities"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Source award reference
    award_id = Column(String(100), unique=True, nullable=False, index=True)
    piid = Column(String(50), nullable=False)

    # Expiration tracking
    period_of_performance_end = Column(Date, nullable=False, index=True)

    # Award details
    naics_code = Column(String(6), nullable=True, index=True)
    total_value = Column(Numeric(15, 2), nullable=True)
    awarding_agency_name = Column(String(255), nullable=True)

    # Incumbent
    incumbent_name = Column(String(255), nullable=True)
    incumbent_uei = Column(String(12), nullable=True)

    # Competition info
    set_aside_type = Column(String(50), nullable=True)

    # Tracking status
    status = Column(String(20), default="upcoming")
    # Status: upcoming, rfp_expected, rfp_posted, awarded

    # Link to SAM.gov opportunity when posted
    linked_opportunity_id = Column(String(100), nullable=True)

    # User tracking (stored as JSON array of UUID strings)
    watching_users = Column(JSONArray(), nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<RecompeteOpportunity {self.piid}>"


class LaborRateCache(Base):
    """Cached labor rate statistics from CALC API."""

    __tablename__ = "labor_rate_cache"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Search key
    search_query = Column(String(255), nullable=False, index=True)
    experience_min = Column(Integer, nullable=True)
    experience_max = Column(Integer, nullable=True)
    education_level = Column(String(50), nullable=True)

    # Cached statistics
    match_count = Column(Integer, default=0)
    min_rate = Column(Numeric(8, 2), nullable=True)
    max_rate = Column(Numeric(8, 2), nullable=True)
    avg_rate = Column(Numeric(8, 2), nullable=True)
    median_rate = Column(Numeric(8, 2), nullable=True)
    percentile_25 = Column(Numeric(8, 2), nullable=True)
    percentile_75 = Column(Numeric(8, 2), nullable=True)

    # Sample data
    sample_categories = Column(JSONDict(), nullable=True)

    # Cache metadata
    cached_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<LaborRateCache {self.search_query}>"


class CommonJobTitle(Base):
    """Common IT job titles for CALC lookups."""

    __tablename__ = "common_job_titles"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # User-friendly title
    display_title = Column(String(255), nullable=False, unique=True)

    # CALC search variations (stored as JSON array of strings)
    calc_search_terms = Column(JSONArray(), nullable=False)

    # Category
    category = Column(String(50), nullable=True)

    # Typical requirements
    typical_experience_min = Column(Integer, nullable=True)
    typical_experience_max = Column(Integer, nullable=True)
    typical_education = Column(String(50), nullable=True)

    # Active
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<CommonJobTitle {self.display_title}>"
