#!/usr/bin/env python3
"""
Daily CSV Import Pipeline for SAM.gov Opportunities

Downloads the daily ContractOpportunitiesFullCSV from SAM.gov (or uses a provided file)
and imports new/updated opportunities into the local database.

Filtering rules:
- Active = "Yes" (SAM.gov CSV only includes active, but we check anyway)
- ResponseDeadLine > today (skip expired opportunities)
- Skip if already exists with same or newer PostedDate

Usage:
    # Import from a specific CSV file
    python scripts/daily_csv_import.py /path/to/ContractOpportunitiesFullCSV.csv

    # Dry run (show what would be imported)
    python scripts/daily_csv_import.py /path/to/file.csv --dry-run

    # Import and queue for AI analysis
    python scripts/daily_csv_import.py /path/to/file.csv --queue-ai
"""

import argparse
import csv
import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent.parent / 'logs' / 'csv_import.log', mode='a'),
    ]
)
logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent.parent / 'bidking_sam.db'


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse various date formats from SAM.gov CSV."""
    if not date_str:
        return None
    try:
        # Handle ISO format with timezone
        if 'T' in date_str:
            # Remove timezone for comparison
            clean = date_str.replace('Z', '+00:00')
            dt = datetime.fromisoformat(clean)
            return dt.replace(tzinfo=None)
        else:
            # Handle "YYYY-MM-DD HH:MM:SS" format
            return datetime.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return None


def is_future_deadline(deadline_str: str) -> bool:
    """Check if deadline is in the future."""
    deadline = parse_date(deadline_str)
    if not deadline:
        # If no deadline, include it (might be ongoing)
        return True
    return deadline > datetime.now()


def build_contacts_json(row: Dict[str, str]) -> str:
    """Build contacts JSON from CSV row."""
    contacts = []

    # Primary contact
    if row.get('PrimaryContactFullname') or row.get('PrimaryContactEmail'):
        contacts.append({
            'type': 'primary',
            'title': row.get('PrimaryContactTitle', ''),
            'name': row.get('PrimaryContactFullname', ''),
            'email': row.get('PrimaryContactEmail', ''),
            'phone': row.get('PrimaryContactPhone', ''),
            'fax': row.get('PrimaryContactFax', ''),
        })

    # Secondary contact
    if row.get('SecondaryContactFullname') or row.get('SecondaryContactEmail'):
        contacts.append({
            'type': 'secondary',
            'title': row.get('SecondaryContactTitle', ''),
            'name': row.get('SecondaryContactFullname', ''),
            'email': row.get('SecondaryContactEmail', ''),
            'phone': row.get('SecondaryContactPhone', ''),
            'fax': row.get('SecondaryContactFax', ''),
        })

    return json.dumps(contacts) if contacts else None


def map_csv_to_opportunity(row: Dict[str, str]) -> Dict[str, Any]:
    """Map CSV row to database opportunity record."""
    return {
        'opportunity_id': row.get('NoticeId', ''),
        'solicitation_number': row.get('Sol#', ''),
        'title': row.get('Title', ''),
        'description': row.get('Description', ''),
        'type': row.get('Type', ''),
        'type_code': row.get('BaseType', ''),
        'posted_date': row.get('PostedDate', ''),
        'response_deadline': row.get('ResponseDeadLine', ''),
        'is_active': 1,
        'is_canceled': 0,
        'agency_name': row.get('Department/Ind.Agency', ''),
        'sub_agency_name': row.get('Sub-Tier', ''),
        'office_name': row.get('Office', ''),
        'naics_code': row.get('NaicsCode', ''),
        'psc_code': row.get('ClassificationCode', ''),
        'set_aside_type': row.get('SetASideCode', ''),
        'set_aside_description': row.get('SetASide', ''),
        'place_city': row.get('PopCity', ''),
        'place_state': row.get('PopState', ''),
        'place_country': row.get('PopCountry', ''),
        'sam_gov_link': row.get('Link', ''),
        'award_amount': float(row['Award$']) if row.get('Award$') else None,
        'award_awardee': row.get('Awardee', ''),
        'contacts_json': build_contacts_json(row),
        'raw_data_json': json.dumps(row),
        'scraped_at': datetime.now().isoformat(),
    }


def init_queue_table(conn: sqlite3.Connection):
    """Create the import queue table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS import_queue (
            opportunity_id TEXT PRIMARY KEY,
            needs_attachments INTEGER DEFAULT 1,
            needs_ai_analysis INTEGER DEFAULT 1,
            queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            attachments_completed_at TIMESTAMP,
            ai_completed_at TIMESTAMP
        )
    """)
    conn.commit()


def get_existing_opportunities(conn: sqlite3.Connection) -> Dict[str, str]:
    """Get existing opportunity IDs and their posted dates."""
    cursor = conn.execute("SELECT opportunity_id, posted_date FROM opportunities")
    return {row[0]: row[1] or '' for row in cursor.fetchall()}


def import_csv(
    csv_path: Path,
    dry_run: bool = False,
    queue_ai: bool = False,
) -> Dict[str, int]:
    """
    Import opportunities from SAM.gov CSV file.

    Returns stats dict with counts of processed records.
    """
    stats = {
        'total_rows': 0,
        'skipped_inactive': 0,
        'skipped_expired': 0,
        'skipped_duplicate': 0,
        'inserted': 0,
        'updated': 0,
        'queued_for_ai': 0,
        'errors': 0,
    }

    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return stats

    conn = sqlite3.connect(DB_PATH)
    init_queue_table(conn)
    existing = get_existing_opportunities(conn)

    logger.info(f"Existing opportunities in DB: {len(existing)}")
    logger.info(f"Reading CSV: {csv_path}")

    to_insert = []
    to_update = []
    to_queue = []

    # Read and filter CSV
    with open(csv_path, 'r', encoding='cp1252', errors='replace') as f:
        reader = csv.DictReader(f)

        for row in reader:
            stats['total_rows'] += 1

            opp_id = row.get('NoticeId', '')
            if not opp_id:
                stats['errors'] += 1
                continue

            # Filter: Active only
            if row.get('Active', '').lower() != 'yes':
                stats['skipped_inactive'] += 1
                continue

            # Filter: Future deadline only
            deadline = row.get('ResponseDeadLine', '')
            if not is_future_deadline(deadline):
                stats['skipped_expired'] += 1
                continue

            # Check for duplicates
            posted_date = row.get('PostedDate', '')
            if opp_id in existing:
                if posted_date <= existing[opp_id]:
                    stats['skipped_duplicate'] += 1
                    continue
                else:
                    # Newer version - update
                    to_update.append(map_csv_to_opportunity(row))
            else:
                # New opportunity
                to_insert.append(map_csv_to_opportunity(row))
                to_queue.append(opp_id)

    logger.info(f"Parsed {stats['total_rows']} rows")
    logger.info(f"Skipped: {stats['skipped_inactive']} inactive, {stats['skipped_expired']} expired, {stats['skipped_duplicate']} duplicates")
    logger.info(f"To insert: {len(to_insert)}, To update: {len(to_update)}")

    if dry_run:
        logger.info("DRY RUN - no changes made")
        stats['inserted'] = len(to_insert)
        stats['updated'] = len(to_update)
        conn.close()
        return stats

    # Insert new opportunities
    if to_insert:
        columns = list(to_insert[0].keys())
        placeholders = ', '.join(['?' for _ in columns])
        column_names = ', '.join(columns)

        for opp in to_insert:
            try:
                values = [opp[col] for col in columns]
                conn.execute(
                    f"INSERT INTO opportunities ({column_names}) VALUES ({placeholders})",
                    values
                )
                stats['inserted'] += 1
            except sqlite3.Error as e:
                logger.error(f"Insert error for {opp['opportunity_id']}: {e}")
                stats['errors'] += 1

    # Update existing opportunities
    if to_update:
        for opp in to_update:
            try:
                opp_id = opp.pop('opportunity_id')
                set_clause = ', '.join([f"{k} = ?" for k in opp.keys()])
                values = list(opp.values()) + [opp_id]
                conn.execute(
                    f"UPDATE opportunities SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE opportunity_id = ?",
                    values
                )
                stats['updated'] += 1
            except sqlite3.Error as e:
                logger.error(f"Update error for {opp_id}: {e}")
                stats['errors'] += 1

    # Queue for AI analysis
    if queue_ai and to_queue:
        for opp_id in to_queue:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO import_queue (opportunity_id) VALUES (?)",
                    (opp_id,)
                )
                stats['queued_for_ai'] += 1
            except sqlite3.Error as e:
                logger.error(f"Queue error for {opp_id}: {e}")

    conn.commit()
    conn.close()

    logger.info(f"Import complete: {stats['inserted']} inserted, {stats['updated']} updated")
    if queue_ai:
        logger.info(f"Queued {stats['queued_for_ai']} opportunities for AI analysis")

    return stats


def mark_stale_inactive(csv_path: Path, dry_run: bool = False) -> int:
    """
    Mark opportunities that are no longer in the active CSV as inactive.

    Returns count of opportunities marked inactive.
    """
    # Get all active opportunity IDs from CSV
    csv_ids = set()
    with open(csv_path, 'r', encoding='cp1252', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('Active', '').lower() == 'yes':
                csv_ids.add(row.get('NoticeId', ''))

    # Find opportunities in DB that are not in CSV
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT opportunity_id FROM opportunities WHERE is_active = 1"
    )
    db_ids = {row[0] for row in cursor.fetchall()}

    stale_ids = db_ids - csv_ids

    if dry_run:
        logger.info(f"DRY RUN - Would mark {len(stale_ids)} opportunities as inactive")
        conn.close()
        return len(stale_ids)

    if stale_ids:
        placeholders = ', '.join(['?' for _ in stale_ids])
        conn.execute(
            f"UPDATE opportunities SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE opportunity_id IN ({placeholders})",
            list(stale_ids)
        )
        conn.commit()
        logger.info(f"Marked {len(stale_ids)} opportunities as inactive")

    conn.close()
    return len(stale_ids)


def main():
    parser = argparse.ArgumentParser(
        description="Import SAM.gov opportunities from CSV"
    )
    parser.add_argument(
        'csv_file',
        type=Path,
        help="Path to ContractOpportunitiesFullCSV.csv"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Show what would be imported without making changes"
    )
    parser.add_argument(
        '--queue-ai',
        action='store_true',
        help="Queue new opportunities for AI analysis"
    )
    parser.add_argument(
        '--mark-stale',
        action='store_true',
        help="Mark opportunities not in CSV as inactive"
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Daily CSV Import Pipeline")
    logger.info("=" * 60)

    # Import new/updated opportunities
    stats = import_csv(
        args.csv_file,
        dry_run=args.dry_run,
        queue_ai=args.queue_ai,
    )

    # Optionally mark stale opportunities
    if args.mark_stale:
        stale_count = mark_stale_inactive(args.csv_file, dry_run=args.dry_run)
        stats['marked_inactive'] = stale_count

    # Print summary
    print("\n" + "=" * 40)
    print("IMPORT SUMMARY")
    print("=" * 40)
    print(f"Total CSV rows:      {stats['total_rows']:,}")
    print(f"Skipped (inactive):  {stats['skipped_inactive']:,}")
    print(f"Skipped (expired):   {stats['skipped_expired']:,}")
    print(f"Skipped (duplicate): {stats['skipped_duplicate']:,}")
    print(f"Inserted:            {stats['inserted']:,}")
    print(f"Updated:             {stats['updated']:,}")
    if args.queue_ai:
        print(f"Queued for AI:       {stats['queued_for_ai']:,}")
    if args.mark_stale:
        print(f"Marked inactive:     {stats.get('marked_inactive', 0):,}")
    print(f"Errors:              {stats['errors']:,}")
    print("=" * 40)

    return 0 if stats['errors'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
