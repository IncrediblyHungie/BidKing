"""Opportunity Pydantic schemas."""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field


class PointOfContactResponse(BaseModel):
    """Schema for point of contact."""

    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    title: Optional[str] = None
    type: Optional[str] = None

    class Config:
        from_attributes = True


class OpportunityAttachmentResponse(BaseModel):
    """Schema for opportunity attachment/link."""

    id: UUID
    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    resource_type: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    posted_date: Optional[datetime] = None

    # Text extraction fields
    text_content: Optional[str] = None
    extraction_status: Optional[str] = None
    extracted_at: Optional[datetime] = None
    extraction_error: Optional[str] = None

    # AI summarization fields
    ai_summary: Optional[dict] = None
    ai_summary_status: Optional[str] = None
    ai_summarized_at: Optional[datetime] = None
    ai_summary_error: Optional[str] = None

    class Config:
        from_attributes = True


class OpportunityHistoryResponse(BaseModel):
    """Schema for opportunity history entry."""

    id: UUID
    action: str
    changed_at: datetime
    description: Optional[str] = None

    class Config:
        from_attributes = True


class OpportunityResponse(BaseModel):
    """Schema for opportunity response."""

    id: UUID
    notice_id: str
    solicitation_number: Optional[str] = None
    title: str
    description: Optional[str] = None

    # Dates
    posted_date: Optional[date] = None
    original_published_date: Optional[datetime] = None
    response_deadline: Optional[datetime] = None
    archive_date: Optional[date] = None
    original_inactive_date: Optional[date] = None
    inactive_policy: Optional[str] = None

    # Classification
    notice_type: Optional[str] = None
    related_notice_id: Optional[str] = None
    naics_code: Optional[str] = None
    naics_description: Optional[str] = None
    psc_code: Optional[str] = None
    psc_description: Optional[str] = None

    # Agency
    department_name: Optional[str] = None
    sub_tier: Optional[str] = None
    agency_name: Optional[str] = None
    office_name: Optional[str] = None
    contracting_office_address: Optional[dict[str, Any]] = None

    # Location (Place of Performance)
    pop_city: Optional[str] = None
    pop_state: Optional[str] = None
    pop_zip: Optional[str] = None
    pop_country: Optional[str] = None

    # Set-aside
    set_aside_type: Optional[str] = None
    set_aside_description: Optional[str] = None

    # Contract Details
    contract_type: Optional[str] = None
    authority: Optional[str] = None
    initiative: Optional[str] = None

    # Award Information
    award_number: Optional[str] = None
    task_delivery_order_number: Optional[str] = None
    modification_number: Optional[str] = None
    award_amount: Optional[Decimal] = None
    award_date: Optional[date] = None
    awardee_name: Optional[str] = None
    awardee_uei: Optional[str] = None

    # AI Estimated Value
    ai_estimated_value_low: Optional[Decimal] = None
    ai_estimated_value_high: Optional[Decimal] = None
    ai_estimated_value_basis: Optional[str] = None

    # Scoring
    likelihood_score: int = 50

    # Links
    ui_link: Optional[str] = None

    # Status
    status: Optional[str] = None

    # Relationships
    points_of_contact: list[PointOfContactResponse] = []
    attachments: list[OpportunityAttachmentResponse] = []
    history: list[OpportunityHistoryResponse] = []

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


VALID_PIPELINE_STATUSES = {"watching", "researching", "preparing", "submitted", "won", "lost", "archived"}


class SavedOpportunityCreate(BaseModel):
    """Schema for saving an opportunity."""

    opportunity_id: UUID
    notes: Optional[str] = Field(None, max_length=5000)
    status: str = Field(default="watching")
    priority: int = Field(default=3, ge=1, le=5)

    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status value."""
        if v.lower() not in VALID_PIPELINE_STATUSES:
            raise ValueError(f"Invalid status. Must be one of: {VALID_PIPELINE_STATUSES}")
        return v.lower()


class SavedOpportunityUpdate(BaseModel):
    """Schema for updating a saved opportunity."""

    status: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=5000)
    priority: Optional[int] = Field(None, ge=1, le=5)
    reminder_date: Optional[date] = None

    # Win tracking (when status = 'won')
    win_amount: Optional[Decimal] = None
    win_date: Optional[date] = None

    # Loss tracking (when status = 'lost')
    winner_name: Optional[str] = Field(None, max_length=255)
    loss_reason: Optional[str] = Field(None, max_length=2000)

    # Feedback notes (for win or loss - lessons learned)
    feedback_notes: Optional[str] = Field(None, max_length=5000)

    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate status value."""
        if v is None:
            return None
        if v.lower() not in VALID_PIPELINE_STATUSES:
            raise ValueError(f"Invalid status. Must be one of: {VALID_PIPELINE_STATUSES}")
        return v.lower()


class SavedOpportunityResponse(BaseModel):
    """Schema for saved opportunity response."""

    id: UUID
    user_id: UUID
    opportunity: OpportunityResponse
    notes: Optional[str] = None
    status: str
    priority: int = 3
    reminder_date: Optional[date] = None
    stage_changed_at: Optional[datetime] = None

    # Win tracking
    win_amount: Optional[Decimal] = None
    win_date: Optional[date] = None

    # Loss tracking
    winner_name: Optional[str] = None
    loss_reason: Optional[str] = None

    # Feedback notes
    feedback_notes: Optional[str] = None

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
