"""Alert profile Pydantic schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AlertProfileCreate(BaseModel):
    """Schema for creating an alert profile."""

    name: str = Field(..., min_length=1, max_length=100)

    # Filters
    naics_codes: Optional[list[str]] = Field(default_factory=list)
    psc_codes: Optional[list[str]] = Field(default_factory=list)
    keywords: Optional[list[str]] = Field(default_factory=list)
    excluded_keywords: Optional[list[str]] = Field(default_factory=list)
    agencies: Optional[list[str]] = Field(default_factory=list)
    states: Optional[list[str]] = Field(default_factory=list)
    set_aside_types: Optional[list[str]] = Field(default_factory=list)

    # Scoring filters
    min_likelihood_score: int = Field(default=40, ge=0, le=100)

    # Alert settings
    alert_frequency: str = Field(default="daily")
    is_active: bool = True

    @field_validator("naics_codes")
    @classmethod
    def validate_naics(cls, v: list[str]) -> list[str]:
        """Validate NAICS codes are 2-6 digits."""
        for code in v:
            if not code.isdigit() or not (2 <= len(code) <= 6):
                raise ValueError(f"Invalid NAICS code: {code}. Must be 2-6 digits.")
        return v

    @field_validator("states")
    @classmethod
    def validate_states(cls, v: list[str]) -> list[str]:
        """Validate state codes are 2 letters."""
        valid_states = {
            "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
            "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
            "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
            "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
            "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
            "DC", "PR", "VI", "GU", "AS", "MP",
        }
        for state in v:
            if state.upper() not in valid_states:
                raise ValueError(f"Invalid state code: {state}")
        return [s.upper() for s in v]

    @field_validator("alert_frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        """Validate alert frequency."""
        valid = {"realtime", "daily", "weekly"}
        if v.lower() not in valid:
            raise ValueError(f"Invalid frequency. Must be one of: {valid}")
        return v.lower()


class AlertProfileUpdate(BaseModel):
    """Schema for updating an alert profile."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    naics_codes: Optional[list[str]] = None
    psc_codes: Optional[list[str]] = None
    keywords: Optional[list[str]] = None
    excluded_keywords: Optional[list[str]] = None
    agencies: Optional[list[str]] = None
    states: Optional[list[str]] = None
    set_aside_types: Optional[list[str]] = None
    min_likelihood_score: Optional[int] = Field(None, ge=0, le=100)
    alert_frequency: Optional[str] = None
    is_active: Optional[bool] = None


class AlertProfileResponse(BaseModel):
    """Schema for alert profile response."""

    id: UUID
    user_id: UUID
    name: str
    naics_codes: list[str]
    psc_codes: list[str]
    keywords: list[str]
    excluded_keywords: list[str]
    agencies: list[str]
    states: list[str]
    set_aside_types: list[str]
    min_likelihood_score: int
    alert_frequency: str
    is_active: bool
    last_alert_sent: Optional[datetime]
    match_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AlertProfileStats(BaseModel):
    """Schema for alert profile statistics."""

    profile_id: UUID
    profile_name: str
    total_matches: int
    matches_this_week: int
    matches_this_month: int
    avg_score: float
    top_agencies: list[str]
