#!/usr/bin/env python3
"""
Upload Contract Awards to Fly.io

Reads contract awards from local SQLite database and uploads to
BidKing's production API via bulk import endpoint.

Usage:
    # Upload all unsynced awards
    python scripts/upload_awards_to_flyio.py

    # Dry run (show what would be uploaded)
    python scripts/upload_awards_to_flyio.py --dry-run

    # Force re-upload all awards (even already synced)
    python scripts/upload_awards_to_flyio.py --force

    # Custom source database
    python scripts/upload_awards_to_flyio.py --source ~/data/awards.db
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent.parent / 'logs' / 'upload_awards.log', mode='a'),
    ]
)
logger = logging.getLogger(__name__)

# Default paths
LOCAL_DB_PATH = Path(__file__).parent.parent / "data" / "usaspending_local.db"
FLYIO_API_URL = "https://bidking-api.fly.dev"

# Get sync secret from environment
SYNC_SECRET = os.environ.get("SYNC_SECRET", "")


def load_awards_from_db(
    db_path: str,
    only_unsynced: bool = True,
    limit: int = None,
) -> List[Dict[str, Any]]:
    """Load contract awards from local SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM contract_awards"
    params = []

    if only_unsynced:
        query += " WHERE synced_to_production = 0"

    query += " ORDER BY fetched_at DESC"

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query, params)
    awards = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return awards


def mark_awards_synced(db_path: str, award_ids: List[str]):
    """Mark awards as successfully synced to production."""
    if not award_ids:
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    placeholders = ",".join("?" for _ in award_ids)
    cursor.execute(
        f"UPDATE contract_awards SET synced_to_production = 1 WHERE award_id IN ({placeholders})",
        award_ids,
    )
    conn.commit()
    conn.close()


def upload_batch(
    awards: List[Dict[str, Any]],
    api_url: str = FLYIO_API_URL,
    dry_run: bool = False,
) -> Dict:
    """Upload a batch of awards to Fly.io."""

    # Transform to API format
    payload = {
        "awards": [
            {
                "award_id": a["award_id"],
                "piid": a.get("piid"),
                "award_type": a.get("award_type"),
                "total_obligation": a.get("total_obligation"),
                "base_and_all_options_value": a.get("base_and_all_options_value"),
                "award_date": a.get("award_date"),
                "period_of_performance_start": a.get("period_of_performance_start"),
                "period_of_performance_end": a.get("period_of_performance_end"),
                "naics_code": a.get("naics_code"),
                "naics_description": a.get("naics_description"),
                "psc_code": a.get("psc_code"),
                "awarding_agency_name": a.get("awarding_agency_name"),
                "awarding_sub_agency_name": a.get("awarding_sub_agency_name"),
                "recipient_uei": a.get("recipient_uei"),
                "recipient_name": a.get("recipient_name"),
                "pop_city": a.get("pop_city"),
                "pop_state": a.get("pop_state"),
                "pop_zip": a.get("pop_zip"),
                "set_aside_type": a.get("set_aside_type"),
            }
            for a in awards
        ]
    }

    if dry_run:
        return {
            "status": "dry_run",
            "awards_received": len(awards),
            "awards_created": len(awards),  # Estimate
            "awards_updated": 0,
        }

    try:
        response = requests.post(
            f"{api_url}/admin/bulk-import-awards",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-Sync-Secret": SYNC_SECRET,
            },
            timeout=120,
        )

        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"API returned HTTP {response.status_code}: {response.text[:200]}")
            return {
                "status": "error",
                "http_status": response.status_code,
                "error": response.text[:200],
            }

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(description="Upload contract awards to Fly.io")
    parser.add_argument(
        "--source",
        type=str,
        default=str(LOCAL_DB_PATH),
        help="Path to local SQLite database"
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default=FLYIO_API_URL,
        help="Fly.io API URL"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of awards per batch (default: 100)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-upload all awards (ignore synced status)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded without making changes"
    )
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        logger.error(f"Source database not found: {source_path}")
        sys.exit(1)

    if not SYNC_SECRET and not args.dry_run:
        logger.warning("SYNC_SECRET not set - upload may fail authentication")

    print("=" * 60)
    print("BidKing Contract Awards Upload to Fly.io")
    print("=" * 60)
    print(f"\nSource: {source_path}")
    print(f"Target: {args.api_url}")
    print(f"Batch size: {args.batch_size}")
    if args.force:
        print("Mode: FORCE (re-upload all awards)")
    else:
        print("Mode: Incremental (only unsynced awards)")
    if args.dry_run:
        print("\n*** DRY RUN - No changes will be made ***")
    print()

    # Load awards
    awards = load_awards_from_db(
        str(source_path),
        only_unsynced=not args.force,
    )

    if not awards:
        logger.info("No awards to upload")
        print("\nNo awards to upload.")
        return

    logger.info(f"Found {len(awards):,} awards to upload")

    # Upload in batches
    total_created = 0
    total_updated = 0
    total_errors = 0
    synced_ids = []

    batch_count = (len(awards) + args.batch_size - 1) // args.batch_size

    for batch_num in range(batch_count):
        batch_start = batch_num * args.batch_size
        batch_end = min(batch_start + args.batch_size, len(awards))
        batch = awards[batch_start:batch_end]

        logger.info(f"Uploading batch {batch_num + 1}/{batch_count} ({len(batch)} awards)...")

        result = upload_batch(batch, api_url=args.api_url, dry_run=args.dry_run)

        if result.get("status") == "success" or result.get("status") == "dry_run":
            total_created += result.get("awards_created", 0)
            total_updated += result.get("awards_updated", 0)
            synced_ids.extend([a["award_id"] for a in batch])
            logger.info(
                f"  Batch {batch_num + 1}: {result.get('awards_created', 0)} created, "
                f"{result.get('awards_updated', 0)} updated"
            )
        else:
            total_errors += len(batch)
            logger.warning(f"  Batch {batch_num + 1} failed: {result.get('error', 'Unknown error')}")

    # Mark successfully uploaded awards as synced
    if not args.dry_run and synced_ids:
        mark_awards_synced(str(source_path), synced_ids)
        logger.info(f"Marked {len(synced_ids):,} awards as synced")

    # Print summary
    print("\n" + "=" * 60)
    print("Upload Complete" + (" (DRY RUN)" if args.dry_run else ""))
    print("=" * 60)
    print(f"Total awards processed: {len(awards):,}")
    print(f"Awards created:         {total_created:,}")
    print(f"Awards updated:         {total_updated:,}")
    print(f"Errors:                 {total_errors:,}")
    if not args.dry_run:
        print(f"Awards marked synced:   {len(synced_ids):,}")


if __name__ == "__main__":
    main()
