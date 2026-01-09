"""Pydantic schemas for API request/response validation."""

from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserLogin,
    Token,
    TokenRefresh,
)
from app.schemas.alert_profile import (
    AlertProfileCreate,
    AlertProfileUpdate,
    AlertProfileResponse,
)
from app.schemas.opportunity import (
    OpportunityResponse,
    OpportunityListResponse,
    OpportunitySearch,
    SavedOpportunityCreate,
)
from app.schemas.subscription import (
    SubscriptionResponse,
    SubscriptionCreate,
    UsageResponse,
)
from app.schemas.market_data import (
    NAICSStatisticsResponse,
    LaborRateRequest,
    LaborRateResponse,
    CompetitorResponse,
    RecompeteResponse,
)
from app.schemas.company import (
    CompanyProfileCreate,
    CompanyProfileUpdate,
    CompanyProfileResponse,
    CompanyNAICSCreate,
    CompanyNAICSResponse,
    CompanyCertificationCreate,
    CompanyCertificationResponse,
    PastPerformanceCreate,
    PastPerformanceResponse,
    OnboardingStatusResponse,
    OpportunityScoreResponse,
)
from app.schemas.saved_search import (
    SavedSearchCreate,
    SavedSearchUpdate,
    SavedSearchResponse,
)

__all__ = [
    # User
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserLogin",
    "Token",
    "TokenRefresh",
    # Alert Profile
    "AlertProfileCreate",
    "AlertProfileUpdate",
    "AlertProfileResponse",
    # Opportunity
    "OpportunityResponse",
    "OpportunityListResponse",
    "OpportunitySearch",
    "SavedOpportunityCreate",
    # Subscription
    "SubscriptionResponse",
    "SubscriptionCreate",
    "UsageResponse",
    # Market Data
    "NAICSStatisticsResponse",
    "LaborRateRequest",
    "LaborRateResponse",
    "CompetitorResponse",
    "RecompeteResponse",
    # Company Profile & Scoring
    "CompanyProfileCreate",
    "CompanyProfileUpdate",
    "CompanyProfileResponse",
    "CompanyNAICSCreate",
    "CompanyNAICSResponse",
    "CompanyCertificationCreate",
    "CompanyCertificationResponse",
    "PastPerformanceCreate",
    "PastPerformanceResponse",
    "OnboardingStatusResponse",
    "OpportunityScoreResponse",
    # Saved Search
    "SavedSearchCreate",
    "SavedSearchUpdate",
    "SavedSearchResponse",
]
