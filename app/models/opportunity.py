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
    # AI Estimated Value (extracted from attachments by Claude)
    # ==========================================================================

    # Low and high estimates from AI analysis of SOW/RFP documents
    ai_estimated_value_low = Column(Numeric(15, 2), nullable=True, index=True)
    ai_estimated_value_high = Column(Numeric(15, 2), nullable=True, index=True)
    ai_estimated_value_basis = Column(Text, nullable=True)  # Explanation of how value was derived

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
    # Amendment Tracking
    # ==========================================================================

    # Previous deadline (before most recent amendment)
    previous_response_deadline = Column(DateTime, nullable=True)

    # Count of amendments (incremented each time key fields change)
    amendment_count = Column(Integer, default=0, index=True)

    # When the last amendment occurred
    last_amendment_date = Column(DateTime, nullable=True)

    # Amendment history - JSON array of all changes
    # [{date: "...", field: "response_deadline", old_value: "...", new_value: "...", change_type: "deadline_extended"}]
    amendment_history = Column(JSONArray(), nullable=True)

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
    reminder_sent = Column(Boolean, default=False)  # Track if reminder was sent
    deadline_reminder_sent = Column(Boolean, default=False)  # Track if deadline warning was sent

    # Stage changed timestamp (for tracking how long in each stage)
    stage_changed_at = Column(DateTime, default=datetime.utcnow)

    # Win tracking (when status = 'won')
    win_amount = Column(Numeric(15, 2), nullable=True)
    win_date = Column(Date, nullable=True)

    # Loss tracking (when status = 'lost')
    winner_name = Column(String(255), nullable=True)  # Who won the contract
    loss_reason = Column(Text, nullable=True)

    # Feedback notes (for win or loss - lessons learned)
    feedback_notes = Column(Text, nullable=True)

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

    # Extraction tracking - ensures PDFs are only processed once
    extraction_status = Column(String(20), default="pending", index=True)
    # Status: pending (not attempted), extracted (success), failed (error), skipped (not a PDF)
    extracted_at = Column(DateTime, nullable=True)
    extraction_error = Column(String(500), nullable=True)  # Error message if failed

    # ==========================================================================
    # AI Summary (Claude-generated analysis of PDF content)
    # ==========================================================================
    ai_summary = Column(JSONDict(), nullable=True)
    # Contains structured data:
    # {
    #   "summary": "2-3 sentence plain English summary",
    #   "period_of_performance": "1 base + 4 option years",
    #   "contract_type": "Time & Materials",
    #   "clearance_required": "Secret",
    #   "labor_categories": [{"title": "...", "quantity": 2, "level": "Senior"}],
    #   "technologies": ["Python", "AWS", "PostgreSQL"],
    #   "certifications_required": ["CMMI Level 3"],
    #   "location": "Remote with travel to DC",
    #   "incumbent": "Booz Allen Hamilton",
    #   "estimated_value": {"low": 500000, "high": 750000, "basis": "..."},
    #   "key_dates": {"proposal_due": "2025-01-15", "questions_due": "2025-01-05"},
    # }
    ai_summary_status = Column(String(20), default="pending", index=True)
    # Status: pending, summarized, failed, skipped (no text content)
    ai_summarized_at = Column(DateTime, nullable=True)
    ai_summary_error = Column(String(500), nullable=True)

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
