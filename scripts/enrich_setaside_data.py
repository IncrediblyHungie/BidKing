#!/usr/bin/env python3
"""
Enrich Contract Awards with Set-Aside Data

The USAspending bulk search API doesn't return set-aside data.
This script fetches individual award details to get set_aside_type.

Usage:
    # Enrich all awards missing set-aside data
    python scripts/enrich_setaside_data.py

    # Limit to first 1000 awards
    python scripts/enrich_setaside_data.py --limit 1000

    # Dry run
    python scripts/enrich_setaside_data.py --dry-run
"""

import argparse
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import httpx

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent.parent / 'logs' / 'setaside_enrichment.log', mode='a'),
    ]
)
logger = logging.getLogger(__name__)

# USAspending API
USASPENDING_API_BASE = "https://api.usaspending.gov/api/v2"

# Local database path
LOCAL_DB_PATH = Path(__file__).parent.parent / "data" / "usaspending_local.db"


def fetch_award_details(award_id: str) -> Optional[Dict[str, Any]]:
    """Fetch individual award details to get set-aside type."""
    url = f"{USASPENDING_API_BASE}/awards/{award_id}/"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.debug(f"Award {award_id} not found (404)")
            return None
        logger.warning(f"HTTP error fetching {award_id}: {e.response.status_code}")
        return None
    except httpx.RequestError as e:
        logger.warning(f"Request error fetching {award_id}: {e}")
        return None


def extract_setaside_from_details(details: Dict[str, Any]) -> Optional[str]:
    """Extract set-aside type from award details response."""
    if not details:
        return None

    # The set-aside is in latest_transaction_contract_data
    contract_data = details.get("latest_transaction_contract_data", {})
    if not contract_data:
        return None

    # Try different field names
    setaside = (
        contract_data.get("type_set_aside_description") or
        contract_data.get("type_of_set_aside") or
        contract_data.get("type_of_set_aside_code") or
        contract_data.get("type_set_aside")
    )

    return setaside


def main():
    parser = argparse.ArgumentParser(description="Enrich awards with set-aside data")
    parser.add_argument(
        "--db",
        type=str,
        default=str(LOCAL_DB_PATH),
        help="Path to local SQLite database"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of awards to enrich"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Commit after this many updates"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fetched without making changes"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="Delay between API requests (seconds)"
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Count awards missing set-aside data
    cursor.execute("""
        SELECT COUNT(*) FROM contract_awards
        WHERE set_aside_type IS NULL OR set_aside_type = ''
    """)
    missing_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM contract_awards")
    total_count = cursor.fetchone()[0]

    print("=" * 60)
    print("BidKing Set-Aside Data Enrichment")
    print("=" * 60)
    print(f"\nTotal awards: {total_count:,}")
    print(f"Missing set-aside: {missing_count:,}")
    if args.limit:
        print(f"Limit: {args.limit:,}")
    if args.dry_run:
        print("\n*** DRY RUN - No changes will be made ***")
    print()

    if missing_count == 0:
        print("All awards already have set-aside data!")
        conn.close()
        return

    # Fetch awards missing set-aside data
    query = """
        SELECT award_id FROM contract_awards
        WHERE set_aside_type IS NULL OR set_aside_type = ''
    """
    if args.limit:
        query += f" LIMIT {args.limit}"

    cursor.execute(query)
    award_ids = [row[0] for row in cursor.fetchall()]

    logger.info(f"Enriching {len(award_ids):,} awards...")

    enriched = 0
    not_found = 0
    no_setaside = 0
    errors = 0

    for i, award_id in enumerate(award_ids):
        if args.dry_run:
            logger.info(f"[DRY RUN] Would fetch: {award_id}")
            continue

        try:
            # Fetch award details
            details = fetch_award_details(award_id)

            if not details:
                not_found += 1
                continue

            # Extract set-aside type
            setaside = extract_setaside_from_details(details)

            if setaside:
                cursor.execute("""
                    UPDATE contract_awards
                    SET set_aside_type = ?, synced_to_production = 0
                    WHERE award_id = ?
                """, (setaside, award_id))
                enriched += 1
                logger.info(f"[{i+1}/{len(award_ids)}] {award_id}: {setaside}")
            else:
                # Mark as "NO SET ASIDE USED" if contract data exists but no setaside
                cursor.execute("""
                    UPDATE contract_awards
                    SET set_aside_type = 'NO SET ASIDE USED', synced_to_production = 0
                    WHERE award_id = ?
                """, (award_id,))
                no_setaside += 1
                logger.debug(f"[{i+1}/{len(award_ids)}] {award_id}: No set-aside in response")

            # Commit periodically
            if (i + 1) % args.batch_size == 0:
                conn.commit()
                logger.info(f"  Committed batch (enriched: {enriched}, no-setaside: {no_setaside})")

            # Rate limiting
            time.sleep(args.delay)

        except Exception as e:
            errors += 1
            logger.error(f"Error processing {award_id}: {e}")
            continue

    # Final commit
    if not args.dry_run:
        conn.commit()

    # Print summary
    print("\n" + "=" * 60)
    print("Enrichment Complete" + (" (DRY RUN)" if args.dry_run else ""))
    print("=" * 60)
    print(f"Awards processed: {len(award_ids):,}")
    print(f"Enriched with set-aside: {enriched:,}")
    print(f"No set-aside (marked): {no_setaside:,}")
    print(f"Not found (404): {not_found:,}")
    print(f"Errors: {errors:,}")

    # Show set-aside distribution
    if not args.dry_run:
        cursor.execute("""
            SELECT set_aside_type, COUNT(*) as cnt
            FROM contract_awards
            WHERE set_aside_type IS NOT NULL AND set_aside_type != ''
            GROUP BY set_aside_type
            ORDER BY cnt DESC
            LIMIT 15
        """)
        rows = cursor.fetchall()

        if rows:
            print("\nSet-Aside Type Distribution:")
            for row in rows:
                print(f"  {row[0]}: {row[1]:,}")

    conn.close()


if __name__ == "__main__":
    main()
