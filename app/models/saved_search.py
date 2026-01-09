"""
Saved Search Model

User-saved filter combinations for quick opportunity search reloading.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.uuid_type import GUID, JSONArray


class SavedSearch(Base):
    """Saved search configuration for quick filter reloading."""

    __tablename__ = "saved_searches"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # User relationship
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Search info
    name = Column(String(255), nullable=False)
    is_default = Column(Boolean, default=False)

    # ==========================================================================
    # Filter Criteria (mirrors OpportunitiesList filters)
    # ==========================================================================

    # Text search
    search_query = Column(String(500), nullable=True)

    # NAICS codes
    naics_codes = Column(JSONArray(), nullable=True)

    # Agencies
    agencies = Column(JSONArray(), nullable=True)

    # States
    states = Column(JSONArray(), nullable=True)

    # Set-aside types
    set_aside_types = Column(JSONArray(), nullable=True)

    # Notice types
    notice_types = Column(JSONArray(), nullable=True)

    # Value range
    min_value = Column(Numeric(15, 2), nullable=True)
    max_value = Column(Numeric(15, 2), nullable=True)

    # AI analysis filter
    has_ai_analysis = Column(String(10), default="all")  # all, yes, no

    # Value estimate filter
    has_value_estimate = Column(String(10), default="all")  # all, yes, no

    # Early stage only (presolicitation, sources sought)
    early_stage_only = Column(Boolean, default=False)

    # Sorting
    sort_by = Column(String(50), default="response_deadline")
    sort_order = Column(String(10), default="asc")

    # ==========================================================================
    # Usage Statistics
    # ==========================================================================

    # Number of times this search has been used
    use_count = Column(Integer, default=0)

    # Last time this search was used
    last_used_at = Column(DateTime, nullable=True)

    # ==========================================================================
    # Timestamps
    # ==========================================================================

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ==========================================================================
    # Relationships
    # ==========================================================================

    user = relationship("User", back_populates="saved_searches")

    def __repr__(self):
        return f"<SavedSearch {self.name}>"

    def to_filters_dict(self) -> dict:
        """Convert to filters dictionary for frontend."""
        return {
            "search_query": self.search_query,
            "naics_codes": self.naics_codes or [],
            "agencies": self.agencies or [],
            "states": self.states or [],
            "set_aside_types": self.set_aside_types or [],
            "notice_types": self.notice_types or [],
            "min_value": float(self.min_value) if self.min_value else None,
            "max_value": float(self.max_value) if self.max_value else None,
            "has_ai_analysis": self.has_ai_analysis,
            "has_value_estimate": self.has_value_estimate,
            "early_stage_only": self.early_stage_only,
            "sort_by": self.sort_by,
            "sort_order": self.sort_order,
        }
