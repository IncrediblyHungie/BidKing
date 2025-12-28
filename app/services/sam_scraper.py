"""
SAM.gov Internal API Scraper

This scraper uses SAM.gov's internal APIs (used by the website frontend) to bypass
the strict rate limits of the public API (10-100 requests/day).

Internal APIs discovered:
- Search: https://sam.gov/api/prod/sgs/v1/search/?naics=541511
- Detail: https://sam.gov/api/prod/opps/v2/opportunities/{id}
- Resources: https://sam.gov/api/prod/opps/v3/opportunities/{id}/resources

These APIs:
- Require Accept: application/hal+json header
- Have no documented rate limits (be respectful with delays)
- Return complete data including NAICS, set-aside, place of performance
"""

import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import httpx

logger = logging.getLogger(__name__)

# API Endpoints
SEARCH_API = "https://sam.gov/api/prod/sgs/v1/search/"
DETAIL_API = "https://sam.gov/api/prod/opps/v2/opportunities/{notice_id}"
RESOURCES_API = "https://sam.gov/api/prod/opps/v3/opportunities/{notice_id}/resources"

# Headers required for internal API
HEADERS = {
    "Accept": "application/hal+json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# NAICS codes for IT/Data/Cloud services
# Primary codes (high volume, high competition)
DEFAULT_NAICS_CODES = [
    "541511",  # Custom Computer Programming Services (PRIMARY)
    "541512",  # Computer Systems Design Services
    "541519",  # Other Computer Related Services
    "518210",  # Data Processing/Hosting - AWS, ETL
    "541690",  # Scientific/Technical Consulting
]

# Expanded NAICS codes for underserved/adjacent markets
# These have lower competition but align with data/analytics/consulting skills
EXPANDED_NAICS_CODES = [
    # Primary (keep existing)
    "541511",  # Custom Computer Programming Services
    "541512",  # Computer Systems Design Services
    "541519",  # Other Computer Related Services
    "518210",  # Data Processing/Hosting - AWS, ETL
    "541690",  # Scientific/Technical Consulting
    # Adjacent markets (lower competition)
    "541611",  # Administrative Management Consulting (data strategy, process improvement)
    "519190",  # All Other Information Services (dashboards, reporting, data analysis)
    "611430",  # Professional Development Training (BI tools, Python, data analysis training)
    "541910",  # Marketing Research & Public Opinion Polling (data analysis, surveys)
    "541618",  # Other Management Consulting (IT strategy, digital transformation)
]


class SAMGovScraper:
    """
    Scraper for SAM.gov using internal APIs.

    Usage:
        scraper = SAMGovScraper()

        # Get opportunities with full details
        opportunities = scraper.get_opportunities_with_details(
            naics_code="541511",
            max_results=1000
        )
    """

    def __init__(self, delay_between_requests: float = 0.3):
        """
        Initialize the scraper.

        Args:
            delay_between_requests: Seconds to wait between API requests
        """
        self.delay = delay_between_requests
        self.client = httpx.Client(timeout=60.0, headers=HEADERS, follow_redirects=True)
        self._last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()

    def search_by_naics(
        self,
        naics_code: str,
        page: int = 0,
        page_size: int = 100,
        active_only: bool = True,
    ) -> Dict[str, Any]:
        """
        Search opportunities by NAICS code.

        Args:
            naics_code: The NAICS code to filter by (e.g., "541511")
            page: Page number (0-indexed)
            page_size: Results per page (max 100)
            active_only: Only return active opportunities

        Returns:
            Dict with 'results' list and 'total' count
        """
        self._rate_limit()

        params = {
            "index": "opp",
            "page": page,
            "size": min(page_size, 100),
            "sort": "-modifiedDate",
            "mode": "search",
            "naics": naics_code,  # This is the correct parameter!
        }

        if active_only:
            params["sfm[status][is_active]"] = "true"

        try:
            response = self.client.get(SEARCH_API, params=params)
            response.raise_for_status()
            data = response.json()

            results = data.get("_embedded", {}).get("results", [])
            total = data.get("page", {}).get("totalElements", 0)

            return {"results": results, "total": total, "page": page}

        except Exception as e:
            logger.error(f"Error searching NAICS {naics_code}: {e}")
            return {"results": [], "total": 0, "page": page, "error": str(e)}

    def get_opportunity_detail(self, notice_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full details for an opportunity.

        Returns complete data including:
        - NAICS codes
        - Set-aside type
        - Place of performance
        - Point of contact
        - Full description

        Args:
            notice_id: The opportunity notice ID

        Returns:
            Dict with full opportunity details, or None if not found
        """
        self._rate_limit()

        url = DETAIL_API.format(notice_id=notice_id)

        try:
            response = self.client.get(url)

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            # Handle case where API returns a list instead of dict
            if isinstance(data, list):
                if len(data) > 0:
                    data = data[0]
                else:
                    return None

            # Ensure we have a dict
            if not isinstance(data, dict):
                logger.warning(f"Unexpected data type for {notice_id}: {type(data)}")
                return None

            # Extract key fields from the nested structure
            data2 = data.get("data2") or data.get("data") or {}
            if not isinstance(data2, dict):
                data2 = {}
            description = data.get("description") or {}
            if not isinstance(description, dict):
                description = {"body": str(description) if description else ""}

            # Parse NAICS codes (with safe type checking)
            naics_list = data2.get("naics") or []
            if not isinstance(naics_list, list):
                naics_list = []
            primary_naics = None
            all_naics = []
            for n in naics_list:
                if isinstance(n, dict):
                    codes = n.get("code", [])
                    if isinstance(codes, list):
                        all_naics.extend(codes)
                        if n.get("type") == "primary" and codes:
                            primary_naics = codes[0]
                    elif isinstance(codes, str):
                        all_naics.append(codes)
                        if n.get("type") == "primary":
                            primary_naics = codes

            # Parse set-aside (with safe type checking)
            solicitation = data2.get("solicitation") or {}
            if not isinstance(solicitation, dict):
                solicitation = {}
            set_aside = solicitation.get("setAside")

            # Parse place of performance (with safe type checking)
            pop = data2.get("placeOfPerformance") or {}
            if not isinstance(pop, dict):
                pop = {}
            pop_city_obj = pop.get("city") or {}
            pop_state_obj = pop.get("state") or {}
            pop_country_obj = pop.get("country") or {}
            pop_city = pop_city_obj.get("name") if isinstance(pop_city_obj, dict) else None
            pop_state = pop_state_obj.get("code") if isinstance(pop_state_obj, dict) else None
            pop_country = pop_country_obj.get("code") if isinstance(pop_country_obj, dict) else None

            # Parse point of contact
            contacts = data2.get("pointOfContact") or []
            if not isinstance(contacts, list):
                contacts = []
            primary_contact = next((c for c in contacts if isinstance(c, dict) and c.get("type") == "primary"), None)

            # Parse deadlines
            deadlines = solicitation.get("deadlines") or {}
            if not isinstance(deadlines, dict):
                deadlines = {}
            response_deadline = deadlines.get("response")

            # Parse archive date safely
            archive = data2.get("archive") or {}
            archive_date = archive.get("date") if isinstance(archive, dict) else None

            return {
                "notice_id": notice_id,
                "title": data2.get("title"),
                "solicitation_number": data2.get("solicitationNumber"),
                "naics_code": primary_naics,
                "all_naics_codes": all_naics,
                "set_aside_type": set_aside,
                "pop_city": pop_city,
                "pop_state": pop_state,
                "pop_country": pop_country,
                "primary_contact": primary_contact,
                "response_deadline": response_deadline,
                "archive_date": archive_date,
                "description": description.get("body", "") if isinstance(description, dict) else "",
                "raw_data": data,
            }

        except Exception as e:
            logger.error(f"Error getting detail for {notice_id}: {e}")
            return None

    def get_attachments(self, notice_id: str) -> List[Dict[str, Any]]:
        """
        Get attachments for an opportunity.

        Args:
            notice_id: The opportunity notice ID

        Returns:
            List of attachment dictionaries with download URLs
        """
        self._rate_limit()

        url = RESOURCES_API.format(notice_id=notice_id)

        try:
            response = self.client.get(url)

            if response.status_code == 404:
                return []

            response.raise_for_status()
            data = response.json()

            attachments = []
            embedded = data.get("_embedded") or {}
            if not isinstance(embedded, dict):
                embedded = {}
            attachment_lists = embedded.get("opportunityAttachmentList") or []
            if not isinstance(attachment_lists, list):
                attachment_lists = []

            for att_list in attachment_lists:
                if not isinstance(att_list, dict):
                    continue
                att_items = att_list.get("attachments") or []
                if not isinstance(att_items, list):
                    continue
                for att in att_items:
                    if not isinstance(att, dict):
                        continue
                    if att.get("deletedFlag") == "1":
                        continue

                    resource_id = att.get("resourceId")
                    if resource_id:
                        att["download_url"] = (
                            f"https://sam.gov/api/prod/opps/v3/opportunities/{notice_id}"
                            f"/resources/files/{resource_id}/download"
                        )

                    attachments.append(att)

            return attachments

        except Exception as e:
            logger.error(f"Error getting attachments for {notice_id}: {e}")
            return []

    def get_opportunities_with_details(
        self,
        naics_code: str,
        max_results: int = 1000,
        include_attachments: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get opportunities with full details and attachments.

        This method:
        1. Searches by NAICS code
        2. Fetches full details for each opportunity
        3. Optionally fetches attachment metadata

        Args:
            naics_code: NAICS code to search
            max_results: Maximum opportunities to fetch
            include_attachments: Whether to fetch attachment info

        Returns:
            List of opportunities with full details
        """
        opportunities = []
        page = 0
        page_size = 100

        while len(opportunities) < max_results:
            # Search for opportunities
            search_result = self.search_by_naics(
                naics_code=naics_code,
                page=page,
                page_size=page_size,
            )

            results = search_result.get("results", [])
            if not results:
                break

            total = search_result.get("total", 0)
            logger.info(f"NAICS {naics_code}: Page {page + 1}, got {len(results)} of {total} total")

            for search_item in results:
                if len(opportunities) >= max_results:
                    break

                notice_id = search_item.get("_id")
                if not notice_id:
                    continue

                # Get full details
                detail = self.get_opportunity_detail(notice_id)
                if not detail:
                    continue

                # Add search-level data
                detail["published_date"] = search_item.get("publishDate")
                detail["modified_date"] = search_item.get("modifiedDate")
                detail["is_active"] = search_item.get("isActive", True)
                detail["notice_type"] = search_item.get("type", {}).get("value")

                # Get organization hierarchy (with null safety)
                org_hierarchy = search_item.get("organizationHierarchy") or []
                if not isinstance(org_hierarchy, list):
                    org_hierarchy = []
                detail["department"] = next(
                    (o["name"] for o in org_hierarchy if isinstance(o, dict) and o.get("type") == "DEPARTMENT"), None
                )
                detail["agency"] = next(
                    (o["name"] for o in org_hierarchy if isinstance(o, dict) and o.get("type") == "AGENCY"), None
                )
                detail["office"] = next(
                    (o["name"] for o in org_hierarchy if isinstance(o, dict) and o.get("type") == "OFFICE"), None
                )

                # Get attachments
                if include_attachments:
                    detail["attachments"] = self.get_attachments(notice_id)

                opportunities.append(detail)

            page += 1

            # Check if we've fetched all available
            if page * page_size >= total:
                break

        logger.info(f"NAICS {naics_code}: Fetched {len(opportunities)} opportunities with details")
        return opportunities

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def sync_opportunities_with_full_details(
    naics_code: str = "541511",
    max_results: int = 1000,
    biddable_only: bool = True,
) -> Dict[str, Any]:
    """
    Sync opportunities from SAM.gov with complete details.

    This function:
    1. Searches for opportunities by NAICS code
    2. Fetches full details (NAICS, set-aside, place of performance)
    3. Fetches attachment metadata
    4. Upserts into database (prevents duplicates via notice_id)
    5. Only creates new attachments (prevents duplicate AI processing)

    Args:
        naics_code: NAICS code to sync (default: 541511 Custom Programming)
        max_results: Maximum opportunities to fetch
        biddable_only: If True, only sync opportunities that are still biddable
                       (Solicitation, Presolicitation, Combined, Sources Sought with future deadline)

    Returns:
        Dictionary with sync statistics
    """
    from app.database import SessionLocal
    from app.models import Opportunity, OpportunityAttachment

    stats = {
        "naics_code": naics_code,
        "opportunities_found": 0,
        "opportunities_created": 0,
        "opportunities_updated": 0,
        "attachments_created": 0,
        "attachments_skipped": 0,
        "skipped_not_biddable": 0,
        "errors": 0,
    }

    # Biddable notice types
    BIDDABLE_TYPES = ["Solicitation", "Presolicitation", "Combined Synopsis/Solicitation", "Sources Sought"]

    logger.info(f"Starting sync for NAICS {naics_code}, max {max_results} opportunities (biddable_only={biddable_only})")

    with SAMGovScraper(delay_between_requests=0.3) as scraper:
        opportunities = scraper.get_opportunities_with_details(
            naics_code=naics_code,
            max_results=max_results,
            include_attachments=True,
        )

        stats["opportunities_found"] = len(opportunities)
        logger.info(f"Found {len(opportunities)} opportunities to sync")

        with SessionLocal() as db:
            for opp in opportunities:
                try:
                    notice_id = opp.get("notice_id")
                    if not notice_id:
                        continue

                    # Parse dates
                    posted_date = _parse_iso_date(opp.get("published_date"))
                    response_deadline = _parse_iso_date(opp.get("response_deadline"))
                    notice_type = opp.get("notice_type")

                    # Filter for biddable opportunities only
                    if biddable_only:
                        is_biddable_type = notice_type in BIDDABLE_TYPES
                        has_future_deadline = response_deadline and response_deadline > datetime.utcnow()

                        if not is_biddable_type or not has_future_deadline:
                            stats["skipped_not_biddable"] += 1
                            continue

                    # Check if opportunity already exists
                    existing = db.query(Opportunity).filter(
                        Opportunity.notice_id == notice_id
                    ).first()

                    opp_data = {
                        "solicitation_number": opp.get("solicitation_number"),
                        "title": (opp.get("title") or "")[:500],
                        "description": opp.get("description", ""),
                        "posted_date": posted_date,
                        "response_deadline": response_deadline,
                        "notice_type": notice_type,
                        "naics_code": opp.get("naics_code"),
                        "agency_name": opp.get("agency") or opp.get("department"),
                        "department_name": opp.get("department"),
                        "office_name": opp.get("office"),
                        "set_aside_type": opp.get("set_aside_type"),
                        "pop_city": opp.get("pop_city"),
                        "pop_state": opp.get("pop_state"),
                        "likelihood_score": 50,
                        "ui_link": f"https://sam.gov/opp/{notice_id}/view",
                        "raw_data": opp.get("raw_data"),
                        "status": "active" if opp.get("is_active") else "archived",
                        "fetched_at": datetime.utcnow(),
                    }

                    if existing:
                        # Update existing opportunity
                        for key, value in opp_data.items():
                            setattr(existing, key, value)
                        existing.updated_at = datetime.utcnow()
                        db_opp = existing
                        stats["opportunities_updated"] += 1
                    else:
                        # Create new opportunity
                        db_opp = Opportunity(
                            id=uuid.uuid4(),
                            notice_id=notice_id,
                            **opp_data
                        )
                        db.add(db_opp)
                        db.flush()  # Get the ID for attachments
                        stats["opportunities_created"] += 1

                    # Process attachments (only create new ones)
                    for att_data in opp.get("attachments", []):
                        download_url = att_data.get("download_url")
                        if not download_url:
                            continue

                        # Check if attachment already exists (prevents duplicate AI processing)
                        existing_att = db.query(OpportunityAttachment).filter(
                            OpportunityAttachment.opportunity_id == db_opp.id,
                            OpportunityAttachment.url == download_url
                        ).first()

                        if existing_att:
                            stats["attachments_skipped"] += 1
                            continue

                        # Create new attachment
                        att = OpportunityAttachment(
                            id=uuid.uuid4(),
                            opportunity_id=db_opp.id,
                            name=att_data.get("name"),
                            description=None,
                            url=download_url,
                            resource_type=att_data.get("type", "file"),
                            file_type=att_data.get("mimeType"),
                            file_size=att_data.get("size"),
                            extraction_status="pending",
                            # ai_summary is NULL - will be processed by AI job
                        )
                        db.add(att)
                        stats["attachments_created"] += 1

                    # Commit periodically
                    if (stats["opportunities_created"] + stats["opportunities_updated"]) % 50 == 0:
                        db.commit()
                        logger.info(
                            f"Progress: {stats['opportunities_created']} created, "
                            f"{stats['opportunities_updated']} updated, "
                            f"{stats['attachments_created']} attachments"
                        )

                except Exception as e:
                    logger.warning(f"Error processing opportunity: {e}")
                    stats["errors"] += 1
                    continue

            db.commit()

    logger.info(
        f"Sync completed for NAICS {naics_code}: "
        f"{stats['opportunities_created']} created, {stats['opportunities_updated']} updated, "
        f"{stats['attachments_created']} new attachments, {stats['attachments_skipped']} att skipped, "
        f"{stats['skipped_not_biddable']} skipped (not biddable)"
    )

    return stats


def _parse_iso_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO format date string."""
    if not date_str:
        return None
    try:
        date_str = date_str.replace("Z", "+00:00")
        if "+" in date_str:
            date_str = date_str.split("+")[0]
        if "." in date_str:
            date_str = date_str.split(".")[0]
        return datetime.fromisoformat(date_str)
    except Exception:
        return None


# Quick test function
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    with SAMGovScraper() as scraper:
        print("Testing SAM.gov Internal API Scraper")
        print("=" * 60)

        # Test search
        print("\n1. Searching for NAICS 541511...")
        result = scraper.search_by_naics("541511", page=0, page_size=5)
        print(f"   Total opportunities: {result['total']:,}")

        if result["results"]:
            # Test detail
            notice_id = result["results"][0]["_id"]
            print(f"\n2. Getting details for {notice_id[:20]}...")
            detail = scraper.get_opportunity_detail(notice_id)
            if detail:
                print(f"   NAICS: {detail['naics_code']}")
                print(f"   Set-aside: {detail['set_aside_type']}")
                print(f"   Location: {detail['pop_city']}, {detail['pop_state']}")

            # Test attachments
            print(f"\n3. Getting attachments...")
            attachments = scraper.get_attachments(notice_id)
            print(f"   Found {len(attachments)} attachments")
            for att in attachments[:3]:
                print(f"   - {att.get('name')} ({att.get('size'):,} bytes)")
