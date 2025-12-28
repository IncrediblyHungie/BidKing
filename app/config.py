"""
BidKing Configuration

Loads settings from environment variables with validation.
"""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ==========================================================================
    # Application
    # ==========================================================================
    app_name: str = "BidKing"
    app_env: str = "development"
    app_url: str = "http://localhost:8000"
    debug: bool = True

    # ==========================================================================
    # Database
    # ==========================================================================
    database_url: str = "postgresql://bidking:bidking@localhost:5432/bidking"

    # ==========================================================================
    # Redis
    # ==========================================================================
    redis_url: str = "redis://localhost:6379/0"

    # ==========================================================================
    # Celery
    # ==========================================================================
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ==========================================================================
    # Security
    # ==========================================================================
    secret_key: str = "change-this-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ==========================================================================
    # Supabase
    # ==========================================================================
    supabase_url: str = "https://kihbcuxmlpzjbcrxirkq.supabase.co"
    supabase_jwt_secret: str = ""  # Get from Supabase dashboard Settings > API > JWT Secret

    # ==========================================================================
    # SAM.gov API
    # ==========================================================================
    sam_gov_api_key: str = ""
    sam_gov_base_url: str = "https://api.sam.gov/opportunities/v2"

    # ==========================================================================
    # USAspending API
    # ==========================================================================
    usaspending_base_url: str = "https://api.usaspending.gov/api/v2"

    # ==========================================================================
    # CALC API
    # ==========================================================================
    calc_base_url: str = "https://api.gsa.gov/acquisition/calc/v3/api"

    # ==========================================================================
    # Stripe
    # ==========================================================================
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_starter_monthly: str = ""
    stripe_price_starter_yearly: str = ""
    stripe_price_pro_monthly: str = ""
    stripe_price_pro_yearly: str = ""

    # ==========================================================================
    # Anthropic (Claude AI)
    # ==========================================================================
    anthropic_api_key: str = ""

    # ==========================================================================
    # Resend (Email)
    # ==========================================================================
    resend_api_key: str = ""
    from_email: str = "alerts@bidking.com"
    from_name: str = "BidKing"

    # ==========================================================================
    # CORS
    # ==========================================================================
    cors_origins: str = "*"

    # ==========================================================================
    # Rate Limiting
    # ==========================================================================
    rate_limit_per_minute: int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience access
settings = get_settings()


# =============================================================================
# Subscription Tier Configuration
# =============================================================================

SUBSCRIPTION_TIERS = {
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "price_yearly": 0,
        "stripe_price_monthly": None,
        "stripe_price_yearly": None,
        "limits": {
            "alert_profiles": 1,
            "alerts_per_month": 10,
            "naics_codes_per_profile": 3,
            "keywords_per_profile": 5,
            "states_per_profile": 1,
            "api_calls_per_hour": 100,
        },
        "features": {
            "instant_alerts": False,
            "daily_digest": True,
            "weekly_digest": True,
            "email_alerts": True,
            "sms_alerts": False,
            "labor_pricing": False,
            "recompete_tracking": False,
            "api_access": False,
            "export_csv": False,
            "saved_opportunities": 10,
        },
    },
    "starter": {
        "name": "Starter",
        "price_monthly": 29,
        "price_yearly": 290,
        "stripe_price_monthly": "stripe_price_starter_monthly",
        "stripe_price_yearly": "stripe_price_starter_yearly",
        "limits": {
            "alert_profiles": 5,
            "alerts_per_month": 100,
            "naics_codes_per_profile": 10,
            "keywords_per_profile": 20,
            "states_per_profile": 10,
            "api_calls_per_hour": 500,
        },
        "features": {
            "instant_alerts": True,
            "daily_digest": True,
            "weekly_digest": True,
            "email_alerts": True,
            "sms_alerts": False,
            "labor_pricing": True,
            "recompete_tracking": False,
            "api_access": False,
            "export_csv": True,
            "saved_opportunities": 100,
        },
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 79,
        "price_yearly": 790,
        "stripe_price_monthly": "stripe_price_pro_monthly",
        "stripe_price_yearly": "stripe_price_pro_yearly",
        "limits": {
            "alert_profiles": 20,
            "alerts_per_month": 500,
            "naics_codes_per_profile": 50,
            "keywords_per_profile": 100,
            "states_per_profile": 50,
            "api_calls_per_hour": 2000,
        },
        "features": {
            "instant_alerts": True,
            "daily_digest": True,
            "weekly_digest": True,
            "email_alerts": True,
            "sms_alerts": True,
            "labor_pricing": True,
            "recompete_tracking": True,
            "api_access": True,
            "export_csv": True,
            "saved_opportunities": 1000,
        },
    },
}


# =============================================================================
# NAICS Codes Configuration
# =============================================================================

RECOMMENDED_NAICS_CODES = [
    # Primary IT/Data codes (high volume)
    ("541511", "Custom Computer Programming Services"),
    ("541512", "Computer Systems Design Services"),
    ("541519", "Other Computer Related Services"),
    ("518210", "Data Processing, Hosting, and Related Services"),
    ("541690", "Other Scientific and Technical Consulting Services"),
    # Adjacent markets (lower competition, underserved)
    ("541611", "Administrative Management and General Management Consulting"),
    ("519190", "All Other Information Services"),
    ("611430", "Professional and Management Development Training"),
    ("541910", "Marketing Research and Public Opinion Polling"),
    ("541618", "Other Management Consulting Services"),
]

# Low competition NAICS codes (avg ~1.0 bids per solicitation in FY2024)
# Source: Squared Compass analysis of FPDS data
LOW_COMPETITION_NAICS = [
    ("531190", "Lessors of Other Real Estate Property", 1.0),
    ("424320", "Men's & Boys' Clothing Wholesalers", 1.0),
    ("621610", "Home Health Care Services", 1.0),
    ("333997", "Scale and Balance Manufacturing", 1.0),
    ("334614", "Software & Pre-Recorded Media Manufacturing", 1.0),
    ("453210", "Office Supplies & Stationery Stores", 1.01),
    ("532283", "Home Health Equipment Rental", 1.05),
    ("623110", "Nursing Care Facilities", 1.05),
    ("624310", "Vocational Rehabilitation Services", 1.06),
    ("621991", "Blood and Organ Banks", 1.07),
]
