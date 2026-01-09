"""
Proposal Templates API Routes

CRUD operations for proposal templates and AI-generated sections.
"""

import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ProposalTemplate, GeneratedSection, User, Opportunity, CompanyProfile
from app.api.deps import get_current_user, rate_limit_ai, track_ai_token_usage

router = APIRouter()


# =============================================================================
# Pydantic Schemas
# =============================================================================

class TemplateSectionInput(BaseModel):
    """A section within a template."""
    heading: str
    content: Optional[str] = None
    ai_prompt: Optional[str] = None
    order: int = 0


class TemplateCreate(BaseModel):
    """Schema for creating a new template."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    template_type: str = Field(..., pattern="^(technical_approach|past_performance|management_approach|key_personnel|price_cost|executive_summary|full_proposal)$")
    target_naics_codes: Optional[List[str]] = None
    target_agencies: Optional[List[str]] = None
    target_keywords: Optional[List[str]] = None
    sections: Optional[List[TemplateSectionInput]] = None
    raw_content: Optional[str] = None
    ai_system_prompt: Optional[str] = None
    use_company_profile: bool = True
    use_past_performance: bool = True
    use_capability_statement: bool = True


class TemplateUpdate(BaseModel):
    """Schema for updating a template."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    template_type: Optional[str] = Field(None, pattern="^(technical_approach|past_performance|management_approach|key_personnel|price_cost|executive_summary|full_proposal)$")
    target_naics_codes: Optional[List[str]] = None
    target_agencies: Optional[List[str]] = None
    target_keywords: Optional[List[str]] = None
    sections: Optional[List[TemplateSectionInput]] = None
    raw_content: Optional[str] = None
    ai_system_prompt: Optional[str] = None
    use_company_profile: Optional[bool] = None
    use_past_performance: Optional[bool] = None
    use_capability_statement: Optional[bool] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class TemplateResponse(BaseModel):
    """Schema for template responses."""
    id: str
    name: str
    description: Optional[str]
    template_type: str
    target_naics_codes: Optional[List[str]]
    target_agencies: Optional[List[str]]
    target_keywords: Optional[List[str]]
    sections: Optional[List[dict]]
    raw_content: Optional[str]
    ai_system_prompt: Optional[str]
    use_company_profile: bool
    use_past_performance: bool
    use_capability_statement: bool
    is_active: bool
    is_default: bool
    is_public: bool
    times_used: int
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GenerateSectionRequest(BaseModel):
    """Request to generate a section using AI."""
    template_id: str
    opportunity_id: Optional[str] = None
    section_key: str
    custom_prompt: Optional[str] = None  # Override the template's prompt


class GeneratedSectionResponse(BaseModel):
    """Response for a generated section."""
    id: str
    template_id: str
    opportunity_id: Optional[str]
    section_key: str
    section_heading: Optional[str]
    generated_content: str
    edited_content: Optional[str]
    use_edited: bool
    model_used: Optional[str]
    tokens_input: Optional[int]
    tokens_output: Optional[int]
    user_rating: Optional[int]
    generated_at: datetime

    class Config:
        from_attributes = True


class UpdateGeneratedSectionRequest(BaseModel):
    """Request to update a generated section."""
    edited_content: Optional[str] = None
    use_edited: Optional[bool] = None
    user_rating: Optional[int] = Field(None, ge=1, le=5)
    feedback_notes: Optional[str] = None


# =============================================================================
# Template CRUD Endpoints
# =============================================================================

@router.get("/templates", response_model=List[TemplateResponse])
async def list_templates(
    template_type: Optional[str] = Query(None, description="Filter by template type"),
    include_public: bool = Query(True, description="Include public templates"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all templates for the current user.
    Optionally includes public templates shared by admins.
    """
    query = db.query(ProposalTemplate).filter(
        ProposalTemplate.is_active == True
    )

    if include_public:
        query = query.filter(
            (ProposalTemplate.user_id == current_user.id) |
            (ProposalTemplate.is_public == True)
        )
    else:
        query = query.filter(ProposalTemplate.user_id == current_user.id)

    if template_type:
        query = query.filter(ProposalTemplate.template_type == template_type)

    templates = query.order_by(
        ProposalTemplate.is_default.desc(),
        ProposalTemplate.times_used.desc(),
        ProposalTemplate.created_at.desc()
    ).all()

    return templates


@router.post("/templates", response_model=TemplateResponse, status_code=201)
async def create_template(
    template_data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new proposal template."""
    template = ProposalTemplate(
        id=uuid.uuid4(),
        user_id=current_user.id,
        name=template_data.name,
        description=template_data.description,
        template_type=template_data.template_type,
        target_naics_codes=template_data.target_naics_codes,
        target_agencies=template_data.target_agencies,
        target_keywords=template_data.target_keywords,
        sections=[s.model_dump() for s in template_data.sections] if template_data.sections else None,
        raw_content=template_data.raw_content,
        ai_system_prompt=template_data.ai_system_prompt,
        use_company_profile=template_data.use_company_profile,
        use_past_performance=template_data.use_past_performance,
        use_capability_statement=template_data.use_capability_statement,
    )

    db.add(template)
    db.commit()
    db.refresh(template)

    return template


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific template by ID."""
    template = db.query(ProposalTemplate).filter(
        ProposalTemplate.id == template_id,
        (ProposalTemplate.user_id == current_user.id) | (ProposalTemplate.is_public == True)
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return template


@router.put("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    template_data: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing template."""
    template = db.query(ProposalTemplate).filter(
        ProposalTemplate.id == template_id,
        ProposalTemplate.user_id == current_user.id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found or you don't have permission to edit it")

    # Update fields
    update_data = template_data.model_dump(exclude_unset=True)

    if "sections" in update_data and update_data["sections"]:
        update_data["sections"] = [s if isinstance(s, dict) else s.model_dump() for s in update_data["sections"]]

    for field, value in update_data.items():
        setattr(template, field, value)

    template.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(template)

    return template


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a template."""
    template = db.query(ProposalTemplate).filter(
        ProposalTemplate.id == template_id,
        ProposalTemplate.user_id == current_user.id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found or you don't have permission to delete it")

    db.delete(template)
    db.commit()

    return None


# =============================================================================
# Default Templates
# =============================================================================

@router.get("/templates/defaults/list")
async def list_default_templates(
    db: Session = Depends(get_db),
):
    """
    Get list of built-in default templates.
    These are starter templates users can copy.
    """
    defaults = [
        {
            "id": "default-technical-approach",
            "name": "Technical Approach Template",
            "template_type": "technical_approach",
            "description": "Standard technical approach outline for IT services proposals",
            "sections": [
                {"heading": "Understanding of Requirements", "ai_prompt": "Summarize your understanding of the government's requirements based on the PWS/SOW.", "order": 1},
                {"heading": "Technical Approach", "ai_prompt": "Describe the technical methodology and approach to meet the requirements.", "order": 2},
                {"heading": "Tools and Technologies", "ai_prompt": "List and justify the tools, technologies, and platforms you will use.", "order": 3},
                {"heading": "Quality Assurance", "ai_prompt": "Describe QA processes, testing methodologies, and quality controls.", "order": 4},
                {"heading": "Risk Mitigation", "ai_prompt": "Identify potential risks and mitigation strategies.", "order": 5},
            ]
        },
        {
            "id": "default-past-performance",
            "name": "Past Performance Template",
            "template_type": "past_performance",
            "description": "Template for presenting relevant past performance",
            "sections": [
                {"heading": "Contract Overview", "ai_prompt": "Describe the contract scope, value, and period of performance.", "order": 1},
                {"heading": "Relevance", "ai_prompt": "Explain how this past performance is relevant to the current opportunity.", "order": 2},
                {"heading": "Challenges & Solutions", "ai_prompt": "Describe challenges encountered and how they were resolved.", "order": 3},
                {"heading": "Results & Outcomes", "ai_prompt": "Highlight measurable results and customer satisfaction.", "order": 4},
            ]
        },
        {
            "id": "default-management-approach",
            "name": "Management Approach Template",
            "template_type": "management_approach",
            "description": "Template for management and staffing approach",
            "sections": [
                {"heading": "Organizational Structure", "ai_prompt": "Describe the project organization and reporting structure.", "order": 1},
                {"heading": "Key Personnel", "ai_prompt": "Introduce key personnel and their qualifications.", "order": 2},
                {"heading": "Communication Plan", "ai_prompt": "Describe communication processes with the government.", "order": 3},
                {"heading": "Transition Plan", "ai_prompt": "Outline the transition-in approach and timeline.", "order": 4},
            ]
        },
        {
            "id": "default-executive-summary",
            "name": "Executive Summary Template",
            "template_type": "executive_summary",
            "description": "Compelling executive summary template",
            "sections": [
                {"heading": "Value Proposition", "ai_prompt": "State your unique value proposition for this contract.", "order": 1},
                {"heading": "Qualifications", "ai_prompt": "Summarize why you are the best choice.", "order": 2},
                {"heading": "Key Differentiators", "ai_prompt": "Highlight what sets you apart from competitors.", "order": 3},
            ]
        },
    ]

    return {"defaults": defaults}


# =============================================================================
# Generated Sections Endpoints
# =============================================================================

@router.get("/templates/{template_id}/sections", response_model=List[GeneratedSectionResponse])
async def list_generated_sections(
    template_id: str,
    opportunity_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all generated sections for a template, optionally filtered by opportunity."""
    query = db.query(GeneratedSection).filter(
        GeneratedSection.template_id == template_id,
        GeneratedSection.user_id == current_user.id
    )

    if opportunity_id:
        query = query.filter(GeneratedSection.opportunity_id == opportunity_id)

    sections = query.order_by(GeneratedSection.generated_at.desc()).all()

    return sections


@router.patch("/sections/{section_id}", response_model=GeneratedSectionResponse)
async def update_generated_section(
    section_id: str,
    update_data: UpdateGeneratedSectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a generated section (edit content, rate, provide feedback)."""
    section = db.query(GeneratedSection).filter(
        GeneratedSection.id == section_id,
        GeneratedSection.user_id == current_user.id
    ).first()

    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    if update_data.edited_content is not None:
        section.edited_content = update_data.edited_content
        section.edited_at = datetime.utcnow()

    if update_data.use_edited is not None:
        section.use_edited = update_data.use_edited

    if update_data.user_rating is not None:
        section.user_rating = update_data.user_rating

    if update_data.feedback_notes is not None:
        section.feedback_notes = update_data.feedback_notes

    section.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(section)

    return section


@router.delete("/sections/{section_id}", status_code=204)
async def delete_generated_section(
    section_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a generated section."""
    section = db.query(GeneratedSection).filter(
        GeneratedSection.id == section_id,
        GeneratedSection.user_id == current_user.id
    ).first()

    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    db.delete(section)
    db.commit()

    return None


# =============================================================================
# AI Generation Endpoints
# =============================================================================

@router.post("/generate", response_model=GeneratedSectionResponse)
async def generate_proposal_section(
    request: GenerateSectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(rate_limit_ai),
):
    """
    Generate a proposal section using AI.

    Uses the specified template and optional opportunity context to generate
    compelling proposal content.
    """
    from app.services.template_generator import (
        generate_from_template,
        build_generation_context,
        save_generated_section,
    )

    # Get the template
    template = db.query(ProposalTemplate).filter(
        ProposalTemplate.id == request.template_id,
        (ProposalTemplate.user_id == current_user.id) | (ProposalTemplate.is_public == True)
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Get opportunity if specified
    opportunity = None
    if request.opportunity_id:
        opportunity = db.query(Opportunity).filter(
            Opportunity.id == request.opportunity_id
        ).first()
        if not opportunity:
            raise HTTPException(status_code=404, detail="Opportunity not found")

    # Get company profile
    company_profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    # Get past performances (most relevant ones)
    past_performances = []
    if company_profile:
        from app.models import PastPerformance
        pp_query = db.query(PastPerformance).filter(
            PastPerformance.company_profile_id == company_profile.id
        )

        # If opportunity has NAICS, prioritize matching past performance
        if opportunity and opportunity.naics_code:
            pp_query = pp_query.order_by(
                (PastPerformance.naics_code == opportunity.naics_code).desc(),
                PastPerformance.contract_value.desc()
            )
        else:
            pp_query = pp_query.order_by(PastPerformance.contract_value.desc())

        past_performances = pp_query.limit(5).all()

    # Get capability statement
    capability_statement = None
    if company_profile:
        from app.models import CapabilityStatement
        capability_statement = db.query(CapabilityStatement).filter(
            CapabilityStatement.company_profile_id == company_profile.id,
            CapabilityStatement.is_default == True
        ).first()

    # Generate content
    result = generate_from_template(
        template=template,
        opportunity=opportunity,
        company_profile=company_profile,
        past_performances=past_performances,
        capability_statement=capability_statement,
        section_key=request.section_key,
    )

    if result.get("status") != "success":
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Failed to generate content")
        )

    # Save the generated section(s)
    saved_section = None
    for section in result.get("sections", []):
        if section.get("status") == "success":
            saved_section = save_generated_section(
                db=db,
                template_id=str(template.id),
                user_id=str(current_user.id),
                section_key=section["section_key"],
                section_heading=section["section_heading"],
                generated_content=section["content"],
                opportunity_id=request.opportunity_id,
                generation_context=build_generation_context(
                    opportunity=opportunity,
                    company_profile=company_profile,
                ),
                model_used="claude-sonnet-4-20250514",
                tokens_input=section.get("tokens_input"),
                tokens_output=section.get("tokens_output"),
            )

    # Update template usage stats
    template.times_used = (template.times_used or 0) + 1
    template.last_used_at = datetime.utcnow()
    db.commit()

    if not saved_section:
        raise HTTPException(
            status_code=500,
            detail="No sections were successfully generated"
        )

    # Track token usage for rate limiting
    total_tokens = sum(
        (s.get("tokens_input", 0) or 0) + (s.get("tokens_output", 0) or 0)
        for s in result.get("sections", [])
        if s.get("status") == "success"
    )
    if total_tokens > 0:
        track_ai_token_usage(db, current_user.id, total_tokens)

    return saved_section


@router.post("/generate-quick")
async def generate_quick_section(
    template_type: str = Query(..., description="Type of section to generate"),
    opportunity_id: Optional[str] = Query(None, description="Opportunity to generate for"),
    custom_prompt: Optional[str] = Query(None, description="Custom generation prompt"),
    db: Session = Depends(get_db),
    current_user: User = Depends(rate_limit_ai),
):
    """
    Quick generation without a saved template.

    Generates a section using default prompts for the specified type.
    Useful for one-off generation without creating a template first.
    """
    from app.services.template_generator import generate_section, build_generation_context

    # Default prompts for each section type
    default_prompts = {
        "technical_approach": "Write a compelling technical approach section that demonstrates deep understanding of the requirements and a clear methodology for successful delivery.",
        "past_performance": "Write a past performance section highlighting relevant experience, specific achievements, and customer satisfaction.",
        "management_approach": "Write a management approach section describing organizational structure, key personnel qualifications, and project management methodology.",
        "executive_summary": "Write a compelling executive summary that captures the value proposition, key qualifications, and differentiators.",
        "key_personnel": "Write key personnel descriptions highlighting relevant experience, certifications, and expertise.",
        "price_cost": "Write a price/cost narrative explaining the pricing approach and demonstrating cost reasonableness.",
    }

    if template_type not in default_prompts:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid template type. Must be one of: {', '.join(default_prompts.keys())}"
        )

    # Get opportunity if specified
    opportunity = None
    if opportunity_id:
        opportunity = db.query(Opportunity).filter(
            Opportunity.id == opportunity_id
        ).first()

    # Get company profile
    company_profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    # Build context
    context = build_generation_context(
        opportunity=opportunity,
        company_profile=company_profile,
    )

    # Generate
    prompt = custom_prompt or default_prompts[template_type]
    result = generate_section(
        section_prompt=prompt,
        section_heading=template_type.replace("_", " ").title(),
        context=context,
    )

    if result.get("status") != "success":
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Failed to generate content")
        )

    # Track token usage for rate limiting
    total_tokens = (result.get("tokens_input") or 0) + (result.get("tokens_output") or 0)
    if total_tokens > 0:
        track_ai_token_usage(db, current_user.id, total_tokens)

    return {
        "section_type": template_type,
        "content": result["content"],
        "tokens_input": result.get("tokens_input"),
        "tokens_output": result.get("tokens_output"),
        "generated_at": result.get("generated_at"),
    }


# =============================================================================
# Compliance Matrix Endpoint
# =============================================================================

@router.post("/compliance-matrix/{opportunity_id}")
async def generate_compliance_matrix_endpoint(
    opportunity_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(rate_limit_ai),
):
    """
    Generate a compliance matrix for an opportunity.

    Analyzes the solicitation to extract requirements and maps them to
    the user's company capabilities. Returns a structured compliance matrix
    showing:
    - All extracted requirements with references
    - Compliance status (Full, Partial, Gap) for each requirement
    - Suggested response approaches
    - Overall fit score
    - Critical gaps and recommendations
    """
    from app.services.template_generator import generate_compliance_matrix

    # Get opportunity
    opportunity = db.query(Opportunity).filter(
        Opportunity.id == opportunity_id
    ).first()

    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    # Build opportunity text from available sources
    opportunity_text_parts = []

    if opportunity.title:
        opportunity_text_parts.append(f"Title: {opportunity.title}")

    if opportunity.description:
        opportunity_text_parts.append(f"Description:\n{opportunity.description}")

    # Include AI summary if available
    if hasattr(opportunity, 'attachments') and opportunity.attachments:
        for attachment in opportunity.attachments:
            if hasattr(attachment, 'ai_summary') and attachment.ai_summary:
                opportunity_text_parts.append(f"AI Analysis:\n{attachment.ai_summary}")

    # Include extracted text from attachments if available
    if hasattr(opportunity, 'attachments') and opportunity.attachments:
        for attachment in opportunity.attachments:
            if hasattr(attachment, 'extracted_text') and attachment.extracted_text:
                opportunity_text_parts.append(f"Attachment ({attachment.name}):\n{attachment.extracted_text[:5000]}")

    if not opportunity_text_parts:
        raise HTTPException(
            status_code=400,
            detail="Opportunity has no description or extracted content to analyze"
        )

    opportunity_text = "\n\n".join(opportunity_text_parts)

    # Get company profile
    company_profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    # Generate compliance matrix
    result = generate_compliance_matrix(
        opportunity_text=opportunity_text,
        company_profile=company_profile,
    )

    if result.get("status") != "success":
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Failed to generate compliance matrix")
        )

    # Track token usage
    total_tokens = (result.get("tokens_input") or 0) + (result.get("tokens_output") or 0)
    if total_tokens > 0:
        track_ai_token_usage(db, current_user.id, total_tokens)

    return {
        "opportunity_id": opportunity_id,
        "opportunity_title": opportunity.title,
        "matrix": result.get("matrix"),
        "tokens_input": result.get("tokens_input"),
        "tokens_output": result.get("tokens_output"),
        "generated_at": result.get("generated_at"),
    }
