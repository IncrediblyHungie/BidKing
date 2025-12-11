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
    #        Award Notice, Special Notice, Justification, etc.

    # Related notice (for linked solicitations)
    related_notice_id = Column(String(100), nullable=True, index=True)

    # ==========================================================================
    # Dates
    # ==========================================================================

    posted_date = Column(Date, nullable=True, index=True)
    original_published_date = Column(DateTime, nullable=True)  # Full datetime with time
    response_deadline = Column(DateTime, nullable=True, index=True)
    archive_date = Column(Date, nullable=True)
    original_inactive_date = Column(Date, nullable=True)
    inactive_policy = Column(String(255), nullable=True)  # e.g., "30 days after published date"

    # ==========================================================================
    # Agency Information
    # ==========================================================================

    department_name = Column(String(255), nullable=True)
    sub_tier = Column(String(255), nullable=True)  # Sub-tier agency
    agency_name = Column(String(255), nullable=True, index=True)
    office_name = Column(String(255), nullable=True)

    # Contracting office address (stored as JSON)
    contracting_office_address = Column(JSONDict(), nullable=True)

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
    authority = Column(String(500), nullable=True)  # e.g., "FAR 6.302-1 - Only one responsible source"
    initiative = Column(String(255), nullable=True)  # e.g., "None" or specific initiative

    # ==========================================================================
    # Award Information (if awarded)
    # ==========================================================================

    award_number = Column(String(100), nullable=True)
    task_delivery_order_number = Column(String(100), nullable=True)
    modification_number = Column(String(50), nullable=True)
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
    attachments = relationship("OpportunityAttachment", back_populates="opportunity", cascade="all, delete-orphan")
    history = relationship("OpportunityHistory", back_populates="opportunity", cascade="all, delete-orphan", order_by="desc(OpportunityHistory.changed_at)")
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
    status = Column(String(50), default="watching", index=True)
    # Status: watching, researching, preparing, submitted, won, lost, archived

    # Priority (1 = highest, 5 = lowest)
    priority = Column(Integer, default=3)

    # User notes
    notes = Column(Text, nullable=True)

    # Reminder
    reminder_date = Column(Date, nullable=True)

    # Stage changed timestamp (for tracking how long in each stage)
    stage_changed_at = Column(DateTime, default=datetime.utcnow)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to opportunity
    opportunity = relationship("Opportunity")

    def __repr__(self):
        return f"<SavedOpportunity {self.status}>"


class OpportunityAttachment(Base):
    """Attachments and links for an opportunity."""

    __tablename__ = "opportunity_attachments"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Opportunity relationship
    opportunity_id = Column(GUID(), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)

    # Attachment info
    name = Column(String(500), nullable=True)  # File name or link title
    description = Column(Text, nullable=True)  # Description of the attachment
    url = Column(Text, nullable=True)  # Download URL or resource URL
    resource_type = Column(String(50), nullable=True)  # file, link, resource
    file_type = Column(String(50), nullable=True)  # pdf, doc, xlsx, etc.
    file_size = Column(Integer, nullable=True)  # Size in bytes

    # For searchability - extracted text content
    text_content = Column(Text, nullable=True)

    # Timestamps
    posted_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    opportunity = relationship("Opportunity", back_populates="attachments")

    def __repr__(self):
        return f"<OpportunityAttachment {self.name}>"


class OpportunityHistory(Base):
    """History of changes for an opportunity."""

    __tablename__ = "opportunity_history"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Opportunity relationship
    opportunity_id = Column(GUID(), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)

    # Change info
    action = Column(String(100), nullable=False)  # e.g., "Presolicitation (Original)", "Combined Synopsis/Solicitation (Updated)"
    changed_at = Column(DateTime, nullable=False)
    description = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    opportunity = relationship("Opportunity", back_populates="history")

    def __repr__(self):
        return f"<OpportunityHistory {self.action} at {self.changed_at}>"
