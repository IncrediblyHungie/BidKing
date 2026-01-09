"""Saved Search Pydantic schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SavedSearchCreate(BaseModel):
    """Schema for creating a saved search."""

    name: str = Field(..., min_length=1, max_length=255)
    is_default: bool = False

    # Filter criteria
    search_query: Optional[str] = Field(None, max_length=500)
    naics_codes: Optional[list[str]] = None
    agencies: Optional[list[str]] = None
    states: Optional[list[str]] = None
    set_aside_types: Optional[list[str]] = None
    notice_types: Optional[list[str]] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    has_ai_analysis: str = Field(default="all")
    has_value_estimate: str = Field(default="all")
    early_stage_only: bool = False
    sort_by: str = Field(default="response_deadline")
    sort_order: str = Field(default="asc")


class SavedSearchUpdate(BaseModel):
    """Schema for updating a saved search."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_default: Optional[bool] = None

    # Filter criteria
    search_query: Optional[str] = Field(None, max_length=500)
    naics_codes: Optional[list[str]] = None
    agencies: Optional[list[str]] = None
    states: Optional[list[str]] = None
    set_aside_types: Optional[list[str]] = None
    notice_types: Optional[list[str]] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    has_ai_analysis: Optional[str] = None
    has_value_estimate: Optional[str] = None
    early_stage_only: Optional[bool] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = None


class SavedSearchFilters(BaseModel):
    """Schema for the filters contained in a saved search."""

    search_query: Optional[str] = None
    naics_codes: list[str] = []
    agencies: list[str] = []
    states: list[str] = []
    set_aside_types: list[str] = []
    notice_types: list[str] = []
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    has_ai_analysis: str = "all"
    has_value_estimate: str = "all"
    early_stage_only: bool = False
    sort_by: str = "response_deadline"
    sort_order: str = "asc"


class SavedSearchResponse(BaseModel):
    """Schema for saved search response."""

    id: UUID
    user_id: UUID
    name: str
    is_default: bool

    # Filter criteria
    search_query: Optional[str] = None
    naics_codes: Optional[list[str]] = None
    agencies: Optional[list[str]] = None
    states: Optional[list[str]] = None
    set_aside_types: Optional[list[str]] = None
    notice_types: Optional[list[str]] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    has_ai_analysis: str = "all"
    has_value_estimate: str = "all"
    early_stage_only: bool = False
    sort_by: str = "response_deadline"
    sort_order: str = "asc"

    # Usage statistics
    use_count: int = 0
    last_used_at: Optional[datetime] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
