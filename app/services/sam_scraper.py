"""
SAM.gov Mass Scraper with Residential Proxy Rotation

This scraper uses SAM.gov's internal APIs with residential proxy rotation to
bypass rate limits and scrape all federal contract opportunities.

Features:
- 215K+ residential proxy rotation
- Concurrent async requests
- PostgreSQL storage
- Resume capability for interrupted scrapes
- Rate limiting and backoff
- STALL DETECTION with auto-recovery

NO API KEY REQUIRED - Uses SAM.gov internal API endpoints.

Integrated from sam-mass-scraper for BidKing production use.
"""

import asyncio
import logging
import random
import uuid
import time
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Set
from collections import deque

import httpx

from app.services.proxy_manager import ProxyManager, get_proxy_manager
from app.services.scoring import calculate_likelihood_score

logger = logging.getLogger(__name__)


# SAM.gov internal API endpoints (no API key required)
SAM_SEARCH_URL = "https://sam.gov/api/prod/sgs/v1/search/"
SAM_DETAILS_URL = "https://sam.gov/api/prod/opps/v2/opportunities"
SAM_RESOURCES_URL = "https://sam.gov/api/prod/opps/v3/opportunities"

# API Endpoints (for backwards compatibility)
SEARCH_API = SAM_SEARCH_URL
DETAIL_API = "https://sam.gov/api/prod/opps/v2/opportunities/{notice_id}"
RESOURCES_API = "https://sam.gov/api/prod/opps/v3/opportunities/{notice_id}/resources"

# Headers required for internal API
HEADERS = {
    "Accept": "application/hal+json, application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://sam.gov/search/",
    "Origin": "https://sam.gov",
}

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# NAICS codes for IT/Data/Cloud services
DEFAULT_NAICS_CODES = [
    "541511",  # Custom Computer Programming Services (PRIMARY)
    "541512",  # Computer Systems Design Services
    "541519",  # Other Computer Related Services
    "518210",  # Data Processing/Hosting - AWS, ETL
    "541690",  # Scientific/Technical Consulting
]

# Expanded NAICS codes for underserved/adjacent markets
EXPANDED_NAICS_CODES = [
    # Primary
    "541511",  # Custom Computer Programming Services
    "541512",  # Computer Systems Design Services
    "541519",  # Other Computer Related Services
    "518210",  # Data Processing/Hosting - AWS, ETL
    "541690",  # Scientific/Technical Consulting
    # Adjacent markets
    "541611",  # Administrative Management Consulting
    "519190",  # All Other Information Services
    "611430",  # Professional Development Training
    "541910",  # Marketing Research & Public Opinion Polling
    "541618",  # Other Management Consulting
]


def get_headers() -> Dict[str, str]:
    """Get request headers with random user agent"""
    headers = HEADERS.copy()
    headers["User-Agent"] = random.choice(USER_AGENTS)
    return headers


def safe_get(obj: Any, *keys, default=None) -> Any:
    """Safely get nested dictionary values"""
    for key in keys:
        if obj is None or not isinstance(obj, dict):
            return default
        obj = obj.get(key)
    return obj if obj is not None else default


class StallDetector:
    """Detects when the scraper has stalled and triggers recovery."""

    def __init__(self, stall_threshold_seconds: int = 60, min_progress_count: int = 5):
        self.stall_threshold = stall_threshold_seconds
        self.min_progress = min_progress_count
        self.progress_times: deque = deque(maxlen=100)
        self.last_progress_time = time.time()
        self.total_progress = 0
        self.consecutive_failures = 0
        self.max_consecutive_failures = 10

    def record_progress(self, count: int = 1):
        """Record that progress was made."""
        now = time.time()
        self.last_progress_time = now
        self.consecutive_failures = 0
        if count > 0:
            self.progress_times.append(now)
            self.total_progress += count

    def record_failure(self):
        """Record a failure."""
        self.consecutive_failures += 1

    def is_stalled(self) -> bool:
        """Check if the scraper appears to be stalled."""
        elapsed = time.time() - self.last_progress_time
        return elapsed > self.stall_threshold

    def should_abort(self) -> bool:
        """Check if we should abort due to too many consecutive failures."""
        return self.consecutive_failures >= self.max_consecutive_failures

    def get_rate(self) -> float:
        """Get recent items per second rate."""
        if len(self.progress_times) < 2:
            return 0.0

        time_span = self.progress_times[-1] - self.progress_times[0]
        if time_span <= 0:
            return 0.0
        return len(self.progress_times) / time_span


class SAMScraper:
    """
    Mass scraper for SAM.gov federal contract opportunities.

    Features:
    - Concurrent async requests with configurable parallelism
    - Automatic proxy rotation through 215K residential proxies
    - PostgreSQL storage with resume capability
    - Rate limiting and backoff on errors
    - STALL DETECTION with automatic recovery
    """

    def __init__(
        self,
        proxy_file: Optional[str] = None,
        concurrent_requests: int = 10,
        page_size: int = 100,
        request_delay: float = 0.5,
        max_retries: int = 3,
        timeout: float = 60.0,
        stall_threshold: int = 90,
        use_proxies: bool = True,
    ):
        # Use provided proxy file or get global manager
        if proxy_file:
            from app.services.proxy_manager import ProxyManager
            self.proxy_manager = ProxyManager(proxy_file)
        else:
            self.proxy_manager = get_proxy_manager()

        self.use_proxies = use_proxies and self.proxy_manager.has_proxies()
        self.concurrent_requests = concurrent_requests
        self.page_size = page_size
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.timeout = timeout

        # Track state
        self.session_id = str(uuid.uuid4())[:8]
        self.scraped_ids: Set[str] = set()
        self.total_scraped = 0
        self.total_errors = 0

        # Stall detection
        self.stall_detector = StallDetector(stall_threshold_seconds=stall_threshold)

        # Blocking detection
        self.consecutive_403s = 0
        self.consecutive_timeouts = 0

        # Semaphore for rate limiting
        self._semaphore = asyncio.Semaphore(concurrent_requests)

        # Pending saves buffer
        self._pending_saves: List[Dict] = []
        self._save_batch_size = 10

    async def _make_request(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[Dict] = None,
        retry_count: int = 0,
    ) -> Optional[Dict]:
        """Make an HTTP request with proxy rotation and retry logic."""
        proxy = None
        proxy_url = None

        if self.use_proxies:
            proxy = self.proxy_manager.get_proxy()
            if proxy:
                proxy_url = proxy.url

        try:
            async with self._semaphore:
                if proxy_url:
                    async with httpx.AsyncClient(
                        timeout=self.timeout,
                        follow_redirects=True,
                        proxy=proxy_url,
                    ) as proxy_client:
                        response = await proxy_client.get(
                            url,
                            params=params,
                            headers=get_headers(),
                        )
                else:
                    response = await client.get(url, params=params, headers=get_headers())

                # Reset error counters on success
                self.consecutive_403s = 0
                self.consecutive_timeouts = 0

                response.raise_for_status()

                if proxy:
                    self.proxy_manager.mark_success(proxy)

                await asyncio.sleep(self.request_delay + random.uniform(0, 0.5))
                return response.json()

        except httpx.HTTPStatusError as e:
            if proxy:
                self.proxy_manager.mark_failure(proxy)

            status_code = e.response.status_code

            if status_code == 403:
                self.consecutive_403s += 1
                logger.warning(f"403 Forbidden - Count: {self.consecutive_403s}")
                if self.consecutive_403s >= 5:
                    await asyncio.sleep(30)
                    self.consecutive_403s = 0

            elif status_code == 429:
                logger.warning(f"Rate limited (429), backing off...")
                await asyncio.sleep(10 + random.uniform(0, 10))

            elif status_code >= 500:
                logger.warning(f"Server error {status_code}, retrying...")
                await asyncio.sleep(2)

            if retry_count < self.max_retries:
                return await self._make_request(client, url, params, retry_count + 1)

            self.stall_detector.record_failure()
            logger.error(f"Request failed after {retry_count + 1} attempts: HTTP {status_code}")
            return None

        except httpx.TimeoutException:
            if proxy:
                self.proxy_manager.mark_failure(proxy)

            self.consecutive_timeouts += 1
            if self.consecutive_timeouts >= 5:
                await asyncio.sleep(10)
                self.consecutive_timeouts = 0

            if retry_count < self.max_retries:
                await asyncio.sleep(2)
                return await self._make_request(client, url, params, retry_count + 1)

            self.stall_detector.record_failure()
            logger.error(f"Request timed out after {retry_count + 1} attempts")
            return None

        except httpx.RequestError as e:
            if proxy:
                self.proxy_manager.mark_failure(proxy)

            if retry_count < self.max_retries:
                await asyncio.sleep(1 + random.uniform(0, 2))
                return await self._make_request(client, url, params, retry_count + 1)

            self.stall_detector.record_failure()
            logger.error(f"Request failed: {e}")
            return None

    async def search_page(
        self,
        client: httpx.AsyncClient,
        page: int,
        naics_code: Optional[str] = None,
        posted_from: Optional[str] = None,
        posted_to: Optional[str] = None,
        active_only: bool = False,
    ) -> tuple[List[Dict], int]:
        """Search for opportunities on a specific page."""
        params = {
            "random": int(datetime.now(timezone.utc).timestamp()),
            "index": "opp",
            "page": page,
            "mode": "search",
            "sort": "-modifiedDate",
            "size": self.page_size,
        }

        if naics_code:
            params["naics"] = naics_code

        if active_only:
            params["sfm[status][is_active]"] = "true"

        if posted_from:
            params["postedFrom"] = posted_from
        if posted_to:
            params["postedTo"] = posted_to

        data = await self._make_request(client, SAM_SEARCH_URL, params)
        if not data:
            return [], 0

        results = data.get("_embedded", {}).get("results", [])
        total = data.get("page", {}).get("totalElements", 0)

        logger.info(f"Page {page + 1}: Found {len(results)} opportunities (total: {total:,})")
        return results, total

    async def get_opportunity_details(
        self,
        client: httpx.AsyncClient,
        opp_id: str,
    ) -> Optional[Dict]:
        """Get full details for an opportunity"""
        url = f"{SAM_DETAILS_URL}/{opp_id}"
        return await self._make_request(client, url)

    async def get_attachments(
        self,
        client: httpx.AsyncClient,
        opp_id: str,
    ) -> List[Dict]:
        """Get attachment metadata for an opportunity"""
        url = f"{SAM_RESOURCES_URL}/{opp_id}/resources"
        data = await self._make_request(client, url)

        if not data:
            return []

        attachments = []
        attachment_lists = data.get("_embedded", {}).get("opportunityAttachmentList", [])

        for att_list in attachment_lists:
            for att in att_list.get("attachments", []) or []:
                if not att or att.get("deletedFlag") == "1":
                    continue

                resource_id = att.get("resourceId")
                if not resource_id:
                    continue

                attachments.append({
                    "resourceId": resource_id,
                    "filename": att.get("name", "unknown"),
                    "type": att.get("mimeType", ""),
                    "size": att.get("size", 0),
                    "accessLevel": att.get("accessLevel", "public"),
                    "postedDate": att.get("postedDate"),
                    "downloadUrl": f"https://sam.gov/api/prod/opps/v3/opportunities/resources/files/{resource_id}/download",
                })

        return attachments

    async def process_opportunity(
        self,
        client: httpx.AsyncClient,
        opp: Dict,
    ) -> Optional[Dict]:
        """Process a single opportunity with details and attachments"""
        opp_id = opp.get("_id", "")

        if opp_id in self.scraped_ids:
            return None

        try:
            # Extract basic data from search result
            org_hierarchy = opp.get("organizationHierarchy", []) or []
            agency_name = org_hierarchy[0].get("name") if org_hierarchy else None
            sub_agency_name = org_hierarchy[1].get("name") if len(org_hierarchy) > 1 else None
            office_name = org_hierarchy[-1].get("name") if org_hierarchy else None

            descriptions = opp.get("descriptions", []) or []
            description = descriptions[0].get("content", "") if descriptions else ""

            # Build base record
            opportunity_data = {
                "opportunityId": opp_id,
                "solicitationNumber": opp.get("solicitationNumber"),
                "title": opp.get("title"),
                "description": description,
                "type": safe_get(opp, "type", "value"),
                "typeCode": safe_get(opp, "type", "code"),
                "postedDate": opp.get("publishDate"),
                "modifiedDate": opp.get("modifiedDate"),
                "responseDeadline": opp.get("responseDate"),
                "responseTimeZone": opp.get("responseTimeZone"),
                "isActive": opp.get("isActive"),
                "isCanceled": opp.get("isCanceled"),
                "agencyName": agency_name,
                "subAgencyName": sub_agency_name,
                "officeName": office_name,
                "samGovLink": f"https://sam.gov/opp/{opp_id}/view",
                "contacts": [],
                "attachments": [],
                "scrapedAt": datetime.now(timezone.utc).isoformat(),
            }

            # Get detailed data
            details = await self.get_opportunity_details(client, opp_id)
            if details:
                data2 = details.get("data2", {}) or {}

                # NAICS codes
                naics_list = data2.get("naics", []) or []
                if naics_list:
                    primary_naics = naics_list[0].get("code", []) or []
                    opportunity_data["naicsCode"] = primary_naics[0] if primary_naics else None

                # PSC code
                opportunity_data["pscCode"] = data2.get("classificationCode")

                # Set-aside
                set_aside = data2.get("typeOfSetAside")
                if set_aside and isinstance(set_aside, dict):
                    opportunity_data["setAsideType"] = set_aside.get("code")
                    opportunity_data["setAsideDescription"] = set_aside.get("value")

                # Place of performance
                pop = data2.get("placeOfPerformance") or {}
                opportunity_data["placeOfPerformance"] = {
                    "city": safe_get(pop, "city", "name"),
                    "state": safe_get(pop, "state", "name"),
                    "stateCode": safe_get(pop, "state", "code"),
                    "country": safe_get(pop, "country", "name"),
                    "countryCode": safe_get(pop, "country", "code"),
                }

                # Contacts
                for contact in (data2.get("pointOfContact") or []):
                    if contact:
                        opportunity_data["contacts"].append({
                            "name": contact.get("fullName"),
                            "email": contact.get("email"),
                            "phone": contact.get("phone"),
                            "title": contact.get("title"),
                            "type": contact.get("type"),
                        })

                # Award info
                award = data2.get("award")
                if award and isinstance(award, dict):
                    awardee = award.get("awardee") or {}
                    opportunity_data["award"] = {
                        "amount": award.get("amount"),
                        "awardee": awardee.get("name") if isinstance(awardee, dict) else None,
                        "awardeeUei": awardee.get("ueiSAM") if isinstance(awardee, dict) else None,
                    }

            # Get attachments metadata
            opportunity_data["attachments"] = await self.get_attachments(client, opp_id)

            return opportunity_data

        except Exception as e:
            logger.error(f"Error processing {opp_id}: {e}")
            self.total_errors += 1
            self.stall_detector.record_failure()
            return None

    async def scrape_naics(
        self,
        naics_code: str,
        days_back: int = 30,
        max_results: int = 10000,
        active_only: bool = True,
        save_to_db: bool = True,
    ) -> Dict[str, Any]:
        """
        Scrape all opportunities for a NAICS code.

        Args:
            naics_code: The NAICS code to scrape
            days_back: How many days back to scrape
            max_results: Maximum opportunities to scrape
            active_only: Only scrape active opportunities
            save_to_db: Whether to save to BidKing database

        Returns:
            Dictionary with scraping statistics
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)

        posted_from = start_date.strftime("%m/%d/%Y")
        posted_to = end_date.strftime("%m/%d/%Y")

        logger.info(f"Scraping NAICS {naics_code}: {posted_from} to {posted_to}")

        if self.use_proxies:
            logger.info(f"Using {self.proxy_manager.active_count:,} proxies")
        else:
            logger.info("Proxies not available, using direct connection")

        stats = {
            "naics_code": naics_code,
            "opportunities_found": 0,
            "opportunities_scraped": 0,
            "opportunities_saved": 0,
            "attachments_found": 0,
            "errors": 0,
            "duration_seconds": 0,
        }

        start_time = time.time()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # First, get total count
            _, total = await self.search_page(
                client, 0, naics_code, posted_from, posted_to, active_only
            )

            stats["opportunities_found"] = min(total, max_results)

            if total == 0:
                logger.warning(f"No opportunities found for NAICS {naics_code}")
                return stats

            logger.info(f"Target: {min(total, max_results):,} opportunities")
            total_pages = (min(total, max_results) + self.page_size - 1) // self.page_size

            page = 0
            opportunities_processed = 0

            while page < total_pages and opportunities_processed < max_results:
                # Check for stall
                if self.stall_detector.is_stalled():
                    logger.warning("Stall detected, backing off...")
                    await asyncio.sleep(30)
                    self.stall_detector.last_progress_time = time.time()
                    continue

                results, _ = await self.search_page(
                    client, page, naics_code, posted_from, posted_to, active_only
                )

                if not results:
                    break

                # Process opportunities concurrently
                tasks = []
                for opp in results:
                    if opportunities_processed >= max_results:
                        break
                    tasks.append(self.process_opportunity(client, opp))
                    opportunities_processed += 1

                if tasks:
                    processed = await asyncio.gather(*tasks, return_exceptions=True)

                    for data in processed:
                        if isinstance(data, Exception):
                            stats["errors"] += 1
                            continue
                        if data:
                            stats["opportunities_scraped"] += 1
                            stats["attachments_found"] += len(data.get("attachments", []))

                            if save_to_db:
                                saved = await self._save_opportunity(data)
                                if saved:
                                    stats["opportunities_saved"] += 1

                            self.stall_detector.record_progress()

                page += 1

                # Progress log
                if page % 5 == 0:
                    rate = self.stall_detector.get_rate()
                    logger.info(
                        f"Progress: Page {page}/{total_pages}, "
                        f"Scraped: {stats['opportunities_scraped']:,}, "
                        f"Rate: {rate:.1f}/sec"
                    )

        stats["duration_seconds"] = time.time() - start_time
        logger.info(f"Completed NAICS {naics_code}: {stats['opportunities_scraped']} scraped in {stats['duration_seconds']:.0f}s")

        return stats

    async def _save_opportunity(self, data: Dict) -> bool:
        """Save an opportunity to the BidKing database."""
        from app.database import SessionLocal
        from app.models import Opportunity, PointOfContact, OpportunityAttachment

        try:
            with SessionLocal() as db:
                notice_id = data["opportunityId"]

                # Check if exists
                existing = db.query(Opportunity).filter(
                    Opportunity.notice_id == notice_id
                ).first()

                # Parse dates
                posted_date = _parse_iso_date(data.get("postedDate"))
                response_deadline = _parse_iso_date(data.get("responseDeadline"))

                # Determine status
                if data.get("isCanceled"):
                    status = "canceled"
                elif not data.get("isActive", True):
                    status = "archived"
                else:
                    status = "active"

                # Get place of performance
                pop = data.get("placeOfPerformance", {}) or {}

                # Calculate score
                score = calculate_likelihood_score({
                    "title": data.get("title"),
                    "set_aside_type": data.get("setAsideType"),
                    "notice_type": data.get("type"),
                })

                opp_data = {
                    "solicitation_number": data.get("solicitationNumber"),
                    "title": (data.get("title") or "")[:500],
                    "description": data.get("description"),
                    "posted_date": posted_date,
                    "response_deadline": response_deadline,
                    "notice_type": data.get("type"),
                    "naics_code": data.get("naicsCode"),
                    "psc_code": data.get("pscCode"),
                    "agency_name": data.get("agencyName"),
                    "department_name": data.get("agencyName"),
                    "sub_tier": data.get("subAgencyName"),
                    "office_name": data.get("officeName"),
                    "set_aside_type": data.get("setAsideType"),
                    "set_aside_description": data.get("setAsideDescription"),
                    "pop_city": pop.get("city"),
                    "pop_state": pop.get("stateCode"),
                    "pop_country": pop.get("countryCode") or "USA",
                    "ui_link": data.get("samGovLink"),
                    "status": status,
                    "likelihood_score": score,
                    "fetched_at": datetime.utcnow(),
                }

                if existing:
                    # === AMENDMENT TRACKING ===
                    # Detect deadline changes and track amendments
                    new_deadline = opp_data.get("response_deadline")
                    old_deadline = existing.response_deadline

                    if new_deadline and old_deadline and new_deadline != old_deadline:
                        # Deadline has changed - this is an amendment
                        existing.previous_response_deadline = old_deadline
                        existing.amendment_count = (existing.amendment_count or 0) + 1
                        existing.last_amendment_date = datetime.utcnow()

                        # Build amendment history entry
                        amendment_entry = {
                            "date": datetime.utcnow().isoformat(),
                            "field": "response_deadline",
                            "old_value": old_deadline.isoformat() if old_deadline else None,
                            "new_value": new_deadline.isoformat() if new_deadline else None,
                            "change_type": "deadline_extended" if new_deadline > old_deadline else "deadline_shortened",
                        }

                        # Append to amendment history
                        history = existing.amendment_history or []
                        history.append(amendment_entry)
                        existing.amendment_history = history

                        logger.info(
                            f"Amendment detected for {notice_id}: deadline changed from "
                            f"{old_deadline} to {new_deadline} (amendment #{existing.amendment_count})"
                        )
                    # === END AMENDMENT TRACKING ===

                    for key, value in opp_data.items():
                        if value is not None:
                            setattr(existing, key, value)
                    existing.updated_at = datetime.utcnow()
                    db_opp = existing
                else:
                    db_opp = Opportunity(
                        id=uuid.uuid4(),
                        notice_id=notice_id,
                        **opp_data
                    )
                    db.add(db_opp)
                    db.flush()

                # Save contacts
                for contact in data.get("contacts", []):
                    if contact.get("name") or contact.get("email"):
                        # Check if contact exists
                        existing_poc = db.query(PointOfContact).filter(
                            PointOfContact.opportunity_id == db_opp.id,
                            PointOfContact.email == contact.get("email")
                        ).first()

                        if not existing_poc:
                            poc = PointOfContact(
                                id=uuid.uuid4(),
                                opportunity_id=db_opp.id,
                                contact_type=contact.get("type", "primary"),
                                name=contact.get("name"),
                                title=contact.get("title"),
                                email=contact.get("email"),
                                phone=contact.get("phone"),
                            )
                            db.add(poc)

                # Save attachments
                for att in data.get("attachments", []):
                    download_url = att.get("downloadUrl")
                    if not download_url:
                        continue

                    existing_att = db.query(OpportunityAttachment).filter(
                        OpportunityAttachment.opportunity_id == db_opp.id,
                        OpportunityAttachment.url == download_url
                    ).first()

                    if not existing_att:
                        file_type = att.get("type", "").split("/")[-1] if att.get("type") else None
                        new_att = OpportunityAttachment(
                            id=uuid.uuid4(),
                            opportunity_id=db_opp.id,
                            name=att.get("filename"),
                            url=download_url,
                            resource_type="file",
                            file_type=file_type,
                            file_size=att.get("size"),
                            extraction_status="pending",
                        )
                        db.add(new_att)

                db.commit()
                self.scraped_ids.add(notice_id)
                return True

        except Exception as e:
            logger.error(f"Error saving opportunity: {e}")
            return False

    async def scrape_all_naics(
        self,
        naics_codes: Optional[List[str]] = None,
        days_back: int = 30,
        max_per_naics: int = 10000,
    ) -> Dict[str, Any]:
        """
        Scrape all configured NAICS codes.

        Args:
            naics_codes: List of NAICS codes (default: EXPANDED_NAICS_CODES)
            days_back: How many days back to scrape
            max_per_naics: Maximum opportunities per NAICS code

        Returns:
            Combined statistics
        """
        if naics_codes is None:
            naics_codes = EXPANDED_NAICS_CODES

        total_stats = {
            "naics_codes_scraped": 0,
            "total_opportunities": 0,
            "total_saved": 0,
            "total_attachments": 0,
            "total_errors": 0,
            "by_naics": {},
        }

        for naics_code in naics_codes:
            try:
                stats = await self.scrape_naics(
                    naics_code=naics_code,
                    days_back=days_back,
                    max_results=max_per_naics,
                )

                total_stats["naics_codes_scraped"] += 1
                total_stats["total_opportunities"] += stats["opportunities_scraped"]
                total_stats["total_saved"] += stats["opportunities_saved"]
                total_stats["total_attachments"] += stats["attachments_found"]
                total_stats["total_errors"] += stats["errors"]
                total_stats["by_naics"][naics_code] = stats

                # Brief pause between NAICS codes
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Error scraping NAICS {naics_code}: {e}")
                total_stats["total_errors"] += 1

        logger.info(
            f"Completed all NAICS codes: {total_stats['total_opportunities']} scraped, "
            f"{total_stats['total_saved']} saved"
        )

        return total_stats


# =============================================================================
# Synchronous Wrapper (for Celery tasks)
# =============================================================================

def sync_opportunities_by_naics(
    naics_code: str,
    days_back: int = 30,
    max_results: int = 1000,
) -> Dict[str, Any]:
    """
    Synchronous wrapper for scraping a single NAICS code.

    This is the main entry point for Celery tasks.
    """
    scraper = SAMScraper(
        concurrent_requests=5,
        request_delay=1.0,
    )

    return asyncio.run(scraper.scrape_naics(
        naics_code=naics_code,
        days_back=days_back,
        max_results=max_results,
    ))


def sync_all_naics_codes(
    days_back: int = 30,
    naics_codes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Synchronous wrapper for scraping all NAICS codes.

    This is the main entry point for full scrapes.
    """
    scraper = SAMScraper(
        concurrent_requests=5,
        request_delay=1.0,
    )

    return asyncio.run(scraper.scrape_all_naics(
        naics_codes=naics_codes,
        days_back=days_back,
    ))


# =============================================================================
# Legacy API (for backwards compatibility)
# =============================================================================

class SAMGovScraper:
    """
    Legacy synchronous scraper (for backwards compatibility).

    New code should use SAMScraper instead.
    """

    def __init__(self, delay_between_requests: float = 0.3):
        self.delay = delay_between_requests
        self.client = httpx.Client(timeout=60.0, headers=HEADERS, follow_redirects=True)
        self._last_request_time = 0

    def _rate_limit(self):
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
        """Search opportunities by NAICS code."""
        self._rate_limit()

        params = {
            "index": "opp",
            "page": page,
            "size": min(page_size, 100),
            "sort": "-modifiedDate",
            "mode": "search",
            "naics": naics_code,
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
        """Get full details for an opportunity."""
        self._rate_limit()

        url = DETAIL_API.format(notice_id=notice_id)

        try:
            response = self.client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting detail for {notice_id}: {e}")
            return None

    def get_attachments(self, notice_id: str) -> List[Dict[str, Any]]:
        """Get attachments for an opportunity."""
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
            attachment_lists = embedded.get("opportunityAttachmentList") or []

            for att_list in attachment_lists:
                if not isinstance(att_list, dict):
                    continue
                for att in att_list.get("attachments", []) or []:
                    if not isinstance(att, dict) or att.get("deletedFlag") == "1":
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

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# =============================================================================
# Utility Functions
# =============================================================================

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


def sync_opportunities_with_full_details(
    naics_code: str = "541511",
    max_results: int = 1000,
    biddable_only: bool = True,
) -> Dict[str, Any]:
    """
    Legacy sync function (uses new async scraper internally).

    For backwards compatibility with existing Celery tasks.
    """
    return sync_opportunities_by_naics(
        naics_code=naics_code,
        days_back=30,
        max_results=max_results,
    )


# =============================================================================
# External Scraper Import (for one-time bulk loads)
# =============================================================================

EXTERNAL_SCRAPER_PATH = "/home/peteylinux/Projects/sam-mass-scraper"
EXTERNAL_SCRAPER_DB = f"{EXTERNAL_SCRAPER_PATH}/bidking_sam.db"


def import_from_external_scraper(
    source_db: str = EXTERNAL_SCRAPER_DB,
    include_ai_summaries: bool = True,
) -> Dict[str, Any]:
    """
    Import opportunities from the external sam-mass-scraper database.

    This is the bridge for one-time bulk loads from the standalone scraper.
    """
    import sqlite3
    from pathlib import Path
    from app.database import SessionLocal
    from app.models import Opportunity, PointOfContact, OpportunityAttachment

    source_path = Path(source_db)
    if not source_path.exists():
        return {"error": f"Source database not found: {source_db}"}

    stats = {
        "source": str(source_db),
        "opportunities_found": 0,
        "opportunities_created": 0,
        "opportunities_updated": 0,
        "contacts_created": 0,
        "attachments_created": 0,
        "ai_summaries_imported": 0,
        "errors": 0,
    }

    conn = sqlite3.connect(source_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM opportunities ORDER BY posted_date DESC")
    opportunities = [dict(row) for row in cursor.fetchall()]
    stats["opportunities_found"] = len(opportunities)

    ai_by_opp = {}
    if include_ai_summaries:
        try:
            cursor.execute("""
                SELECT opportunity_id, ai_summary
                FROM ai_analysis
                WHERE status = 'completed' AND ai_summary IS NOT NULL
            """)
            for row in cursor.fetchall():
                ai_by_opp[row['opportunity_id']] = row['ai_summary']
        except sqlite3.OperationalError:
            pass

    conn.close()

    logger.info(f"Importing {len(opportunities)} opportunities from {source_db}")

    with SessionLocal() as db:
        for opp in opportunities:
            try:
                notice_id = opp['opportunity_id']

                existing = db.query(Opportunity).filter(
                    Opportunity.notice_id == notice_id
                ).first()

                posted_date = _parse_iso_date(opp.get('posted_date'))
                response_deadline = _parse_iso_date(opp.get('response_deadline'))

                if opp.get('is_canceled'):
                    status = 'canceled'
                elif not opp.get('is_active', True):
                    status = 'archived'
                else:
                    status = 'active'

                score = calculate_likelihood_score({
                    'title': opp.get('title'),
                    'set_aside_type': opp.get('set_aside_type'),
                    'notice_type': opp.get('type'),
                })

                ai_summary = ai_by_opp.get(notice_id)
                ai_value_low = None
                ai_value_high = None
                ai_value_basis = None

                if ai_summary:
                    try:
                        summary_data = json.loads(ai_summary) if isinstance(ai_summary, str) else ai_summary
                        est_value = summary_data.get('estimated_value', {})
                        ai_value_low = est_value.get('low')
                        ai_value_high = est_value.get('high')
                        ai_value_basis = est_value.get('basis')
                    except:
                        pass

                state_code = opp.get('place_state_code') or opp.get('place_state')
                if state_code and len(state_code) > 2:
                    state_code = state_code[:2]

                opp_data = {
                    "solicitation_number": opp.get('solicitation_number'),
                    "title": (opp.get('title') or '')[:500],
                    "description": opp.get('description'),
                    "posted_date": posted_date,
                    "response_deadline": response_deadline,
                    "notice_type": opp.get('type'),
                    "naics_code": opp.get('naics_code'),
                    "psc_code": opp.get('psc_code'),
                    "agency_name": opp.get('agency_name'),
                    "department_name": opp.get('agency_name'),
                    "sub_tier": opp.get('sub_agency_name'),
                    "office_name": opp.get('office_name'),
                    "set_aside_type": opp.get('set_aside_type'),
                    "set_aside_description": opp.get('set_aside_description'),
                    "pop_city": opp.get('place_city'),
                    "pop_state": state_code.upper() if state_code else None,
                    "pop_country": opp.get('place_country') or 'USA',
                    "ui_link": opp.get('sam_gov_link'),
                    "status": status,
                    "likelihood_score": score,
                    "ai_estimated_value_low": ai_value_low,
                    "ai_estimated_value_high": ai_value_high,
                    "ai_estimated_value_basis": ai_value_basis,
                    "fetched_at": datetime.utcnow(),
                }

                if existing:
                    for key, value in opp_data.items():
                        if value is not None:
                            setattr(existing, key, value)
                    existing.updated_at = datetime.utcnow()
                    db_opp = existing
                    stats["opportunities_updated"] += 1
                else:
                    db_opp = Opportunity(
                        id=uuid.uuid4(),
                        notice_id=notice_id,
                        **opp_data
                    )
                    db.add(db_opp)
                    db.flush()
                    stats["opportunities_created"] += 1

                # Import contacts
                contacts_json = opp.get('contacts_json')
                if contacts_json:
                    try:
                        contacts = json.loads(contacts_json) if isinstance(contacts_json, str) else contacts_json
                        for contact in contacts:
                            if contact.get('name') or contact.get('email'):
                                poc = PointOfContact(
                                    id=uuid.uuid4(),
                                    opportunity_id=db_opp.id,
                                    contact_type=contact.get('type', 'primary'),
                                    name=contact.get('name'),
                                    title=contact.get('title'),
                                    email=contact.get('email'),
                                    phone=contact.get('phone'),
                                )
                                db.add(poc)
                                stats["contacts_created"] += 1
                    except:
                        pass

                # Import attachments
                attachments_json = opp.get('attachments_json')
                if attachments_json:
                    try:
                        attachments = json.loads(attachments_json) if isinstance(attachments_json, str) else attachments_json
                        for att in attachments:
                            resource_id = att.get('resourceId')
                            if not resource_id:
                                continue

                            download_url = att.get('downloadUrl') or f"https://sam.gov/api/prod/opps/v3/opportunities/resources/files/{resource_id}/download"

                            existing_att = db.query(OpportunityAttachment).filter(
                                OpportunityAttachment.opportunity_id == db_opp.id,
                                OpportunityAttachment.url == download_url
                            ).first()

                            if not existing_att:
                                file_type = att.get('type', '').split('/')[-1] if att.get('type') else None
                                new_att = OpportunityAttachment(
                                    id=uuid.uuid4(),
                                    opportunity_id=db_opp.id,
                                    name=att.get('filename'),
                                    url=download_url,
                                    resource_type='file',
                                    file_type=file_type,
                                    file_size=att.get('size'),
                                    extraction_status='pending',
                                )

                                if ai_summary:
                                    try:
                                        summary_data = json.loads(ai_summary) if isinstance(ai_summary, str) else ai_summary
                                        new_att.ai_summary = summary_data
                                        new_att.ai_summary_status = 'summarized'
                                        new_att.ai_summarized_at = datetime.utcnow()
                                        stats["ai_summaries_imported"] += 1
                                    except:
                                        pass

                                db.add(new_att)
                                stats["attachments_created"] += 1
                    except:
                        pass

                total_processed = stats["opportunities_created"] + stats["opportunities_updated"]
                if total_processed % 100 == 0:
                    db.commit()
                    logger.info(f"Imported {total_processed} opportunities...")

            except Exception as e:
                stats["errors"] += 1
                if stats["errors"] <= 5:
                    logger.warning(f"Error importing {opp.get('opportunity_id')}: {e}")

        db.commit()

    logger.info(
        f"Import complete: {stats['opportunities_created']} created, "
        f"{stats['opportunities_updated']} updated, "
        f"{stats['ai_summaries_imported']} AI summaries"
    )

    return stats


# =============================================================================
# Configuration
# =============================================================================

class ScraperConfig:
    """Configuration for the SAM.gov scraper."""

    PROXY_FILE: str = str(Path.home() / "Downloads" / "Webshare residential proxies(1).txt")
    USE_PROXIES: bool = True

    CONCURRENT_REQUESTS: int = 5
    REQUEST_DELAY: float = 1.0
    MAX_RETRIES: int = 3
    TIMEOUT: float = 60.0

    PAGE_SIZE: int = 100
    DEFAULT_DAYS_BACK: int = 30

    NAICS_CODES: List[str] = EXPANDED_NAICS_CODES

    STALL_THRESHOLD_SECONDS: int = 90
    MAX_CONSECUTIVE_FAILURES: int = 10

    EXTERNAL_SCRAPER_PATH: str = EXTERNAL_SCRAPER_PATH
    EXTERNAL_SCRAPER_DB: str = EXTERNAL_SCRAPER_DB

    @classmethod
    def from_env(cls) -> "ScraperConfig":
        """Load configuration from environment variables."""
        import os
        config = cls()

        if os.environ.get("SAM_PROXY_FILE"):
            config.PROXY_FILE = os.environ["SAM_PROXY_FILE"]
        if os.environ.get("SAM_USE_PROXIES"):
            config.USE_PROXIES = os.environ["SAM_USE_PROXIES"].lower() == "true"
        if os.environ.get("SAM_CONCURRENT_REQUESTS"):
            config.CONCURRENT_REQUESTS = int(os.environ["SAM_CONCURRENT_REQUESTS"])
        if os.environ.get("SAM_REQUEST_DELAY"):
            config.REQUEST_DELAY = float(os.environ["SAM_REQUEST_DELAY"])
        if os.environ.get("SAM_NAICS_CODES"):
            config.NAICS_CODES = os.environ["SAM_NAICS_CODES"].split(",")

        return config


from pathlib import Path
