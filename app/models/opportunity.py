"""
Opportunity Model

Federal contract opportunities from SAM.gov.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Text, Numeric, Date
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.uuid_type import GUID, JSONArray, JSONDict


class Opportunity(Base):
    """Federal contract opportunity from SAM.gov."""

    __tablename__ = "opportunities"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # SAM.gov identifiers
    notice_id = Column(String(100), unique=True, nullable=False, index=True)
    solicitation_number = Column(String(100), nullable=True, index=True)

    # Basic info
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)

    # Notice type
    notice_type = Column(String(100), nullable=True)
    # Types: Presolicitation, Combined Synopsis/Solicitation, Sources Sought,
    #        Award Notice, Special Notice, etc.

    # ==========================================================================
    # Dates
    # ==========================================================================

    posted_date = Column(Date, nullable=True, index=True)
    response_deadline = Column(DateTime, nullable=True, index=True)
    archive_date = Column(Date, nullable=True)

    # ==========================================================================
    # Agency Information
    # ==========================================================================

    department_name = Column(String(255), nullable=True)
    agency_name = Column(String(255), nullable=True, index=True)
    office_name = Column(String(255), nullable=True)

    # ==========================================================================
    # Classification
    # ==========================================================================

    naics_code = Column(String(6), nullable=True, index=True)
    naics_description = Column(String(255), nullable=True)
    psc_code = Column(String(10), nullable=True, index=True)
    psc_description = Column(String(255), nullable=True)

    # ==========================================================================
    # Set-Aside
    # ==========================================================================

    set_aside_type = Column(String(100), nullable=True, index=True)
    set_aside_description = Column(String(255), nullable=True)

    # ==========================================================================
    # Place of Performance
    # ==========================================================================

    pop_city = Column(String(100), nullable=True)
    pop_state = Column(String(2), nullable=True, index=True)
    pop_zip = Column(String(10), nullable=True)
    pop_country = Column(String(3), nullable=True)

    # ==========================================================================
    # Contract Details
    # ==========================================================================

    contract_type = Column(String(100), nullable=True)

    # ==========================================================================
    # Award Information (if awarded)
    # ==========================================================================

    award_number = Column(String(100), nullable=True)
    award_amount = Column(Numeric(15, 2), nullable=True)
    award_date = Column(Date, nullable=True)
    awardee_name = Column(String(255), nullable=True)
    awardee_uei = Column(String(12), nullable=True)

    # ==========================================================================
    # Scoring (BidKing's unique feature)
    # ==========================================================================

    # Likelihood score that contract is under $100K (0-100)
    likelihood_score = Column(Integer, default=50, index=True)

    # Reasons for the score
    score_reasons = Column(JSONArray(), nullable=True)

    # ==========================================================================
    # Links
    # ==========================================================================

    ui_link = Column(Text, nullable=True)  # Link to SAM.gov page

    # ==========================================================================
    # Status
    # ==========================================================================

    status = Column(String(50), default="active", index=True)
    # Status: active, archived, awarded, canceled

    # ==========================================================================
    # Raw Data
    # ==========================================================================

    # Store full JSON for future flexibility
    raw_data = Column(JSONDict(), nullable=True)

    # ==========================================================================
    # Timestamps
    # ==========================================================================

    fetched_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ==========================================================================
    # Relationships
    # ==========================================================================

    points_of_contact = relationship("PointOfContact", back_populates="opportunity", cascade="all, delete-orphan")
    alerts_sent = relationship("AlertSent", back_populates="opportunity")

    def __repr__(self):
        return f"<Opportunity {self.notice_id}: {self.title[:50]}...>"

    def to_dict(self) -> dict:
        """Convert to dictionary for matching."""
        return {
            "notice_id": self.notice_id,
            "title": self.title,
            "description": self.description,
            "naics_code": self.naics_code,
            "psc_code": self.psc_code,
            "pop_state": self.pop_state,
            "set_aside_type": self.set_aside_type,
            "notice_type": self.notice_type,
            "agency_name": self.agency_name,
            "likelihood_score": self.likelihood_score,
            "response_deadline": self.response_deadline.isoformat() if self.response_deadline else None,
            "posted_date": self.posted_date.isoformat() if self.posted_date else None,
        }


class PointOfContact(Base):
    """Point of contact for an opportunity."""

    __tablename__ = "points_of_contact"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Opportunity relationship
    opportunity_id = Column(GUID(), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)

    # Contact info
    contact_type = Column(String(50), nullable=True)  # primary, secondary
    name = Column(String(255), nullable=True)
    title = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    fax = Column(String(50), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    opportunity = relationship("Opportunity", back_populates="points_of_contact")

    def __repr__(self):
        return f"<PointOfContact {self.name}>"


class SavedOpportunity(Base):
    """User's saved/tracked opportunities."""

    __tablename__ = "saved_opportunities"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Relationships
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    opportunity_id = Column(GUID(), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)

    # Tracking status
    status = Column(String(50), default="saved")
    # Status: saved, reviewing, preparing, submitted, won, lost

    # User notes
    notes = Column(Text, nullable=True)

    # Reminder
    reminder_date = Column(Date, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SavedOpportunity {self.status}>"
