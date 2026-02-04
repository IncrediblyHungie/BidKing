"""
AI Summarization Service

Uses Claude API to analyze PDF text content and extract structured information
about federal contract opportunities.
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

# The prompt for Claude to extract structured data from PDF content
# NOTE: Literal braces in the JSON template are doubled ({{ and }}) to escape them from .format()
EXTRACTION_PROMPT = """You are an expert federal contracting analyst. Analyze this government contract document and extract key information.

<document>
{document_text}
</document>

Extract the following information and return it as JSON. If information is not found, use null for that field.

{{
  "summary": "2-3 sentence plain English summary of what the government wants done",
  "period_of_performance": "Duration of the contract (e.g., '1 base year + 4 option years', '12 months', etc.)",
  "contract_type": "Type of contract (e.g., 'Firm Fixed Price', 'Time & Materials', 'Cost Plus Fixed Fee', 'IDIQ', etc.)",
  "clearance_required": "Security clearance level required (e.g., 'None', 'Public Trust', 'Secret', 'Top Secret', 'TS/SCI', etc.)",
  "labor_categories": [
    {{
      "title": "Job title/role",
      "quantity": number_of_positions_or_null,
      "level": "Junior/Mid/Senior/Lead or null"
    }}
  ],
  "technologies": ["List of specific technologies, languages, frameworks, tools, platforms mentioned"],
  "certifications_required": ["Required certifications like CMMI, ISO 27001, FedRAMP, PMP, etc."],
  "set_aside_info": "Small business set-aside type if mentioned (8(a), SDVOSB, HUBZone, WOSB, etc.)",
  "location": "Work location (e.g., 'Remote', 'On-site at Pentagon', 'Hybrid - DC area', specific city/state)",
  "incumbent": "Current contractor name if this is a recompete/follow-on",
  "estimated_value": {{
    "low": estimated_low_value_in_dollars_as_integer,
    "high": estimated_high_value_in_dollars_as_integer,
    "basis": "Brief explanation of how you estimated this (labor categories x duration x typical rates)"
  }},
  "key_dates": {{
    "proposal_due": "YYYY-MM-DD or null",
    "questions_due": "YYYY-MM-DD or null",
    "anticipated_start": "YYYY-MM-DD or null"
  }},
  "evaluation_factors": ["List of evaluation criteria if mentioned (e.g., 'Technical Approach', 'Past Performance', 'Price')"],
  "naics_code": "NAICS code if mentioned",
  "contract_number": "Existing contract number if this is a recompete"
}}

Important guidelines:
1. For estimated_value, use industry standard labor rates (GS-13 ~$85/hr, Senior Dev ~$150-200/hr, PM ~$175/hr) multiplied by labor categories and duration
2. If specific dollar amounts are mentioned in the document, use those instead of estimating
3. For technologies, be specific - list actual tool names (e.g., "AWS Lambda" not just "cloud")
4. If the document is a Sources Sought or RFI, note that in the summary
5. Return ONLY valid JSON, no other text"""


def summarize_pdf_content(
    text_content: str,
    attachment_name: str = "",
    max_chars: int = 100000
) -> Dict[str, Any]:
    """
    Use Claude to analyze PDF text and extract structured information.

    Args:
        text_content: The extracted text from the PDF
        attachment_name: Name of the attachment for context
        max_chars: Maximum characters to send to Claude (to manage costs)

    Returns:
        Dictionary with extracted information or error details
    """
    if not settings.anthropic_api_key:
        logger.error("Anthropic API key not configured")
        return {
            "error": "API key not configured",
            "status": "failed"
        }

    if not text_content or len(text_content.strip()) < 100:
        logger.info(f"Skipping {attachment_name}: insufficient text content")
        return {
            "error": "Insufficient text content",
            "status": "skipped"
        }

    # Truncate if too long (to manage API costs)
    if len(text_content) > max_chars:
        text_content = text_content[:max_chars] + "\n\n[Document truncated for analysis...]"

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        # Build the prompt
        prompt = EXTRACTION_PROMPT.format(document_text=text_content)

        # Call Claude API with Haiku for cost-effective extraction
        logger.info(f"Calling Claude API (Haiku) for {attachment_name}...")
        message = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        # Track token usage
        input_tokens = message.usage.input_tokens if message.usage else 0
        output_tokens = message.usage.output_tokens if message.usage else 0
        total_tokens = input_tokens + output_tokens
        logger.info(f"Claude API response received, stop_reason: {message.stop_reason}, tokens: {input_tokens}+{output_tokens}={total_tokens}")

        # Extract the text response
        response_text = ""
        if message.content and len(message.content) > 0:
            block = message.content[0]
            logger.info(f"Content block type: {type(block).__name__}")
            if hasattr(block, 'text'):
                response_text = block.text
            else:
                logger.error(f"Block has no text attribute: {block}")

        if not response_text:
            return {
                "error": "No text response from Claude",
                "status": "failed"
            }

        # Parse JSON from response
        # Claude might wrap it in markdown code blocks
        json_text = response_text.strip()
        if json_text.startswith("```json"):
            json_text = json_text[7:]
        elif json_text.startswith("```"):
            json_text = json_text[3:]
        if json_text.endswith("```"):
            json_text = json_text[:-3]
        json_text = json_text.strip()

        # Find the actual JSON object - look for first { and last }
        first_brace = json_text.find('{')
        last_brace = json_text.rfind('}')
        if first_brace != -1 and last_brace != -1:
            json_text = json_text[first_brace:last_brace + 1]

        try:
            summary_data = json.loads(json_text)
            summary_data["status"] = "summarized"
            summary_data["model"] = "claude-3-5-haiku-20241022"
            summary_data["analyzed_at"] = datetime.utcnow().isoformat()
            summary_data["tokens_used"] = total_tokens
            return summary_data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.error(f"JSON text was: {json_text[:500]}")
            logger.error(f"Original response was: {response_text[:500]}")
            return {
                "error": f"JSON parse error at position {e.pos}: {e.msg}",
                "raw_response": response_text[:500],
                "status": "failed"
            }
        except Exception as e:
            logger.error(f"Unexpected error parsing Claude response: {type(e).__name__}: {e}")
            return {
                "error": f"Parse error: {type(e).__name__}: {str(e)[:200]}",
                "raw_response": response_text[:500] if response_text else "No response",
                "status": "failed"
            }

    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        return {
            "error": f"API error: {str(e)}",
            "status": "failed"
        }
    except Exception as e:
        logger.error(f"Error summarizing PDF: {e}")
        return {
            "error": str(e),
            "status": "failed"
        }


def batch_summarize_attachments(
    limit: int = 10,
    force: bool = False,
    user_id: str = None
) -> Dict[str, Any]:
    """
    Summarize multiple attachments that have extracted text but no AI summary.

    Args:
        limit: Maximum number of attachments to process
        force: If True, re-summarize even if already done
        user_id: If provided, track usage for this user

    Returns:
        Summary of processing results
    """
    from decimal import Decimal
    from app.database import SessionLocal
    from app.models import OpportunityAttachment, Opportunity, UsageTracking

    results = {
        "processed": 0,
        "summarized": 0,
        "failed": 0,
        "skipped": 0,
        "total_tokens": 0,
        "errors": []
    }

    with SessionLocal() as db:
        # Find attachments with extracted text that need summarization
        query = db.query(OpportunityAttachment).filter(
            OpportunityAttachment.text_content.isnot(None),
            OpportunityAttachment.text_content != "",
        )

        if not force:
            query = query.filter(
                OpportunityAttachment.ai_summary_status.in_(["pending", None])
            )

        attachments = query.limit(limit).all()

        logger.info(f"Found {len(attachments)} attachments to summarize")

        import time
        for i, att in enumerate(attachments):
            results["processed"] += 1

            # Rate limit: Claude API allows 30K tokens/minute
            # Add delay between calls to avoid hitting limits
            if i > 0:
                time.sleep(3)  # 3 second delay between API calls

            try:
                summary = summarize_pdf_content(
                    text_content=att.text_content,
                    attachment_name=att.name or "Unknown"
                )

                status = summary.get("status", "failed")

                if status == "summarized":
                    att.ai_summary = summary
                    att.ai_summary_status = "summarized"
                    att.ai_summarized_at = datetime.utcnow()
                    att.ai_summary_error = None
                    results["summarized"] += 1

                    # Track token usage
                    tokens_used = summary.get("tokens_used", 0)
                    results["total_tokens"] += tokens_used
                    logger.info(f"Summarized: {att.name} ({tokens_used} tokens)")

                    # Update parent opportunity with AI estimated value
                    estimated_value = summary.get("estimated_value")
                    if estimated_value and att.opportunity_id:
                        opportunity = db.query(Opportunity).filter(
                            Opportunity.id == att.opportunity_id
                        ).first()
                        if opportunity:
                            # Only update if opportunity doesn't have values yet
                            # (first attachment wins, or highest estimate wins)
                            low_val = estimated_value.get("low")
                            high_val = estimated_value.get("high")
                            basis = estimated_value.get("basis")

                            if low_val is not None:
                                new_low = Decimal(str(low_val))
                                if opportunity.ai_estimated_value_low is None or new_low > opportunity.ai_estimated_value_low:
                                    opportunity.ai_estimated_value_low = new_low

                            if high_val is not None:
                                new_high = Decimal(str(high_val))
                                if opportunity.ai_estimated_value_high is None or new_high > opportunity.ai_estimated_value_high:
                                    opportunity.ai_estimated_value_high = new_high

                            if basis and not opportunity.ai_estimated_value_basis:
                                opportunity.ai_estimated_value_basis = basis

                            logger.info(f"Updated opportunity {att.opportunity_id} with estimated value: ${low_val}-${high_val}")
                elif status == "skipped":
                    att.ai_summary_status = "skipped"
                    att.ai_summarized_at = datetime.utcnow()
                    att.ai_summary_error = summary.get("error")
                    results["skipped"] += 1
                else:
                    att.ai_summary_status = "failed"
                    att.ai_summarized_at = datetime.utcnow()
                    att.ai_summary_error = summary.get("error", "Unknown error")[:500]
                    results["failed"] += 1
                    results["errors"].append({
                        "name": att.name,
                        "error": summary.get("error")
                    })

                db.commit()

            except Exception as e:
                logger.error(f"Error processing {att.name}: {e}")
                att.ai_summary_status = "failed"
                att.ai_summary_error = str(e)[:500]
                att.ai_summarized_at = datetime.utcnow()
                db.commit()
                results["failed"] += 1
                results["errors"].append({
                    "name": att.name,
                    "error": str(e)
                })

        # Update usage tracking if user_id provided and tokens were used
        if user_id and results["total_tokens"] > 0:
            try:
                from calendar import monthrange
                now = datetime.utcnow()
                month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                _, last_day = monthrange(now.year, now.month)
                month_end = month_start.replace(day=last_day, hour=23, minute=59, second=59)

                usage = db.query(UsageTracking).filter(
                    UsageTracking.user_id == user_id,
                    UsageTracking.period_start == month_start,
                ).first()

                if not usage:
                    import uuid
                    usage = UsageTracking(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        period_start=month_start,
                        period_end=month_end,
                        ai_generations=0,
                        ai_tokens_used=0,
                    )
                    db.add(usage)

                usage.ai_generations = (usage.ai_generations or 0) + results["summarized"]
                usage.ai_tokens_used = (usage.ai_tokens_used or 0) + results["total_tokens"]
                db.commit()
                logger.info(f"Updated usage tracking: +{results['summarized']} generations, +{results['total_tokens']} tokens")
            except Exception as e:
                logger.error(f"Error updating usage tracking: {e}")

    return results


def get_opportunity_summary(opportunity_id: str, generate_if_missing: bool = True) -> Optional[Dict[str, Any]]:
    """
    Get a combined AI summary for an opportunity.

    First checks for PDF attachment summaries, then falls back to
    analyzing the opportunity description if no PDF summaries exist.
    """
    from app.database import SessionLocal
    from app.models import OpportunityAttachment, Opportunity

    with SessionLocal() as db:
        # Get all summarized attachments for this opportunity
        attachments = db.query(OpportunityAttachment).filter(
            OpportunityAttachment.opportunity_id == opportunity_id,
            OpportunityAttachment.ai_summary_status == "summarized",
            OpportunityAttachment.ai_summary.isnot(None)
        ).all()

        # If no PDF summaries, try to analyze the opportunity description
        if not attachments and generate_if_missing:
            opportunity = db.query(Opportunity).filter(
                Opportunity.id == opportunity_id
            ).first()

            if opportunity and opportunity.description:
                # Extract text from description (may contain HTML/JSON)
                desc_text = opportunity.description
                # Try to parse if it's JSON
                import json as json_module
                try:
                    if desc_text.startswith('{'):
                        parsed = json_module.loads(desc_text)
                        desc_text = parsed.get('description', desc_text)
                except:
                    pass

                # Strip HTML tags
                import re
                desc_text = re.sub(r'<[^>]+>', ' ', desc_text)
                desc_text = re.sub(r'&[a-zA-Z]+;', ' ', desc_text)  # HTML entities
                desc_text = re.sub(r'\s+', ' ', desc_text).strip()

                if len(desc_text) > 200:  # Only if substantial description
                    logger.info(f"Generating summary from description for {opportunity_id}")
                    summary = summarize_pdf_content(
                        text_content=desc_text,
                        attachment_name=f"Description: {opportunity.title[:50]}",
                        max_chars=50000
                    )

                    if summary.get("status") == "summarized":
                        summary["source_documents"] = ["Opportunity Description"]
                        return summary

            return None

        if not attachments:
            return None

        # If only one attachment, return its summary directly
        if len(attachments) == 1:
            summary = attachments[0].ai_summary.copy() if attachments[0].ai_summary else {}
            summary["source_documents"] = [attachments[0].name]
            return summary

        # Merge multiple summaries
        merged = {
            "summary": "",
            "period_of_performance": None,
            "contract_type": None,
            "clearance_required": None,
            "labor_categories": [],
            "technologies": [],
            "certifications_required": [],
            "location": None,
            "incumbent": None,
            "estimated_value": None,
            "key_dates": {},
            "evaluation_factors": [],
            "source_documents": []
        }

        summaries = []
        for att in attachments:
            if not att.ai_summary:
                continue

            merged["source_documents"].append(att.name)
            s = att.ai_summary

            # Collect summaries
            if s.get("summary"):
                summaries.append(s["summary"])

            # Take first non-null values for single fields
            for field in ["period_of_performance", "contract_type", "clearance_required",
                         "location", "incumbent", "estimated_value", "set_aside_info",
                         "naics_code", "contract_number"]:
                if s.get(field) and not merged.get(field):
                    merged[field] = s[field]

            # Merge arrays (deduplicate)
            for field in ["technologies", "certifications_required", "evaluation_factors"]:
                if s.get(field):
                    for item in s[field]:
                        if item and item not in merged[field]:
                            merged[field].append(item)

            # Merge labor categories
            if s.get("labor_categories"):
                for lc in s["labor_categories"]:
                    # Check if similar role already exists
                    exists = any(
                        existing.get("title", "").lower() == lc.get("title", "").lower()
                        for existing in merged["labor_categories"]
                    )
                    if not exists:
                        merged["labor_categories"].append(lc)

            # Merge key dates
            if s.get("key_dates"):
                for k, v in s["key_dates"].items():
                    if v and not merged["key_dates"].get(k):
                        merged["key_dates"][k] = v

        # Combine summaries
        if summaries:
            merged["summary"] = " ".join(summaries[:3])  # First 3 summaries

        return merged
