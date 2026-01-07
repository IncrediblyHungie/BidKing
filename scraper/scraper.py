"""
SAM.gov Mass Scraper with Residential Proxy Rotation

Scrapes ALL federal contract opportunities from SAM.gov using:
- 215K+ residential proxy rotation
- Concurrent async requests
- SQLite storage for millions of records
- Resume capability for interrupted scrapes
- Rate limiting to avoid detection
- STALL DETECTION with auto-recovery

NO API KEY REQUIRED - Uses SAM.gov internal API endpoints.
"""

import asyncio
import logging
import random
import uuid
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Set
from pathlib import Path
from collections import deque

import httpx

from proxy_manager import ProxyManager, create_proxy_manager
from database import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scraper.log'),
    ]
)
logger = logging.getLogger(__name__)


# SAM.gov internal API endpoints (no API key required)
SAM_SEARCH_URL = "https://sam.gov/api/prod/sgs/v1/search/"
SAM_DETAILS_URL = "https://sam.gov/api/prod/opps/v2/opportunities"
SAM_RESOURCES_URL = "https://sam.gov/api/prod/opps/v3/opportunities"

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def get_headers() -> Dict[str, str]:
    """Get request headers with random user agent"""
    return {
        "Accept": "application/hal+json, application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://sam.gov/search/",
        "Origin": "https://sam.gov",
        "User-Agent": random.choice(USER_AGENTS),
    }


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
        """Record that progress was made. count=0 resets timer without incrementing."""
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
    - SQLite storage with resume capability
    - Rate limiting and backoff on errors
    - STALL DETECTION with automatic recovery
    - Progress checkpointing
    """

    def __init__(
        self,
        proxy_file: str = "/home/peteylinux/Projects/sam-mass-scraper/brightdata_proxy.txt",
        db_path: str = "sam_opportunities.db",
        concurrent_requests: int = 10,
        page_size: int = 100,  # Max allowed by SAM.gov API
        request_delay: float = 0.5,  # Seconds between requests per worker
        max_retries: int = 3,
        timeout: float = 60.0,
        stall_threshold: int = 90,  # Seconds without progress before recovery
    ):
        self.proxy_manager = create_proxy_manager(proxy_file)
        self.db = Database(db_path)
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
        self.blocked_proxy_count = 0

        # Semaphore for rate limiting
        self._semaphore = asyncio.Semaphore(concurrent_requests)

        # Pending saves buffer (save in batches)
        self._pending_saves: List[Dict] = []
        self._save_batch_size = 10

    def _flush_pending_saves(self):
        """Save all pending opportunities to database."""
        if not self._pending_saves:
            return

        saved_count = 0
        for data in self._pending_saves:
            if self.db.save_opportunity(data):
                self.scraped_ids.add(data["opportunityId"])
                saved_count += 1

        if saved_count > 0:
            self.stall_detector.record_progress(saved_count)
            self.total_scraped += saved_count
            logger.info(f"💾 Saved batch of {saved_count} opportunities (Total: {self.total_scraped:,})")

        self._pending_saves = []

    async def _make_request(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[Dict] = None,
        retry_count: int = 0,
    ) -> Optional[Dict]:
        """
        Make an HTTP request with proxy rotation, retry logic, and blocking detection.
        """
        proxy = self.proxy_manager.get_proxy()
        if not proxy:
            logger.warning("⚠️ No proxies available, trying direct connection...")
            # Fallback to direct connection without proxy
            try:
                async with self._semaphore:
                    response = await client.get(url, params=params, headers=get_headers())
                    response.raise_for_status()
                    await asyncio.sleep(self.request_delay)
                    return response.json()
            except Exception as e:
                logger.error(f"❌ Direct request failed: {e}")
                return None

        try:
            async with self._semaphore:
                # Create a new client with this proxy for this request
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=True,
                    proxy=proxy.url,
                ) as proxy_client:
                    response = await proxy_client.get(
                        url,
                        params=params,
                        headers=get_headers(),
                    )

                    # Reset consecutive error counters on success
                    self.consecutive_403s = 0
                    self.consecutive_timeouts = 0

                    response.raise_for_status()
                    self.proxy_manager.mark_success(proxy)
                    await asyncio.sleep(self.request_delay + random.uniform(0, 0.5))

                    return response.json()

        except httpx.HTTPStatusError as e:
            self.proxy_manager.mark_failure(proxy)
            status_code = e.response.status_code

            if status_code == 403:
                self.consecutive_403s += 1
                self.blocked_proxy_count += 1
                logger.warning(f"🚫 403 Forbidden (proxy may be blocked) - Count: {self.consecutive_403s}")

                # If we get many 403s, something is wrong
                if self.consecutive_403s >= 5:
                    logger.warning("⚠️ Multiple 403s detected - backing off 30s and rotating proxies aggressively")
                    await asyncio.sleep(30)
                    self.consecutive_403s = 0

            elif status_code == 429:  # Rate limited
                logger.warning(f"⏳ Rate limited (429), backing off... (retry {retry_count + 1})")
                await asyncio.sleep(10 + random.uniform(0, 10))

            elif status_code >= 500:
                logger.warning(f"🔥 Server error {status_code}, retrying...")
                await asyncio.sleep(2)
            else:
                logger.warning(f"HTTP {status_code} error")

            if retry_count < self.max_retries:
                return await self._make_request(client, url, params, retry_count + 1)

            self.stall_detector.record_failure()
            logger.error(f"❌ Request failed after {retry_count + 1} attempts: HTTP {status_code}")
            return None

        except httpx.TimeoutException as e:
            self.proxy_manager.mark_failure(proxy)
            self.consecutive_timeouts += 1

            if self.consecutive_timeouts >= 5:
                logger.warning(f"⚠️ Multiple timeouts ({self.consecutive_timeouts}) - may indicate blocking")
                await asyncio.sleep(10)
                self.consecutive_timeouts = 0

            if retry_count < self.max_retries:
                logger.debug(f"⏱️ Timeout, retrying with different proxy...")
                await asyncio.sleep(2)
                return await self._make_request(client, url, params, retry_count + 1)

            self.stall_detector.record_failure()
            logger.error(f"❌ Request timed out after {retry_count + 1} attempts")
            return None

        except httpx.RequestError as e:
            self.proxy_manager.mark_failure(proxy)

            if retry_count < self.max_retries:
                logger.debug(f"🔄 Request error, retrying: {type(e).__name__}")
                await asyncio.sleep(1 + random.uniform(0, 2))
                return await self._make_request(client, url, params, retry_count + 1)

            self.stall_detector.record_failure()
            logger.error(f"❌ Request failed: {e}")
            return None

    async def search_page(
        self,
        client: httpx.AsyncClient,
        page: int,
        posted_from: Optional[str] = None,
        posted_to: Optional[str] = None,
        include_inactive: bool = True,
    ) -> tuple[List[Dict], int]:
        """
        Search for opportunities on a specific page.

        Returns:
            Tuple of (results list, total count)
        """
        params = {
            "random": int(datetime.now(timezone.utc).timestamp()),
            "index": "opp",
            "page": page,
            "mode": "search",
            "sort": "-modifiedDate",
            "size": self.page_size,
        }

        # Include all opportunities (active and inactive)
        if not include_inactive:
            params["is_active"] = "true"

        if posted_from:
            params["postedFrom"] = posted_from
        if posted_to:
            params["postedTo"] = posted_to

        data = await self._make_request(client, SAM_SEARCH_URL, params)
        if not data:
            return [], 0

        results = data.get("_embedded", {}).get("results", [])
        total = data.get("page", {}).get("totalElements", 0)

        logger.info(f"📄 Page {page + 1}: Found {len(results)} opportunities (total: {total:,})")
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

            # Get attachments metadata (not downloading files)
            opportunity_data["attachments"] = await self.get_attachments(client, opp_id)

            return opportunity_data

        except Exception as e:
            logger.error(f"❌ Error processing {opp_id}: {e}")
            self.total_errors += 1
            self.stall_detector.record_failure()
            return None

    async def scrape_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        include_inactive: bool = True,
    ) -> int:
        """
        Scrape all opportunities within a date range with stall detection and recovery.

        Returns total opportunities scraped.
        """
        posted_from = start_date.strftime("%m/%d/%Y")
        posted_to = end_date.strftime("%m/%d/%Y")

        logger.info(f"🚀 Starting scrape: {posted_from} to {posted_to}")
        logger.info(f"🔄 Using {self.proxy_manager.active_count:,} proxies")

        # Load already scraped IDs for resume capability
        self.scraped_ids = self.db.get_scraped_ids()
        logger.info(f"✅ Already scraped: {len(self.scraped_ids):,} opportunities (will skip)")

        # Create session
        self.db.create_session(self.session_id, {
            "posted_from": posted_from,
            "posted_to": posted_to,
            "include_inactive": include_inactive,
        })

        # First, get total count
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            _, total_opportunities = await self.search_page(
                client, 0, posted_from, posted_to, include_inactive
            )

        if total_opportunities == 0:
            logger.warning("⚠️ No opportunities found!")
            return 0

        logger.info(f"📊 Target: {total_opportunities:,} total opportunities")
        total_pages = (total_opportunities + self.page_size - 1) // self.page_size
        logger.info(f"📑 Total pages to scrape: {total_pages:,}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            page = 0
            stall_recovery_attempts = 0
            max_stall_recoveries = 5

            while page < total_pages:
                # Check for stall condition
                if self.stall_detector.is_stalled():
                    stall_recovery_attempts += 1
                    logger.warning(f"⚠️ STALL DETECTED! No progress for {self.stall_detector.stall_threshold}s")
                    logger.warning(f"🔧 Recovery attempt {stall_recovery_attempts}/{max_stall_recoveries}")

                    if stall_recovery_attempts >= max_stall_recoveries:
                        logger.error("❌ Max stall recovery attempts reached. Aborting.")
                        break

                    # Recovery: flush saves, back off, and continue
                    self._flush_pending_saves()
                    backoff = 30 * stall_recovery_attempts
                    logger.info(f"⏳ Backing off for {backoff} seconds...")
                    await asyncio.sleep(backoff)

                    # Reset stall detector
                    self.stall_detector.last_progress_time = time.time()
                    continue

                # Check for too many consecutive failures
                if self.stall_detector.should_abort():
                    logger.error(f"❌ Too many consecutive failures ({self.stall_detector.consecutive_failures}). Aborting.")
                    break

                # Get page of results
                results, _ = await self.search_page(
                    client, page, posted_from, posted_to, include_inactive
                )

                if not results:
                    if page == 0:
                        logger.warning("⚠️ No results found on first page!")
                        break
                    # Empty page might mean we're at the end
                    logger.info(f"📭 Empty page {page + 1}, may have reached end")
                    # Try a couple more pages before giving up
                    empty_pages = 0
                    while empty_pages < 3 and page < total_pages:
                        page += 1
                        results, _ = await self.search_page(
                            client, page, posted_from, posted_to, include_inactive
                        )
                        if results:
                            break
                        empty_pages += 1
                    if not results:
                        break

                # Count how many are already scraped vs new
                new_ids = []
                skipped_ids = []
                for opp in results:
                    opp_id = opp.get("_id")
                    if opp_id:
                        if opp_id in self.scraped_ids:
                            skipped_ids.append(opp_id)
                        else:
                            new_ids.append(opp_id)

                # If all items on this page are already scraped, quickly move to next
                if not new_ids and skipped_ids:
                    logger.info(f"⏭️ Page {page + 1}: All {len(skipped_ids)} opportunities already scraped, skipping...")
                    # Still count this as progress to prevent stall detection
                    self.stall_detector.record_progress(0)  # Record activity but no new items
                    page += 1
                    continue

                # Process new opportunities concurrently
                tasks = []
                for opp in results:
                    opp_id = opp.get("_id")
                    if opp_id in new_ids:
                        tasks.append(self.process_opportunity(client, opp))

                if tasks:
                    logger.info(f"🔄 Processing {len(tasks)} new opportunities on page {page + 1} (skipped {len(skipped_ids)} already done)")
                    processed = await asyncio.gather(*tasks, return_exceptions=True)

                    processed_count = 0
                    for data in processed:
                        if isinstance(data, Exception):
                            logger.error(f"❌ Task exception: {data}")
                            self.total_errors += 1
                            continue
                        if data:
                            self._pending_saves.append(data)
                            processed_count += 1

                            # Save in batches
                            if len(self._pending_saves) >= self._save_batch_size:
                                self._flush_pending_saves()

                    # Record progress for processed items (critical for stall detection)
                    if processed_count > 0:
                        self.stall_detector.record_progress(processed_count)
                        logger.debug(f"✅ Recorded {processed_count} items progress")

                    # If we only processed a few items (less than batch size), flush now
                    # This prevents data loss and stalling on sparse pages
                    if len(self._pending_saves) > 0 and len(self._pending_saves) < self._save_batch_size:
                        self._flush_pending_saves()

                # Update session progress
                self.db.update_session_progress(self.session_id, page, self.total_scraped)
                logger.debug(f"📄 Completed page {page + 1}, moving to next page...")

                # Log progress every 5 pages
                if (page + 1) % 5 == 0 or page == 0:
                    stats = self.proxy_manager.get_stats()
                    progress_pct = (self.total_scraped / total_opportunities * 100) if total_opportunities > 0 else 0
                    rate = self.stall_detector.get_rate()
                    eta_seconds = ((total_opportunities - self.total_scraped) / rate) if rate > 0 else 0
                    eta_minutes = eta_seconds / 60

                    logger.info(
                        f"📈 Progress: Page {page + 1}/{total_pages}, "
                        f"Scraped: {self.total_scraped:,}/{total_opportunities:,} ({progress_pct:.1f}%), "
                        f"Rate: {rate:.1f}/sec, "
                        f"ETA: {eta_minutes:.0f}min, "
                        f"Errors: {self.total_errors}, "
                        f"Proxy success: {stats['success_rate']:.1f}%"
                    )

                # Reset stall recovery on successful page
                stall_recovery_attempts = 0

                # Check if we've reached the end
                if len(results) < self.page_size:
                    logger.info(f"📭 Last page reached (got {len(results)} < {self.page_size})")
                    break

                page += 1

        # Flush any remaining saves
        self._flush_pending_saves()

        # Complete session
        self.db.complete_session(self.session_id, page + 1, self.total_scraped)

        logger.info(f"✅ Scrape complete! Total: {self.total_scraped:,} opportunities")
        return self.total_scraped

    async def scrape_all(
        self,
        years_back: int = 5,
        chunk_days: int = 30,
    ):
        """
        Scrape ALL opportunities by chunking date ranges.

        Args:
            years_back: How many years of data to scrape
            chunk_days: Size of each date chunk (to avoid API limits)
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=years_back * 365)

        logger.info(f"🌐 Full scrape: {start_date.date()} to {end_date.date()}")
        logger.info(f"📦 Chunking into {chunk_days}-day ranges")

        current_start = start_date
        total = 0

        while current_start < end_date:
            current_end = min(current_start + timedelta(days=chunk_days), end_date)

            try:
                scraped = await self.scrape_date_range(current_start, current_end)
                total += scraped
            except Exception as e:
                logger.error(f"❌ Error in chunk {current_start.date()} - {current_end.date()}: {e}")
                self.db.fail_session(self.session_id, str(e))

            current_start = current_end

            # Brief pause between chunks
            await asyncio.sleep(2)

        logger.info(f"🎉 Full scrape complete! Total: {total:,} opportunities")
        return total


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="SAM.gov Mass Scraper")
    parser.add_argument("--years", type=int, default=5, help="Years of data to scrape")
    parser.add_argument("--chunk-days", type=int, default=30, help="Days per chunk")
    parser.add_argument("--concurrent", type=int, default=10, help="Concurrent requests")
    parser.add_argument("--db", type=str, default="sam_opportunities.db", help="Database file")
    parser.add_argument("--proxy-file", type=str,
                       default="/home/peteylinux/Projects/sam-mass-scraper/brightdata_proxy.txt",
                       help="Proxy file path (default: Bright Data rotating proxy)")

    args = parser.parse_args()

    scraper = SAMScraper(
        proxy_file=args.proxy_file,
        db_path=args.db,
        concurrent_requests=args.concurrent,
    )

    try:
        await scraper.scrape_all(years_back=args.years, chunk_days=args.chunk_days)
    except KeyboardInterrupt:
        logger.info("⏹️ Scrape interrupted by user")
    finally:
        # Print final stats
        stats = scraper.db.get_stats()
        logger.info("\n=== Final Database Stats ===")
        logger.info(f"Total opportunities: {stats['total_opportunities']:,}")
        logger.info(f"Active opportunities: {stats['active_opportunities']:,}")
        logger.info(f"Total attachments: {stats['total_attachments']:,}")

        proxy_stats = scraper.proxy_manager.get_stats()
        logger.info("\n=== Proxy Stats ===")
        logger.info(f"Total requests: {proxy_stats['total_requests']:,}")
        logger.info(f"Success rate: {proxy_stats['success_rate']:.1f}%")
        logger.info(f"Active proxies: {proxy_stats['active_proxies']:,}")


if __name__ == "__main__":
    asyncio.run(main())
