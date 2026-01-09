"""
Local LLM Service for AI Analysis

Uses your GPU via Ollama to analyze federal contract PDFs locally.
This avoids paying for Claude API calls while leveraging your hardware.

Supported models (via Ollama):
- Qwen2.5-14B (currently running)
- Llama 3.1 70B (if you have enough VRAM)
- Mistral 7B (lightweight option)

Usage:
    from app.services.local_llm import LocalLLMService

    service = LocalLLMService()
    summary = service.analyze_contract(pdf_text)

Benefits:
- FREE - No API costs
- FAST - Local GPU inference
- PRIVATE - Data never leaves your machine
- UNLIMITED - No rate limits
"""

import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

# Default Ollama endpoint
OLLAMA_URL = "http://localhost:11434"

# AI Analysis prompt (same schema as Claude version)
ANALYSIS_PROMPT = """You are a federal contracting expert. Analyze this solicitation document and extract structured information.

DOCUMENT TEXT:
{text}

Respond with a JSON object containing:

{{
    "summary": "2-3 sentence plain English description of what the government is buying",
    "estimated_value": {{
        "low": <number or null>,
        "high": <number or null>,
        "basis": "Explain how you calculated this estimate (labor categories × rates × duration, or similar contracts, etc.)"
    }},
    "period_of_performance": "e.g., '1 base year + 4 option years' or '5 years'",
    "contract_type": "Firm Fixed Price | Time & Materials | Cost Plus | IDIQ | BPA",
    "clearance_required": "None | Public Trust | Secret | Top Secret | TS/SCI",
    "labor_categories": [
        {{"title": "role name", "quantity": 2, "level": "Senior/Mid/Junior"}}
    ],
    "technologies": ["specific tools, platforms, languages mentioned"],
    "certifications_required": ["CMMI", "ISO 27001", "FedRAMP", etc.],
    "location": "Remote | On-site: City, State | Hybrid",
    "incumbent": "Current contractor name if this is a recompete, or null",
    "key_dates": {{
        "proposal_due": "YYYY-MM-DD or null",
        "questions_due": "YYYY-MM-DD or null"
    }},
    "evaluation_factors": ["Technical Approach", "Past Performance", "Price", etc.],
    "small_business_set_aside": "8(a) | SDVOSB | HUBZone | WOSB | SBA | None",
    "naics_codes": ["541511", etc.],
    "deliverables": ["Monthly status reports", "Software deliverables", etc.]
}}

If information is not available in the document, use null for that field.
For estimated_value, try to calculate from labor rates × FTEs × duration, or reference similar contracts.
Be specific about technologies and tools mentioned (e.g., "Python 3.10", not just "Python").

IMPORTANT: Respond with ONLY the JSON object, no additional text."""


class LocalLLMService:
    """
    Service for running AI analysis locally using Ollama.

    Uses your GPU for fast, free inference without API costs.
    """

    def __init__(
        self,
        base_url: str = OLLAMA_URL,
        model: str = "qwen2.5:14b",  # Default model
        timeout: float = 300.0,  # 5 minute timeout for long documents
    ):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self._available_models: Optional[List[str]] = None

    def check_connection(self) -> Dict[str, Any]:
        """Check if Ollama is running and accessible."""
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = [m["name"] for m in data.get("models", [])]
                    self._available_models = models
                    return {
                        "status": "connected",
                        "available_models": models,
                        "current_model": self.model,
                        "model_available": self.model in models or any(self.model in m for m in models),
                    }
                else:
                    return {"status": "error", "message": f"HTTP {response.status_code}"}
        except httpx.ConnectError:
            return {"status": "error", "message": "Cannot connect to Ollama. Is it running?"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def list_models(self) -> List[str]:
        """List available Ollama models."""
        if self._available_models is not None:
            return self._available_models

        status = self.check_connection()
        return status.get("available_models", [])

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,  # Low temp for structured output
        max_tokens: int = 4096,
    ) -> Optional[str]:
        """
        Generate a completion using Ollama.

        Args:
            prompt: The user prompt
            system: Optional system prompt
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text or None on error
        """
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }

            if system:
                payload["system"] = system

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("response", "")
                else:
                    logger.error(f"Ollama error: HTTP {response.status_code}")
                    return None

        except httpx.TimeoutException:
            logger.error("Ollama request timed out")
            return None
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return None

    def analyze_contract(
        self,
        text: str,
        max_text_length: int = 50000,  # Limit input to avoid context overflow
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a federal contract document and extract structured information.

        Args:
            text: The PDF text content
            max_text_length: Maximum text length to process

        Returns:
            Structured analysis dict or None on error
        """
        if not text or len(text.strip()) < 100:
            logger.warning("Text too short for analysis")
            return None

        # Truncate if too long
        if len(text) > max_text_length:
            text = text[:max_text_length] + "\n\n[... document truncated for analysis ...]"

        prompt = ANALYSIS_PROMPT.format(text=text)

        result = self.generate(
            prompt=prompt,
            temperature=0.1,
            max_tokens=4096,
        )

        if not result:
            return None

        # Parse JSON response
        try:
            # Try to extract JSON from the response
            result = result.strip()

            # Handle markdown code blocks
            if result.startswith("```json"):
                result = result[7:]
            if result.startswith("```"):
                result = result[3:]
            if result.endswith("```"):
                result = result[:-3]

            # Find JSON object
            start_idx = result.find("{")
            end_idx = result.rfind("}") + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = result[start_idx:end_idx]
                analysis = json.loads(json_str)
                return analysis
            else:
                logger.warning("No JSON object found in response")
                return None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response was: {result[:500]}...")
            return None

    def batch_analyze(
        self,
        texts: List[Dict[str, Any]],  # List of {"id": str, "text": str}
        progress_callback: Optional[callable] = None,
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple documents.

        Args:
            texts: List of dicts with "id" and "text" keys
            progress_callback: Optional callback(current, total, id)

        Returns:
            List of results with "id", "analysis", "error"
        """
        results = []
        total = len(texts)

        for i, item in enumerate(texts):
            doc_id = item.get("id")
            text = item.get("text")

            if progress_callback:
                progress_callback(i + 1, total, doc_id)

            try:
                analysis = self.analyze_contract(text)
                results.append({
                    "id": doc_id,
                    "analysis": analysis,
                    "error": None if analysis else "Analysis failed",
                })
            except Exception as e:
                results.append({
                    "id": doc_id,
                    "analysis": None,
                    "error": str(e),
                })

        return results


def analyze_pending_attachments(
    limit: int = 50,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Analyze pending PDF attachments using local LLM.

    This is the equivalent of the Claude-based AI summarization,
    but runs locally on your GPU for free.

    Args:
        limit: Maximum attachments to process
        force: Re-analyze even if already done

    Returns:
        Stats dict
    """
    from app.database import SessionLocal
    from app.models import OpportunityAttachment

    service = LocalLLMService()

    # Check connection
    status = service.check_connection()
    if status["status"] != "connected":
        return {
            "error": f"Ollama not available: {status.get('message')}",
            "hint": "Make sure Ollama is running: ollama serve",
        }

    stats = {
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "model": service.model,
        "started_at": datetime.utcnow().isoformat(),
    }

    with SessionLocal() as db:
        # Get attachments to process
        query = db.query(OpportunityAttachment).filter(
            OpportunityAttachment.extraction_status == "extracted",
            OpportunityAttachment.text_content.isnot(None),
        )

        if not force:
            query = query.filter(
                (OpportunityAttachment.ai_summary_status.is_(None)) |
                (OpportunityAttachment.ai_summary_status == "pending")
            )

        attachments = query.limit(limit).all()

        logger.info(f"Processing {len(attachments)} attachments with local LLM")

        for att in attachments:
            stats["processed"] += 1

            try:
                analysis = service.analyze_contract(att.text_content)

                if analysis:
                    att.ai_summary = analysis
                    att.ai_summary_status = "summarized"
                    att.ai_summarized_at = datetime.utcnow()
                    stats["succeeded"] += 1

                    # Also update opportunity with AI estimated values
                    if analysis.get("estimated_value"):
                        from app.models import Opportunity
                        opp = db.query(Opportunity).filter(
                            Opportunity.id == att.opportunity_id
                        ).first()
                        if opp:
                            est = analysis["estimated_value"]
                            opp.ai_estimated_value_low = est.get("low")
                            opp.ai_estimated_value_high = est.get("high")
                            opp.ai_estimated_value_basis = est.get("basis")

                    logger.info(f"Analyzed attachment {att.id}")
                else:
                    att.ai_summary_status = "failed"
                    stats["failed"] += 1
                    logger.warning(f"Analysis failed for {att.id}")

            except Exception as e:
                att.ai_summary_status = "failed"
                stats["failed"] += 1
                logger.error(f"Error analyzing {att.id}: {e}")

            # Commit every 5 to avoid losing progress
            if stats["processed"] % 5 == 0:
                db.commit()

        db.commit()

    stats["completed_at"] = datetime.utcnow().isoformat()
    logger.info(f"Local LLM analysis complete: {stats['succeeded']} succeeded, {stats['failed']} failed")

    return stats


# CLI for testing
if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("BidKing Local LLM Service (Ollama)")
    print("=" * 60)

    service = LocalLLMService()

    print("\nChecking Ollama connection...")
    status = service.check_connection()

    if status["status"] == "connected":
        print(f"  Status: Connected")
        print(f"  Available models: {', '.join(status['available_models'])}")
        print(f"  Current model: {service.model}")
        print(f"  Model available: {status['model_available']}")

        if len(sys.argv) > 1 and sys.argv[1] == "--test":
            print("\nRunning test analysis...")
            test_text = """
            This is a Sources Sought notice for IT Support Services.
            The requirement is for 2 Senior Software Engineers and
            1 Junior Developer for a 1 base year + 4 option year contract.
            Work is hybrid, 3 days on-site in Washington DC.
            Clearance required: Secret.
            Technologies: Python, AWS, Docker, Kubernetes.
            Estimated total value: $2-3 million.
            """
            result = service.analyze_contract(test_text)
            if result:
                print("\nAnalysis result:")
                print(json.dumps(result, indent=2))
            else:
                print("\nAnalysis failed!")
    else:
        print(f"  Error: {status['message']}")
        print("\nTo start Ollama:")
        print("  ollama serve")
        print("\nTo install Qwen2.5:")
        print("  ollama pull qwen2.5:14b")
