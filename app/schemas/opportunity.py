"""Opportunity Pydantic schemas."""

from datetime import datetime, date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PointOfContactResponse(BaseModel):
    """Schema for point of contact."""

    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    title: Optional[str]
    type: Optional[str]


class OpportunityResponse(BaseModel):
    """Schema for opportunity response."""

    id: UUID
    notice_id: str
    solicitation_number: Optional[str]
    title: str
    description: Optional[str]

    # Dates
    posted_date: Optional[date]
    response_deadline: Optional[datetime]
    archive_date: Optional[date]

    # Classification
    type: Optional[str]
    type_description: Optional[str]
    naics_code: Optional[str]
    naics_description: Optional[str]
    psc_code: Optional[str]
    psc_description: Optional[str]

    # Agency
    agency_name: Optional[str]
    sub_agency_name: Optional[str]
    office_name: Optional[str]

    # Location
    pop_city: Optional[str]
    pop_state: Optional[str]
    pop_zip: Optional[str]
    pop_country: Optional[str]

    # Set-aside
    set_aside_type: Optional[str]
    set_aside_description: Optional[str]

    # Scoring
    likelihood_score: int

    # Links
    sam_gov_link: Optional[str]

    # Contacts
    points_of_contact: list[PointOfContactResponse] = []

    class Config:
        from_attributes = True


class OpportunityListResponse(BaseModel):
    """Schema for paginated opportunity list."""

    items: list[OpportunityResponse]
    total: int
    page: int
    page_size: int
    pages: int


class OpportunitySearch(BaseModel):
    """Schema for opportunity search/filter."""

    # Text search
    query: Optional[str] = Field(None, max_length=500)

    # Filters
    naics_codes: Optional[list[str]] = None
    psc_codes: Optional[list[str]] = None
    agencies: Optional[list[str]] = None
    states: Optional[list[str]] = None
    set_aside_types: Optional[list[str]] = None

    # Date filters
    posted_after: Optional[date] = None
    posted_before: Optional[date] = None
    deadline_after: Optional[datetime] = None
    deadline_before: Optional[datetime] = None

    # Score filter
    min_score: int = Field(default=0, ge=0, le=100)
    max_score: int = Field(default=100, ge=0, le=100)

    # Pagination
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    # Sorting
    sort_by: str = Field(default="response_deadline")
    sort_order: str = Field(default="asc")


class SavedOpportunityCreate(BaseModel):
    """Schema for saving an opportunity."""

    opportunity_id: UUID
    notes: Optional[str] = Field(None, max_length=5000)
    status: str = Field(default="watching")
    priority: int = Field(default=3, ge=1, le=5)

    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status value."""
        valid = {"watching", "preparing", "submitted", "awarded", "lost", "archived"}
        if v.lower() not in valid:
            raise ValueError(f"Invalid status. Must be one of: {valid}")
        return v.lower()


class SavedOpportunityResponse(BaseModel):
    """Schema for saved opportunity response."""

    id: UUID
    user_id: UUID
    opportunity: OpportunityResponse
    notes: Optional[str]
    status: str
    priority: int
    reminder_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OpportunityStats(BaseModel):
    """Schema for opportunity statistics."""

    total_active: int
    new_today: int
    new_this_week: int
    expiring_soon: int  # Within 7 days
    by_agency: dict[str, int]
    by_naics: dict[str, int]
    by_state: dict[str, int]
    avg_score: float
    score_distribution: dict[str, int]  # e.g., "0-20": 5, "21-40": 10, etc.
