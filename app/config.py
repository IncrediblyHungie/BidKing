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
    ("541511", "Custom Computer Programming Services"),
    ("541512", "Computer Systems Design Services"),
    ("541519", "Other Computer Related Services"),
    ("518210", "Data Processing, Hosting, and Related Services"),
    ("541690", "Other Scientific and Technical Consulting Services"),
    ("541712", "Research and Development in Physical, Engineering, and Life Sciences"),
    ("541330", "Engineering Services"),
    ("541990", "All Other Professional, Scientific, and Technical Services"),
]
