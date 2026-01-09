"""
Template Generation Service

Uses Claude API to generate proposal sections based on templates,
company profiles, and opportunity context.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

# System prompt for proposal generation
PROPOSAL_SYSTEM_PROMPT = """You are an expert federal contract proposal writer with 20+ years of experience winning government contracts. You write compelling, compliant, and professional proposal sections that directly address evaluation criteria.

Your writing style:
- Clear, concise, and action-oriented
- Uses strong verbs and specific metrics
- Addresses requirements directly
- Highlights differentiators without being salesy
- Professional government contractor tone
- Avoids jargon unless industry-standard

When generating proposal content:
1. Address every requirement mentioned in the PWS/SOW
2. Use specific examples and metrics from past performance when available
3. Reference company capabilities and certifications
4. Follow the section structure provided
5. Use compliant language (shall, will, must)
6. Include clear headers and logical organization"""


def build_generation_context(
    opportunity: Optional[Any] = None,
    company_profile: Optional[Any] = None,
    past_performances: Optional[List[Any]] = None,
    capability_statement: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Build the context dictionary for AI generation.

    Args:
        opportunity: The opportunity being bid on
        company_profile: The user's company profile
        past_performances: List of relevant past performances
        capability_statement: The company's capability statement

    Returns:
        Dictionary with all context for generation
    """
    context = {}

    # Add opportunity context
    if opportunity:
        context["opportunity"] = {
            "title": opportunity.title,
            "solicitation_number": opportunity.solicitation_number,
            "naics_code": opportunity.naics_code,
            "agency": opportunity.agency_name,
            "description": (opportunity.description or "")[:5000],  # Truncate long descriptions
            "set_aside": opportunity.set_aside_type,
            "response_deadline": str(opportunity.response_deadline) if opportunity.response_deadline else None,
        }

        # Add AI summary if available
        if hasattr(opportunity, 'metadata') and opportunity.metadata:
            metadata = opportunity.metadata
            if hasattr(metadata, 'ai_summary') and metadata.ai_summary:
                context["opportunity"]["ai_analysis"] = metadata.ai_summary

    # Add company profile context
    if company_profile:
        context["company"] = {
            "name": company_profile.company_name,
            "uei": company_profile.uei,
            "cage_code": company_profile.cage_code,
            "business_size": company_profile.business_size,
            "employee_count": company_profile.employee_count,
            "headquarters_state": company_profile.headquarters_state,
            "facility_clearance": company_profile.facility_clearance,
        }

        # Add certifications
        if company_profile.certifications:
            context["company"]["certifications"] = [
                {
                    "type": cert.certification_type,
                    "is_active": cert.is_active,
                }
                for cert in company_profile.certifications
                if cert.is_active
            ]

        # Add NAICS expertise
        if company_profile.naics_codes:
            context["company"]["naics_expertise"] = [
                {
                    "code": naics.naics_code,
                    "description": naics.naics_description,
                    "experience_level": naics.experience_level,
                    "contracts_won": naics.contracts_won,
                }
                for naics in company_profile.naics_codes
            ]

    # Add past performance context
    if past_performances:
        context["past_performance"] = [
            {
                "title": pp.contract_title,
                "agency": pp.agency_name,
                "value": float(pp.contract_value) if pp.contract_value else None,
                "naics_code": pp.naics_code,
                "role": pp.role,
                "description": (pp.description or "")[:1000],
                "performance_rating": pp.performance_rating,
            }
            for pp in past_performances[:5]  # Limit to top 5
        ]

    # Add capability statement context
    if capability_statement:
        context["capability_statement"] = {
            "core_competencies": capability_statement.core_competencies or [],
            "differentiators": capability_statement.differentiators or [],
            "full_text": (capability_statement.full_text or "")[:3000],
        }

    return context


def generate_section(
    section_prompt: str,
    section_heading: str,
    context: Dict[str, Any],
    custom_system_prompt: Optional[str] = None,
    max_tokens: int = 2000,
) -> Dict[str, Any]:
    """
    Generate a single proposal section using Claude.

    Args:
        section_prompt: The prompt describing what to generate
        section_heading: The heading for this section
        context: Context dictionary with opportunity, company, past performance data
        custom_system_prompt: Optional override for the system prompt
        max_tokens: Maximum tokens to generate

    Returns:
        Dictionary with generated content and metadata
    """
    if not settings.anthropic_api_key:
        logger.error("Anthropic API key not configured")
        return {
            "error": "API key not configured",
            "status": "failed"
        }

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        # Build the user prompt
        user_prompt = f"""Generate the "{section_heading}" section for a federal contract proposal.

## Context

{json.dumps(context, indent=2, default=str)}

## Instructions

{section_prompt}

## Requirements

1. Write in professional federal proposal style
2. Be specific and reference the company's actual capabilities
3. Address the opportunity requirements directly
4. Use clear headers and organized structure
5. Include specific metrics and examples where possible
6. Keep the tone confident but not boastful
7. Ensure compliance with federal proposal conventions

Generate the section content now:"""

        system_prompt = custom_system_prompt or PROPOSAL_SYSTEM_PROMPT

        logger.info(f"Generating proposal section: {section_heading}")

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )

        # Extract response
        response_text = ""
        if message.content and len(message.content) > 0:
            block = message.content[0]
            if hasattr(block, 'text'):
                response_text = block.text

        if not response_text:
            return {
                "error": "No text response from Claude",
                "status": "failed"
            }

        return {
            "content": response_text,
            "status": "success",
            "model": "claude-sonnet-4-20250514",
            "tokens_input": message.usage.input_tokens,
            "tokens_output": message.usage.output_tokens,
            "generated_at": datetime.utcnow().isoformat(),
        }

    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        return {
            "error": f"API error: {str(e)}",
            "status": "failed"
        }
    except Exception as e:
        logger.error(f"Error generating section: {e}")
        return {
            "error": str(e),
            "status": "failed"
        }


def generate_from_template(
    template: Any,
    opportunity: Optional[Any] = None,
    company_profile: Optional[Any] = None,
    past_performances: Optional[List[Any]] = None,
    capability_statement: Optional[Any] = None,
    section_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate proposal content from a template.

    Args:
        template: The ProposalTemplate to use
        opportunity: The opportunity being bid on
        company_profile: The user's company profile
        past_performances: Relevant past performances
        capability_statement: Company capability statement
        section_key: Optional specific section to generate (otherwise generates all)

    Returns:
        Dictionary with generated sections and metadata
    """
    # Build context
    context = build_generation_context(
        opportunity=opportunity,
        company_profile=company_profile if template.use_company_profile else None,
        past_performances=past_performances if template.use_past_performance else None,
        capability_statement=capability_statement if template.use_capability_statement else None,
    )

    results = {
        "template_id": str(template.id),
        "template_name": template.name,
        "sections": [],
        "total_tokens_input": 0,
        "total_tokens_output": 0,
        "generated_at": datetime.utcnow().isoformat(),
    }

    # Get sections to generate
    sections = template.sections or []

    if section_key:
        # Generate only the specified section
        sections = [s for s in sections if s.get("heading", "").lower().replace(" ", "_") == section_key.lower()]
        if not sections and template.raw_content:
            # Use raw content with the section key
            sections = [{"heading": section_key, "ai_prompt": template.raw_content, "order": 1}]

    if not sections:
        # If no sections defined, use raw content as single section
        if template.raw_content:
            sections = [{"heading": template.name, "ai_prompt": template.raw_content, "order": 1}]
        else:
            return {
                "error": "Template has no sections or content defined",
                "status": "failed"
            }

    # Generate each section
    for section in sorted(sections, key=lambda s: s.get("order", 0)):
        heading = section.get("heading", "Section")
        prompt = section.get("ai_prompt", section.get("content", "Generate this section."))

        # Add any static content as context
        if section.get("content"):
            prompt = f"{section['content']}\n\n{prompt}"

        result = generate_section(
            section_prompt=prompt,
            section_heading=heading,
            context=context,
            custom_system_prompt=template.ai_system_prompt,
        )

        section_result = {
            "section_key": heading.lower().replace(" ", "_"),
            "section_heading": heading,
            "status": result.get("status"),
        }

        if result.get("status") == "success":
            section_result["content"] = result["content"]
            section_result["tokens_input"] = result.get("tokens_input", 0)
            section_result["tokens_output"] = result.get("tokens_output", 0)
            results["total_tokens_input"] += result.get("tokens_input", 0)
            results["total_tokens_output"] += result.get("tokens_output", 0)
        else:
            section_result["error"] = result.get("error")

        results["sections"].append(section_result)

    # Check if any sections succeeded
    successful = [s for s in results["sections"] if s.get("status") == "success"]
    if successful:
        results["status"] = "success"
    else:
        results["status"] = "failed"
        results["error"] = "All sections failed to generate"

    return results


def save_generated_section(
    db,
    template_id: str,
    user_id: str,
    section_key: str,
    section_heading: str,
    generated_content: str,
    opportunity_id: Optional[str] = None,
    generation_prompt: Optional[str] = None,
    generation_context: Optional[Dict] = None,
    model_used: Optional[str] = None,
    tokens_input: Optional[int] = None,
    tokens_output: Optional[int] = None,
) -> Any:
    """
    Save a generated section to the database.

    Returns the created GeneratedSection object.
    """
    from app.models import GeneratedSection

    section = GeneratedSection(
        id=uuid.uuid4(),
        template_id=template_id,
        opportunity_id=opportunity_id,
        user_id=user_id,
        section_key=section_key,
        section_heading=section_heading,
        generated_content=generated_content,
        generation_prompt=generation_prompt,
        generation_context=generation_context,
        model_used=model_used,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
    )

    db.add(section)
    db.commit()
    db.refresh(section)

    return section


# Compliance Matrix System Prompt
COMPLIANCE_MATRIX_SYSTEM_PROMPT = """You are an expert federal contract proposal analyst with 20+ years of experience. You analyze solicitations to extract requirements and create compliance matrices.

A compliance matrix maps each requirement from the PWS/SOW to a response approach, showing the government how your company will address every requirement.

For each requirement:
1. Extract the exact requirement text or summary
2. Identify the section/reference (e.g., "PWS 3.1.2" or "RFP Section C.5")
3. Determine if mandatory (M), desirable (D), or informational (I)
4. Assess company compliance: Full (can fully meet), Partial (need partner/additional capability), or Gap (cannot currently meet)
5. Suggest a response approach

Output must be valid JSON."""


def generate_compliance_matrix(
    opportunity_text: str,
    company_profile: Optional[Any] = None,
    max_tokens: int = 4000,
) -> Dict[str, Any]:
    """
    Generate a compliance matrix from a solicitation.

    Extracts requirements from the opportunity and maps them to company capabilities.

    Args:
        opportunity_text: The solicitation text (PWS, SOW, description, etc.)
        company_profile: Optional company profile for capability matching
        max_tokens: Maximum tokens to generate

    Returns:
        Dictionary with compliance matrix and metadata
    """
    if not settings.anthropic_api_key:
        logger.error("Anthropic API key not configured")
        return {
            "error": "API key not configured",
            "status": "failed"
        }

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        # Build company capabilities context
        company_context = ""
        if company_profile:
            capabilities = []
            if company_profile.naics_codes:
                capabilities.append(f"NAICS expertise: {', '.join([n.naics_code for n in company_profile.naics_codes])}")
            if hasattr(company_profile, 'certifications') and company_profile.certifications:
                active_certs = [c.certification_type for c in company_profile.certifications if c.is_active]
                if active_certs:
                    capabilities.append(f"Certifications: {', '.join(active_certs)}")
            if company_profile.facility_clearance:
                capabilities.append(f"Clearance: {company_profile.facility_clearance}")
            if company_profile.employee_count:
                capabilities.append(f"Employee count: {company_profile.employee_count}")

            if capabilities:
                company_context = f"""
## Company Capabilities

{chr(10).join('- ' + c for c in capabilities)}
"""

        user_prompt = f"""Analyze this federal solicitation and create a compliance matrix.

## Solicitation Text

{opportunity_text[:15000]}

{company_context}

## Instructions

1. Extract ALL requirements from the solicitation (functional, technical, administrative)
2. For each requirement, determine:
   - The exact or summarized requirement text
   - Section reference (PWS section, RFP paragraph, etc.)
   - Requirement type: M (mandatory), D (desirable), I (informational)
   - Compliance status based on company capabilities: Full, Partial, Gap
   - Suggested response approach

3. Identify overall fit score (0-100) based on how well the company matches requirements

4. List any critical gaps that would prevent winning

Return JSON in this exact format:
{{
    "requirements": [
        {{
            "id": "REQ-001",
            "reference": "PWS 3.1",
            "requirement_text": "The contractor shall...",
            "type": "M",
            "compliance": "Full",
            "approach": "We will leverage our..."
        }}
    ],
    "summary": {{
        "total_requirements": 15,
        "mandatory": 10,
        "desirable": 5,
        "full_compliance": 12,
        "partial_compliance": 2,
        "gaps": 1,
        "fit_score": 85
    }},
    "critical_gaps": ["List of any gaps that would disqualify the bid"],
    "strengths": ["Key strengths that position us well"],
    "recommendations": ["Actions to improve compliance before proposal submission"]
}}

Generate the compliance matrix now:"""

        logger.info("Generating compliance matrix")

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=COMPLIANCE_MATRIX_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )

        # Extract response
        response_text = ""
        if message.content and len(message.content) > 0:
            block = message.content[0]
            if hasattr(block, 'text'):
                response_text = block.text

        if not response_text:
            return {
                "error": "No text response from Claude",
                "status": "failed"
            }

        # Parse JSON response
        try:
            # Clean up response - sometimes Claude wraps in markdown
            clean_response = response_text.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.startswith("```"):
                clean_response = clean_response[3:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]

            matrix_data = json.loads(clean_response.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse compliance matrix JSON: {e}")
            # Return the raw text if JSON parsing fails
            matrix_data = {
                "raw_text": response_text,
                "parse_error": str(e)
            }

        return {
            "matrix": matrix_data,
            "status": "success",
            "model": "claude-sonnet-4-20250514",
            "tokens_input": message.usage.input_tokens,
            "tokens_output": message.usage.output_tokens,
            "generated_at": datetime.utcnow().isoformat(),
        }

    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        return {
            "error": f"API error: {str(e)}",
            "status": "failed"
        }
    except Exception as e:
        logger.error(f"Error generating compliance matrix: {e}")
        return {
            "error": str(e),
            "status": "failed"
        }
