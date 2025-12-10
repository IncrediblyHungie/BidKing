"""
Alert Profile Model

User-configured alert criteria for opportunity matching.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Text, Numeric
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.uuid_type import GUID, JSONArray


class AlertProfile(Base):
    """Alert profile configuration for opportunity matching."""

    __tablename__ = "alert_profiles"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # User relationship
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Profile info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    # ==========================================================================
    # Matching Criteria
    # ==========================================================================

    # NAICS codes (e.g., ['541511', '541512'])
    naics_codes = Column(JSONArray(), nullable=True)

    # PSC codes (Product Service Codes)
    psc_codes = Column(JSONArray(), nullable=True)

    # Keywords to match in title/description
    keywords = Column(JSONArray(), nullable=True)

    # Keywords to exclude
    excluded_keywords = Column(JSONArray(), nullable=True)

    # ==========================================================================
    # Geographic Filters
    # ==========================================================================

    # State codes (e.g., ['CA', 'TX', 'NY'])
    states = Column(JSONArray(), nullable=True)

    # Country codes (default USA)
    countries = Column(JSONArray(), nullable=True)

    # ==========================================================================
    # Contract Type Filters
    # ==========================================================================

    # Set-aside types (e.g., ['SBA', 'WOSB', '8(a)'])
    set_aside_types = Column(JSONArray(), nullable=True)

    # Notice types (e.g., ['Solicitation', 'Sources Sought', 'Award Notice'])
    notice_types = Column(JSONArray(), nullable=True)

    # Minimum likelihood score (0-100)
    min_score = Column(Integer, default=0)

    # ==========================================================================
    # Dollar Amount Filters
    # ==========================================================================

    # Minimum contract value estimate
    min_value = Column(Numeric(15, 2), nullable=True)

    # Maximum contract value estimate (e.g., 100000 for <$100K)
    max_value = Column(Numeric(15, 2), nullable=True)

    # ==========================================================================
    # Agency Filters
    # ==========================================================================

    # Specific agencies to include
    agencies = Column(JSONArray(), nullable=True)

    # Agencies to exclude
    excluded_agencies = Column(JSONArray(), nullable=True)

    # ==========================================================================
    # Delivery Preferences
    # ==========================================================================

    # Alert frequency: instant, daily, weekly
    alert_frequency = Column(String(20), default="daily")

    # Override email (if different from account email)
    alert_email = Column(String(255), nullable=True)

    # SMS number for Pro tier
    alert_sms = Column(String(20), nullable=True)

    # ==========================================================================
    # Statistics
    # ==========================================================================

    # Total matches found
    total_matches = Column(Integer, default=0)

    # Last time this profile matched an opportunity
    last_match_at = Column(DateTime, nullable=True)

    # ==========================================================================
    # Timestamps
    # ==========================================================================

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ==========================================================================
    # Relationships
    # ==========================================================================

    user = relationship("User", back_populates="alert_profiles")
    alerts_sent = relationship("AlertSent", back_populates="alert_profile", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AlertProfile {self.name}>"

    def to_dict(self) -> dict:
        """Convert to dictionary for matching."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "naics_codes": self.naics_codes or [],
            "psc_codes": self.psc_codes or [],
            "keywords": self.keywords or [],
            "excluded_keywords": self.excluded_keywords or [],
            "states": self.states or [],
            "set_aside_types": self.set_aside_types or [],
            "notice_types": self.notice_types or [],
            "min_score": self.min_score or 0,
            "min_value": float(self.min_value) if self.min_value else None,
            "max_value": float(self.max_value) if self.max_value else None,
            "agencies": self.agencies or [],
            "excluded_agencies": self.excluded_agencies or [],
            "alert_frequency": self.alert_frequency,
        }
