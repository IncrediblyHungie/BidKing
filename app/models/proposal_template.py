"""
Proposal Template Models

AI-generated proposal templates for federal contract responses.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.uuid_type import GUID, JSONArray, JSONDict


class ProposalTemplate(Base):
    """
    Reusable proposal templates with AI-generated sections.
    Templates can be generic or targeted to specific NAICS/agencies.
    """

    __tablename__ = "proposal_templates"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Link to user (owner)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # ==========================================================================
    # Template Metadata
    # ==========================================================================

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Template type: technical_approach, past_performance, management_approach,
    # key_personnel, price_cost, executive_summary, full_proposal
    template_type = Column(String(50), nullable=False, index=True)

    # ==========================================================================
    # Target Criteria (for matching opportunities)
    # ==========================================================================

    target_naics_codes = Column(JSONArray(), nullable=True)  # NAICS codes this template works for
    target_agencies = Column(JSONArray(), nullable=True)  # Target agencies
    target_keywords = Column(JSONArray(), nullable=True)  # Keywords that indicate good fit

    # ==========================================================================
    # Template Content
    # ==========================================================================

    # Sections as JSON array with structure:
    # [{"heading": "Section Title", "content": "Template text...", "ai_prompt": "Generate...", "order": 1}]
    sections = Column(JSONArray(), nullable=True)

    # Variables that can be replaced: {company_name}, {contract_title}, {naics_code}, etc.
    variables = Column(JSONArray(), nullable=True)

    # Full raw content (for simple templates without sections)
    raw_content = Column(Text, nullable=True)

    # ==========================================================================
    # AI Generation Settings
    # ==========================================================================

    # Base prompt for AI generation
    ai_system_prompt = Column(Text, nullable=True)

    # Whether to use company profile data in generation
    use_company_profile = Column(Boolean, default=True)

    # Whether to use past performance data
    use_past_performance = Column(Boolean, default=True)

    # Whether to use capability statement
    use_capability_statement = Column(Boolean, default=True)

    # ==========================================================================
    # Status & Visibility
    # ==========================================================================

    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # Default template for its type
    is_public = Column(Boolean, default=False)  # Shared with all users (admin only)

    # Usage tracking
    times_used = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)

    # ==========================================================================
    # Timestamps
    # ==========================================================================

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ==========================================================================
    # Relationships
    # ==========================================================================

    user = relationship("User", backref="proposal_templates")
    generated_sections = relationship("GeneratedSection", back_populates="template", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ProposalTemplate {self.name} ({self.template_type})>"


class GeneratedSection(Base):
    """
    AI-generated proposal sections saved for reuse or editing.
    Links a template to a specific opportunity with generated content.
    """

    __tablename__ = "generated_sections"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Links
    template_id = Column(GUID(), ForeignKey("proposal_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    opportunity_id = Column(GUID(), ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # ==========================================================================
    # Generated Content
    # ==========================================================================

    # Section identifier (e.g., "technical_approach", "past_performance_1")
    section_key = Column(String(100), nullable=False)
    section_heading = Column(String(255), nullable=True)

    # The AI-generated content
    generated_content = Column(Text, nullable=False)

    # User's edited version (if modified)
    edited_content = Column(Text, nullable=True)

    # Which content is active (generated vs edited)
    use_edited = Column(Boolean, default=False)

    # ==========================================================================
    # Generation Metadata
    # ==========================================================================

    # The prompt used to generate this section
    generation_prompt = Column(Text, nullable=True)

    # Context provided to AI (opportunity summary, company profile, etc.)
    generation_context = Column(JSONDict(), nullable=True)

    # Model used and tokens consumed
    model_used = Column(String(100), nullable=True)
    tokens_input = Column(Integer, nullable=True)
    tokens_output = Column(Integer, nullable=True)

    # Generation quality feedback
    user_rating = Column(Integer, nullable=True)  # 1-5 stars
    feedback_notes = Column(Text, nullable=True)

    # ==========================================================================
    # Timestamps
    # ==========================================================================

    generated_at = Column(DateTime, default=datetime.utcnow)
    edited_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ==========================================================================
    # Relationships
    # ==========================================================================

    template = relationship("ProposalTemplate", back_populates="generated_sections")
    opportunity = relationship("Opportunity", backref="generated_sections")

    def __repr__(self):
        return f"<GeneratedSection {self.section_key}>"

    @property
    def active_content(self) -> str:
        """Return the currently active content (edited or generated)."""
        if self.use_edited and self.edited_content:
            return self.edited_content
        return self.generated_content
