#!/usr/bin/env python3
"""
Local USAspending Sync with Proxy Rotation

Fetches contract award data from USAspending.gov API using Webshare proxies.
Stores data locally for bulk upload to production.

Usage:
    # Initial backfill (2 years)
    python scripts/sync_usaspending_local.py --days 730

    # Daily sync (last 7 days)
    python scripts/sync_usaspending_local.py --days 7

    # Specific NAICS codes
    python scripts/sync_usaspending_local.py --days 30 --naics 541511,541512

    # Dry run (just show what would be fetched)
    python scripts/sync_usaspending_local.py --days 30 --dry-run
"""

import argparse
import json
import logging
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional, List, Dict, Any

import httpx


# Inline ProxyManager to avoid app dependency chain
class Proxy:
    """Represents a single proxy configuration"""
    def __init__(self, host: str, port: int, username: str, password: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.successes = 0
        self.failures = 0
        self.consecutive_failures = 0

    @property
    def url(self) -> str:
        return f"http://{self.username}:{self.password}@{self.host}:{self.port}"


class ProxyManager:
    """Manages proxy rotation for USAspending API requests."""

    def __init__(self, proxy_file: Optional[str] = None):
        if proxy_file:
            self.proxy_file = Path(proxy_file)
        else:
            self.proxy_file = Path.home() / "Downloads" / "Webshare residential proxies(1).txt"

        self._proxies: List[Proxy] = []
        self._current_index = 0
        self._load_proxies()

    def _load_proxies(self):
        if not self.proxy_file.exists():
            logger.warning(f"Proxy file not found: {self.proxy_file}")
            return

        import random
        proxies = []
        with open(self.proxy_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                try:
                    parts = line.split(':')
                    if len(parts) >= 4:
                        proxy = Proxy(
                            host=parts[0],
                            port=int(parts[1]),
                            username=parts[2],
                            password=parts[3],
                        )
                        proxies.append(proxy)
                except (ValueError, IndexError):
                    pass

        random.shuffle(proxies)
        self._proxies = proxies
        logger.info(f"Loaded {len(self._proxies):,} proxies")

    def get_proxy(self) -> Optional[Proxy]:
        if not self._proxies:
            return None
        proxy = self._proxies[self._current_index % len(self._proxies)]
        self._current_index += 1
        return proxy

    def mark_success(self, proxy: Proxy):
        proxy.successes += 1
        proxy.consecutive_failures = 0

    def mark_failure(self, proxy: Proxy):
        proxy.failures += 1
        proxy.consecutive_failures += 1

    def has_proxies(self) -> bool:
        return len(self._proxies) > 0

    @property
    def total_count(self) -> int:
        return len(self._proxies)

    def get_stats(self) -> Dict[str, Any]:
        total_successes = sum(p.successes for p in self._proxies)
        total_failures = sum(p.failures for p in self._proxies)
        return {
            "total_proxies": len(self._proxies),
            "active_proxies": len(self._proxies),
            "failed_proxies": 0,
            "total_requests": total_successes + total_failures,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "success_rate": total_successes / max(1, total_successes + total_failures) * 100,
        }


def get_proxy_manager() -> ProxyManager:
    """Get a proxy manager instance."""
    return ProxyManager()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent.parent / 'logs' / 'usaspending_sync.log', mode='a'),
    ]
)
logger = logging.getLogger(__name__)

# USAspending API
USASPENDING_API_BASE = "https://api.usaspending.gov/api/v2"

# Default NAICS codes for IT/software contracts
DEFAULT_NAICS_CODES = [
    "541511", "541512", "541519", "518210",
    "541690", "541712", "541330", "541990",
    "541611", "519190", "611430", "541910", "541618",  # Additional from user's config
]

# Local database path
LOCAL_DB_PATH = Path(__file__).parent.parent / "data" / "usaspending_local.db"


def init_local_db(db_path: Path) -> sqlite3.Connection:
    """Initialize local SQLite database for storing awards."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contract_awards (
            award_id TEXT PRIMARY KEY,
            piid TEXT,
            award_type TEXT,
            total_obligation REAL,
            base_and_all_options_value REAL,
            award_date TEXT,
            period_of_performance_start TEXT,
            period_of_performance_end TEXT,
            naics_code TEXT,
            naics_description TEXT,
            psc_code TEXT,
            awarding_agency_name TEXT,
            awarding_sub_agency_name TEXT,
            recipient_uei TEXT,
            recipient_name TEXT,
            pop_city TEXT,
            pop_state TEXT,
            pop_zip TEXT,
            set_aside_type TEXT,
            fetched_at TEXT,
            synced_to_production INTEGER DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naics ON contract_awards(naics_code)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_synced ON contract_awards(synced_to_production)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_set_aside ON contract_awards(set_aside_type)
    """)

    conn.commit()
    return conn


def fetch_awards_for_naics(
    naics_code: str,
    start_date: str,
    end_date: str,
    proxy_manager: ProxyManager,
    dry_run: bool = False,
) -> List[Dict[str, Any]]:
    """Fetch awards for a specific NAICS code with proxy rotation."""

    url = f"{USASPENDING_API_BASE}/search/spending_by_award/"

    payload = {
        "filters": {
            "time_period": [
                {"start_date": start_date, "end_date": end_date}
            ],
            "award_type_codes": ["A", "B", "C", "D"],  # Contracts only
            "naics_codes": [naics_code],
        },
        "fields": [
            "Award ID",
            "Recipient Name",
            "Recipient UEI",
            "Award Amount",
            "Total Obligation",
            "Start Date",
            "End Date",
            "Awarding Agency",
            "Awarding Sub Agency",
            "Award Type",
            "NAICS Code",
            "NAICS Description",
            "PSC Code",
            "Place of Performance City",
            "Place of Performance State",
            "Place of Performance Zip",
            "recipient_id",
            "generated_internal_id",
            "Type of Set Aside",
        ],
        "page": 1,
        "limit": 100,
        "sort": "Award Amount",
        "order": "desc",
    }

    all_awards = []
    page = 1
    max_pages = 100  # Safety limit
    max_retries = 3  # Max retries per page

    while page <= max_pages:
        payload["page"] = page

        # Get a proxy for this request (if available and not disabled)
        use_proxy = proxy_manager.has_proxies() if proxy_manager else False
        proxy = proxy_manager.get_proxy() if use_proxy else None
        proxy_url = proxy.url if proxy else None

        if dry_run:
            logger.info(f"  [DRY RUN] Would fetch page {page} for NAICS {naics_code}")
            if page == 1:
                # Just show that we'd make a request
                return [{"dry_run": True, "naics": naics_code}]
            break

        retries = 0
        success = False
        last_page = False

        while retries < max_retries and not success:
            try:
                proxy_info = f" via {proxy.host}:{proxy.port}" if proxy else " (direct)"
                logger.info(f"  Fetching page {page}{proxy_info}...")

                with httpx.Client(timeout=60.0, proxy=proxy_url) as client:
                    response = client.post(url, json=payload)

                    if proxy:
                        if response.status_code == 200:
                            proxy_manager.mark_success(proxy)
                        else:
                            proxy_manager.mark_failure(proxy)

                    response.raise_for_status()
                    data = response.json()

                results = data.get("results", [])
                if not results:
                    success = True  # No more results
                    last_page = True
                    break

                all_awards.extend(results)
                logger.info(f"  Page {page}: {len(results)} awards (total: {len(all_awards)})")
                success = True

                # Check for more pages
                if len(results) < payload["limit"]:
                    last_page = True  # This was the last page

            except httpx.HTTPStatusError as e:
                retries += 1
                logger.warning(f"  HTTP error on page {page}: {e.response.status_code} (retry {retries}/{max_retries})")
                if proxy:
                    proxy_manager.mark_failure(proxy)
                    proxy = proxy_manager.get_proxy()
                    proxy_url = proxy.url if proxy else None
                time.sleep(1)

            except httpx.RequestError as e:
                retries += 1
                logger.warning(f"  Request error on page {page}: {e} (retry {retries}/{max_retries})")
                if proxy:
                    proxy_manager.mark_failure(proxy)
                    proxy = proxy_manager.get_proxy()
                    proxy_url = proxy.url if proxy else None
                time.sleep(1)

        if not success and retries >= max_retries:
            logger.error(f"  Failed to fetch page {page} after {max_retries} retries, moving to next NAICS")
            break

        if last_page:
            break

        page += 1
        time.sleep(0.5)  # Small delay between pages

    return all_awards


def parse_date(date_str: Optional[str]) -> Optional[str]:
    """Parse date string to YYYY-MM-DD format."""
    if not date_str:
        return None
    try:
        return date_str[:10]
    except:
        return None


def save_awards_to_db(conn: sqlite3.Connection, awards: List[Dict[str, Any]], naics_code: str):
    """Save fetched awards to local database."""
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()

    inserted = 0
    updated = 0

    for award in awards:
        award_id = award.get("generated_internal_id") or award.get("Award ID")
        if not award_id:
            continue

        # Check if exists
        cursor.execute("SELECT award_id FROM contract_awards WHERE award_id = ?", (award_id,))
        exists = cursor.fetchone()

        record = (
            award_id,
            award.get("Award ID"),  # piid
            award.get("Award Type"),
            float(award.get("Total Obligation") or 0),
            float(award.get("Award Amount") or 0),
            parse_date(award.get("Start Date")),
            parse_date(award.get("Start Date")),
            parse_date(award.get("End Date")),
            naics_code,
            award.get("NAICS Description"),
            award.get("PSC Code"),
            award.get("Awarding Agency"),
            award.get("Awarding Sub Agency"),
            award.get("Recipient UEI"),
            award.get("Recipient Name"),
            award.get("Place of Performance City"),
            award.get("Place of Performance State"),
            award.get("Place of Performance Zip"),
            award.get("Type of Set Aside"),
            now,
            0,  # synced_to_production = false
        )

        if exists:
            # Update existing - mark as not synced since we have new data
            cursor.execute("""
                UPDATE contract_awards SET
                    piid = ?, award_type = ?, total_obligation = ?,
                    base_and_all_options_value = ?, award_date = ?,
                    period_of_performance_start = ?, period_of_performance_end = ?,
                    naics_code = ?, naics_description = ?, psc_code = ?,
                    awarding_agency_name = ?, awarding_sub_agency_name = ?,
                    recipient_uei = ?, recipient_name = ?,
                    pop_city = ?, pop_state = ?, pop_zip = ?,
                    set_aside_type = ?, fetched_at = ?, synced_to_production = 0
                WHERE award_id = ?
            """, record[1:] + (award_id,))
            updated += 1
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO contract_awards (
                    award_id, piid, award_type, total_obligation,
                    base_and_all_options_value, award_date,
                    period_of_performance_start, period_of_performance_end,
                    naics_code, naics_description, psc_code,
                    awarding_agency_name, awarding_sub_agency_name,
                    recipient_uei, recipient_name,
                    pop_city, pop_state, pop_zip,
                    set_aside_type, fetched_at, synced_to_production
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, record)
            inserted += 1

    conn.commit()
    return inserted, updated


def main():
    parser = argparse.ArgumentParser(description="Sync USAspending data locally with proxy rotation")
    parser.add_argument(
        "--days",
        type=int,
        default=730,
        help="Number of days to look back (default: 730 for 2-year backfill)"
    )
    parser.add_argument(
        "--naics",
        type=str,
        default=None,
        help="Comma-separated NAICS codes (default: IT/software codes)"
    )
    parser.add_argument(
        "--db",
        type=str,
        default=str(LOCAL_DB_PATH),
        help="Path to local SQLite database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fetched without actually fetching"
    )
    parser.add_argument(
        "--no-proxy",
        action="store_true",
        help="Disable proxy usage (direct connections to USAspending API)"
    )
    args = parser.parse_args()

    # Parse NAICS codes
    if args.naics:
        naics_codes = [n.strip() for n in args.naics.split(",")]
    else:
        naics_codes = DEFAULT_NAICS_CODES

    # Calculate date range
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=args.days)).strftime("%Y-%m-%d")

    print("=" * 60)
    print("BidKing Local USAspending Sync")
    print("=" * 60)
    print(f"\nDate Range: {start_date} to {end_date} ({args.days} days)")
    print(f"NAICS Codes: {', '.join(naics_codes)}")
    print(f"Database: {args.db}")
    if args.dry_run:
        print("\n*** DRY RUN - No data will be saved ***")
    if args.no_proxy:
        print("*** DIRECT CONNECTIONS (no proxy) ***")
    print()

    # Initialize proxy manager (or None if disabled)
    if args.no_proxy:
        proxy_manager = None
        logger.info("Proxy disabled - using direct connections")
    else:
        proxy_manager = get_proxy_manager()
        if proxy_manager.has_proxies():
            logger.info(f"Loaded {proxy_manager.total_count:,} proxies")
        else:
            logger.warning("No proxies available - using direct connections")

    # Initialize local database
    db_path = Path(args.db)
    if not args.dry_run:
        conn = init_local_db(db_path)
        logger.info(f"Initialized local database: {db_path}")
    else:
        conn = None

    # Sync each NAICS code
    total_fetched = 0
    total_inserted = 0
    total_updated = 0

    for naics_code in naics_codes:
        logger.info(f"\nSyncing NAICS {naics_code}...")

        try:
            awards = fetch_awards_for_naics(
                naics_code,
                start_date,
                end_date,
                proxy_manager,
                dry_run=args.dry_run,
            )

            total_fetched += len(awards)

            if not args.dry_run and conn and awards:
                inserted, updated = save_awards_to_db(conn, awards, naics_code)
                total_inserted += inserted
                total_updated += updated
                logger.info(f"  Saved: {inserted} new, {updated} updated")

        except Exception as e:
            logger.error(f"  Error syncing NAICS {naics_code}: {e}")
            continue

    # Print summary
    print("\n" + "=" * 60)
    print("Sync Complete" + (" (DRY RUN)" if args.dry_run else ""))
    print("=" * 60)
    print(f"Total awards fetched: {total_fetched:,}")
    if not args.dry_run:
        print(f"New awards inserted:  {total_inserted:,}")
        print(f"Existing updated:     {total_updated:,}")

    # Print proxy stats
    if proxy_manager.has_proxies():
        stats = proxy_manager.get_stats()
        print(f"\nProxy Stats:")
        print(f"  Active: {stats['active_proxies']:,} / {stats['total_proxies']:,}")
        print(f"  Success rate: {stats['success_rate']:.1f}%")

    if conn:
        # Show set-aside type distribution
        cursor = conn.cursor()
        cursor.execute("""
            SELECT set_aside_type, COUNT(*) as cnt
            FROM contract_awards
            WHERE set_aside_type IS NOT NULL AND set_aside_type != ''
            GROUP BY set_aside_type
            ORDER BY cnt DESC
            LIMIT 10
        """)
        rows = cursor.fetchall()

        if rows:
            print("\nSet-Aside Type Distribution:")
            for row in rows:
                print(f"  {row[0] or 'NULL'}: {row[1]:,}")

        conn.close()


if __name__ == "__main__":
    main()
