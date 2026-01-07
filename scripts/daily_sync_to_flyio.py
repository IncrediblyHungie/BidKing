#!/usr/bin/env python3
"""
Daily Sync to Fly.io

This script runs on your local machine and syncs data from the local
sam-mass-scraper database to BidKing's production Fly.io PostgreSQL.

Benefits:
- Scraping runs locally with 215K residential proxies
- AI analysis runs locally with your GPU (free)
- Fly.io stays lightweight (just serves the API/frontend)
- No proxy costs or API rate limits on production

Usage:
    # One-time sync
    python scripts/daily_sync_to_flyio.py

    # Cron job for daily sync (e.g., 6 AM)
    0 6 * * * cd /home/peteylinux/Projects/BidKing && python scripts/daily_sync_to_flyio.py >> logs/daily_sync.log 2>&1

    # Sync with custom source database
    python scripts/daily_sync_to_flyio.py --source ~/Projects/sam-mass-scraper/bidking_sam.db

    # Dry run (show what would be synced)
    python scripts/daily_sync_to_flyio.py --dry-run
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent.parent / 'logs' / 'daily_sync.log', mode='a'),
    ]
)
logger = logging.getLogger(__name__)

# Default paths
DEFAULT_SOURCE_DB = Path.home() / "Projects" / "sam-mass-scraper" / "bidking_sam.db"
FLYIO_API_URL = "https://bidking-api.fly.dev"


def parse_date(date_str: str) -> Optional[str]:
    """Parse various date formats to YYYY-MM-DD"""
    if not date_str:
        return None
    try:
        if 'T' in str(date_str):
            return date_str[:10]
        return date_str[:10] if len(str(date_str)) >= 10 else None
    except:
        return None


def parse_datetime(dt_str: str) -> Optional[str]:
    """Parse to ISO datetime string"""
    if not dt_str:
        return None
    try:
        if 'T' in str(dt_str):
            # Handle ISO format
            dt_str = dt_str.replace('Z', '+00:00')
            if '+' in dt_str:
                dt_str = dt_str.split('+')[0]
            return dt_str
        return f"{dt_str[:10]}T00:00:00"
    except:
        return None


def get_state_code(state: str) -> Optional[str]:
    """Extract 2-letter state code"""
    if not state:
        return None
    if len(state) == 2:
        return state.upper()
    state_map = {
        'california': 'CA', 'virginia': 'VA', 'maryland': 'MD',
        'texas': 'TX', 'florida': 'FL', 'new york': 'NY',
        'district of columbia': 'DC', 'washington': 'WA',
    }
    return state_map.get(state.lower(), state[:2].upper() if state else None)


def calculate_likelihood_score(opp: dict) -> int:
    """Calculate likelihood score (0-100) that contract is under $100K"""
    score = 50  # Start neutral

    title = (opp.get('title') or '').lower()
    set_aside = (opp.get('set_aside_type') or '').lower()
    opp_type = (opp.get('type') or '').lower()

    # Positive indicators
    if any(x in set_aside for x in ['small', 'sba', '8(a)', 'hubzone', 'sdvosb', 'wosb']):
        score += 15
    if any(x in opp_type for x in ['sources sought', 'special notice', 'rfi']):
        score += 10
    if any(x in title for x in ['support', 'maintenance', 'subscription', 'license']):
        score += 10

    # Negative indicators
    if any(x in title for x in ['enterprise', 'system-wide', 'global', 'agency-wide']):
        score -= 15
    if 'idiq' in opp_type or 'idiq' in title:
        score -= 10

    return max(0, min(100, score))


def load_source_data(
    source_db: str,
    days_back: Optional[int] = None,
) -> tuple[List[dict], List[dict], List[dict]]:
    """
    Load opportunities, attachments, and AI analyses from source database.

    Args:
        source_db: Path to SQLite database
        days_back: Only sync opportunities modified in the last N days (None = all)
    """
    conn = sqlite3.connect(source_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Build query with optional date filter
    query = "SELECT * FROM opportunities"
    params = []

    if days_back:
        cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        query += " WHERE modified_date >= ? OR scraped_at >= ?"
        params = [cutoff_date, cutoff_date]

    query += " ORDER BY modified_date DESC"

    cursor.execute(query, params)
    opportunities = [dict(row) for row in cursor.fetchall()]

    # Load attachments with text content
    cursor.execute("""
        SELECT
            opportunity_id, resource_id, filename, mime_type,
            file_size, access_level, posted_date, download_url,
            text_extracted, extracted_text
        FROM attachments
        WHERE downloaded = 1 OR text_extracted = 1
    """)
    attachments = [dict(row) for row in cursor.fetchall()]

    # Load AI analyses
    ai_analyses = []
    try:
        cursor.execute("""
            SELECT
                opportunity_id, attachment_id, status,
                text_content, ai_summary, model_used, analyzed_at
            FROM ai_analysis
            WHERE status = 'completed' AND ai_summary IS NOT NULL
        """)
        ai_analyses = [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        pass  # Table may not exist

    conn.close()

    logger.info(f"Loaded from {source_db}:")
    logger.info(f"  - {len(opportunities):,} opportunities")
    logger.info(f"  - {len(attachments):,} attachments with content")
    logger.info(f"  - {len(ai_analyses):,} AI analyses")

    return opportunities, attachments, ai_analyses


def sync_to_flyio(
    opportunities: List[dict],
    attachments: List[dict],
    ai_analyses: List[dict],
    api_url: str = FLYIO_API_URL,
    dry_run: bool = False,
) -> dict:
    """
    Sync data to Fly.io production database via API.

    This uses a bulk import endpoint that upserts opportunities.
    """
    stats = {
        'opportunities_synced': 0,
        'attachments_synced': 0,
        'ai_summaries_synced': 0,
        'errors': [],
    }

    if dry_run:
        logger.info("=== DRY RUN - No changes will be made ===")
        stats['opportunities_synced'] = len(opportunities)
        stats['attachments_synced'] = len(attachments)
        stats['ai_summaries_synced'] = len(ai_analyses)
        return stats

    # Build lookup for AI analyses by opportunity_id
    ai_by_opp = {}
    for ai in ai_analyses:
        opp_id = ai['opportunity_id']
        if opp_id not in ai_by_opp:
            ai_by_opp[opp_id] = []
        ai_by_opp[opp_id].append(ai)

    # Build lookup for attachments by opportunity_id
    att_by_opp = {}
    for att in attachments:
        opp_id = att['opportunity_id']
        if opp_id not in att_by_opp:
            att_by_opp[opp_id] = []
        att_by_opp[opp_id].append(att)

    # Process in batches
    batch_size = 50
    total_batches = (len(opportunities) + batch_size - 1) // batch_size

    for batch_num in range(total_batches):
        batch_start = batch_num * batch_size
        batch_end = min(batch_start + batch_size, len(opportunities))
        batch = opportunities[batch_start:batch_end]

        payload = []
        for opp in batch:
            try:
                notice_id = opp['opportunity_id']

                # Determine status
                if opp.get('is_canceled'):
                    status = 'canceled'
                elif not opp.get('is_active', True):
                    status = 'archived'
                else:
                    status = 'active'

                # Get AI analysis for this opportunity
                ai_list = ai_by_opp.get(notice_id, [])
                ai_summary = None
                ai_value_low = None
                ai_value_high = None
                ai_value_basis = None

                if ai_list:
                    try:
                        ai_data = ai_list[0]
                        ai_summary = json.loads(ai_data['ai_summary']) if isinstance(ai_data['ai_summary'], str) else ai_data['ai_summary']
                        if ai_summary:
                            est_value = ai_summary.get('estimated_value', {})
                            ai_value_low = est_value.get('low')
                            ai_value_high = est_value.get('high')
                            ai_value_basis = est_value.get('basis')
                            stats['ai_summaries_synced'] += 1
                    except:
                        pass

                # Build record
                record = {
                    'notice_id': notice_id,
                    'solicitation_number': opp.get('solicitation_number'),
                    'title': opp.get('title', 'Untitled'),
                    'description': opp.get('description'),
                    'notice_type': opp.get('type'),
                    'posted_date': parse_date(opp.get('posted_date')),
                    'response_deadline': parse_datetime(opp.get('response_deadline')),
                    'department_name': opp.get('agency_name'),
                    'agency_name': opp.get('agency_name'),
                    'sub_tier': opp.get('sub_agency_name'),
                    'office_name': opp.get('office_name'),
                    'naics_code': opp.get('naics_code'),
                    'psc_code': opp.get('psc_code'),
                    'set_aside_type': opp.get('set_aside_type'),
                    'set_aside_description': opp.get('set_aside_description'),
                    'pop_city': opp.get('place_city'),
                    'pop_state': get_state_code(opp.get('place_state_code') or opp.get('place_state')),
                    'pop_country': opp.get('place_country') or 'USA',
                    'award_amount': opp.get('award_amount'),
                    'awardee_name': opp.get('award_awardee'),
                    'awardee_uei': opp.get('award_awardee_uei'),
                    'ui_link': opp.get('sam_gov_link'),
                    'status': status,
                    'likelihood_score': calculate_likelihood_score(opp),
                    'ai_estimated_value_low': ai_value_low,
                    'ai_estimated_value_high': ai_value_high,
                    'ai_estimated_value_basis': ai_value_basis,
                    'ai_summary': ai_summary,
                }

                # Add attachments
                opp_attachments = att_by_opp.get(notice_id, [])
                raw_attachments = json.loads(opp.get('attachments_json') or '[]')

                record['attachments'] = []
                for raw_att in raw_attachments:
                    resource_id = raw_att.get('resourceId')
                    downloaded = next(
                        (a for a in opp_attachments if a.get('resource_id') == resource_id),
                        None
                    )

                    att_record = {
                        'name': raw_att.get('filename'),
                        'url': raw_att.get('downloadUrl'),
                        'file_type': raw_att.get('type', '').split('/')[-1] if raw_att.get('type') else None,
                        'file_size': raw_att.get('size'),
                    }

                    if downloaded and downloaded.get('extracted_text'):
                        att_record['text_content'] = downloaded['extracted_text']

                    record['attachments'].append(att_record)
                    stats['attachments_synced'] += 1

                # Add contacts
                contacts = json.loads(opp.get('contacts_json') or '[]')
                record['contacts'] = contacts

                payload.append(record)
                stats['opportunities_synced'] += 1

            except Exception as e:
                stats['errors'].append(f"{opp.get('opportunity_id')}: {str(e)}")

        # Send batch to Fly.io
        try:
            response = requests.post(
                f"{api_url}/api/v1/admin/bulk-import",
                json={'opportunities': payload},
                headers={'Content-Type': 'application/json'},
                timeout=120,
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Batch {batch_num + 1}/{total_batches}: Synced {len(payload)} opportunities")
            else:
                logger.warning(f"Batch {batch_num + 1}/{total_batches}: HTTP {response.status_code}")
                stats['errors'].append(f"Batch {batch_num + 1}: HTTP {response.status_code}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Batch {batch_num + 1}/{total_batches}: Request failed: {e}")
            stats['errors'].append(f"Batch {batch_num + 1}: {str(e)}")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Sync local scraper data to Fly.io")
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE_DB),
        help="Path to source SQLite database"
    )
    parser.add_argument(
        "--api-url",
        default=FLYIO_API_URL,
        help="Fly.io API URL"
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=None,
        help="Only sync opportunities modified in the last N days"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview sync without making changes"
    )
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        logger.error(f"Source database not found: {source_path}")
        sys.exit(1)

    print("=" * 60)
    print("BidKing Daily Sync to Fly.io")
    print("=" * 60)
    print(f"\nSource: {source_path}")
    print(f"Target: {args.api_url}")
    if args.days_back:
        print(f"Filter: Last {args.days_back} days")
    print()

    # Load source data
    opportunities, attachments, ai_analyses = load_source_data(
        str(source_path),
        days_back=args.days_back,
    )

    if not opportunities:
        logger.info("No opportunities to sync")
        sys.exit(0)

    # Sync to Fly.io
    logger.info("Starting sync to Fly.io...")
    stats = sync_to_flyio(
        opportunities,
        attachments,
        ai_analyses,
        api_url=args.api_url,
        dry_run=args.dry_run,
    )

    # Print results
    print("\n" + "=" * 60)
    print("Sync Complete" + (" (DRY RUN)" if args.dry_run else ""))
    print("=" * 60)
    print(f"  Opportunities synced: {stats['opportunities_synced']:,}")
    print(f"  Attachments synced:   {stats['attachments_synced']:,}")
    print(f"  AI summaries synced:  {stats['ai_summaries_synced']:,}")

    if stats['errors']:
        print(f"\n  Errors: {len(stats['errors'])}")
        for err in stats['errors'][:10]:
            print(f"    - {err}")
        if len(stats['errors']) > 10:
            print(f"    ... and {len(stats['errors']) - 10} more")


if __name__ == "__main__":
    main()
