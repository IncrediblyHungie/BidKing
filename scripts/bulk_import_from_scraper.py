#!/usr/bin/env python3
"""
Bulk Import from Local SAM.gov Scraper

One-time import script to load opportunities from the local sam-mass-scraper
database (bidking_sam.db) into BidKing's production database.

Includes AI analysis summaries.

Usage:
    python scripts/bulk_import_from_scraper.py --source ~/Projects/sam-mass-scraper/bidking_sam.db
    python scripts/bulk_import_from_scraper.py --source ~/Projects/sam-mass-scraper/bidking_sam.db --dry-run
"""

import argparse
import json
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database import SessionLocal, engine
from app.models import Opportunity, PointOfContact, OpportunityAttachment
from app.config import settings


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


def parse_datetime(dt_str: str) -> Optional[datetime]:
    """Parse to datetime object"""
    if not dt_str:
        return None
    try:
        if 'T' in str(dt_str):
            # Handle ISO format
            dt_str = dt_str.replace('Z', '+00:00')
            if '+' in dt_str:
                dt_str = dt_str.split('+')[0]
            return datetime.fromisoformat(dt_str)
        return datetime.strptime(dt_str[:10], '%Y-%m-%d')
    except:
        return None


def get_state_code(state: str) -> Optional[str]:
    """Extract 2-letter state code"""
    if not state:
        return None
    if len(state) == 2:
        return state.upper()
    # Common state name mappings
    state_map = {
        'california': 'CA', 'virginia': 'VA', 'maryland': 'MD',
        'texas': 'TX', 'florida': 'FL', 'new york': 'NY',
        'district of columbia': 'DC', 'washington': 'WA',
        # Add more as needed
    }
    return state_map.get(state.lower(), state[:2].upper() if state else None)


def calculate_likelihood_score(opp: dict) -> int:
    """Calculate likelihood score (0-100) that contract is under $100K"""
    score = 50  # Start neutral

    title = (opp.get('title') or '').lower()
    desc = (opp.get('description') or '').lower()
    set_aside = (opp.get('set_aside_type') or '').lower()
    opp_type = (opp.get('type') or '').lower()

    # Positive indicators (likely smaller)
    if any(x in set_aside for x in ['small', 'sba', '8(a)', 'hubzone', 'sdvosb', 'wosb']):
        score += 15
    if any(x in opp_type for x in ['sources sought', 'special notice', 'rfi']):
        score += 10
    if any(x in title for x in ['support', 'maintenance', 'subscription', 'license']):
        score += 10
    if any(x in title for x in ['micro', 'small']):
        score += 15

    # Negative indicators (likely larger)
    if any(x in title for x in ['enterprise', 'system-wide', 'global', 'agency-wide']):
        score -= 15
    if 'idiq' in opp_type or 'idiq' in title:
        score -= 10
    if any(x in desc for x in ['million', '$1,000,000', 'multi-year']):
        score -= 15

    return max(0, min(100, score))


def load_source_data(source_db: str) -> tuple[List[dict], List[dict], List[dict]]:
    """Load opportunities, attachments, and AI analyses from source database."""

    conn = sqlite3.connect(source_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Load opportunities
    cursor.execute("""
        SELECT
            opportunity_id,
            solicitation_number,
            title,
            description,
            type,
            type_code,
            posted_date,
            modified_date,
            response_deadline,
            is_active,
            is_canceled,
            agency_name,
            sub_agency_name,
            office_name,
            naics_code,
            psc_code,
            set_aside_type,
            set_aside_description,
            place_city,
            place_state,
            place_state_code,
            place_country,
            sam_gov_link,
            award_amount,
            award_awardee,
            award_awardee_uei,
            contacts_json,
            attachments_json,
            scraped_at
        FROM opportunities
    """)
    opportunities = [dict(row) for row in cursor.fetchall()]

    # Load attachments with text content
    cursor.execute("""
        SELECT
            opportunity_id,
            resource_id,
            filename,
            mime_type,
            file_size,
            access_level,
            posted_date,
            download_url,
            text_extracted,
            extracted_text
        FROM attachments
        WHERE downloaded = 1 OR text_extracted = 1
    """)
    attachments = [dict(row) for row in cursor.fetchall()]

    # Load AI analyses
    cursor.execute("""
        SELECT
            opportunity_id,
            attachment_id,
            status,
            text_content,
            ai_summary,
            model_used,
            analyzed_at
        FROM ai_analysis
        WHERE status = 'completed' AND ai_summary IS NOT NULL
    """)
    ai_analyses = [dict(row) for row in cursor.fetchall()]

    conn.close()

    print(f"Loaded from {source_db}:")
    print(f"  - {len(opportunities):,} opportunities")
    print(f"  - {len(attachments):,} attachments with content")
    print(f"  - {len(ai_analyses):,} AI analyses")

    return opportunities, attachments, ai_analyses


def import_to_bidking(
    opportunities: List[dict],
    attachments: List[dict],
    ai_analyses: List[dict],
    dry_run: bool = False
) -> dict:
    """Import data into BidKing database."""

    stats = {
        'opportunities_inserted': 0,
        'opportunities_updated': 0,
        'contacts_inserted': 0,
        'attachments_inserted': 0,
        'ai_summaries_added': 0,
        'errors': []
    }

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

    if dry_run:
        print("\n=== DRY RUN - No changes will be made ===\n")

    with SessionLocal() as db:
        for i, opp in enumerate(opportunities):
            try:
                notice_id = opp['opportunity_id']

                # Check if opportunity exists
                existing = db.query(Opportunity).filter(
                    Opportunity.notice_id == notice_id
                ).first()

                # Determine status
                if opp.get('is_canceled'):
                    status = 'canceled'
                elif not opp.get('is_active'):
                    status = 'archived'
                else:
                    status = 'active'

                # Calculate likelihood score
                score = calculate_likelihood_score(opp)

                # Build opportunity record
                opp_data = {
                    'notice_id': notice_id,
                    'solicitation_number': opp.get('solicitation_number'),
                    'title': opp.get('title', 'Untitled'),
                    'description': opp.get('description'),
                    'notice_type': opp.get('type'),
                    'posted_date': parse_date(opp.get('posted_date')),
                    'response_deadline': parse_datetime(opp.get('response_deadline')),
                    'department_name': opp.get('agency_name'),
                    'sub_tier': opp.get('sub_agency_name'),
                    'agency_name': opp.get('agency_name'),
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
                    'likelihood_score': score,
                    'fetched_at': parse_datetime(opp.get('scraped_at')) or datetime.utcnow(),
                }

                # Get AI analysis for this opportunity (use first one's estimated value)
                ai_list = ai_by_opp.get(notice_id, [])
                if ai_list:
                    ai_data = ai_list[0]
                    ai_summary = json.loads(ai_data['ai_summary']) if isinstance(ai_data['ai_summary'], str) else ai_data['ai_summary']
                    if ai_summary:
                        est_value = ai_summary.get('estimated_value', {})
                        if est_value:
                            opp_data['ai_estimated_value_low'] = est_value.get('low')
                            opp_data['ai_estimated_value_high'] = est_value.get('high')
                            opp_data['ai_estimated_value_basis'] = est_value.get('basis')

                if not dry_run:
                    if existing:
                        # Update existing
                        for key, value in opp_data.items():
                            if value is not None:
                                setattr(existing, key, value)
                        existing.updated_at = datetime.utcnow()
                        opp_id = existing.id
                        stats['opportunities_updated'] += 1
                    else:
                        # Insert new
                        new_opp = Opportunity(**opp_data)
                        db.add(new_opp)
                        db.flush()  # Get the ID
                        opp_id = new_opp.id
                        stats['opportunities_inserted'] += 1

                    # Import contacts
                    contacts = json.loads(opp.get('contacts_json') or '[]')
                    for contact in contacts:
                        if contact.get('name') or contact.get('email'):
                            poc = PointOfContact(
                                opportunity_id=opp_id,
                                contact_type=contact.get('type', 'primary'),
                                name=contact.get('name'),
                                title=contact.get('title'),
                                email=contact.get('email'),
                                phone=contact.get('phone'),
                            )
                            db.add(poc)
                            stats['contacts_inserted'] += 1

                    # Import attachments with AI summaries
                    opp_attachments = att_by_opp.get(notice_id, [])
                    raw_attachments = json.loads(opp.get('attachments_json') or '[]')

                    # Combine scraped attachment info with downloaded content
                    for raw_att in raw_attachments:
                        resource_id = raw_att.get('resourceId')

                        # Find matching downloaded attachment
                        downloaded = next(
                            (a for a in opp_attachments if a.get('resource_id') == resource_id),
                            None
                        )

                        att_record = OpportunityAttachment(
                            opportunity_id=opp_id,
                            name=raw_att.get('filename'),
                            url=raw_att.get('downloadUrl'),
                            resource_type='file',
                            file_type=raw_att.get('type', '').split('/')[-1] if raw_att.get('type') else None,
                            file_size=raw_att.get('size'),
                            posted_date=parse_datetime(raw_att.get('postedDate')),
                            extraction_status='pending',
                        )

                        # Add extracted text if available
                        if downloaded and downloaded.get('extracted_text'):
                            att_record.text_content = downloaded['extracted_text']
                            att_record.extraction_status = 'extracted'
                            att_record.extracted_at = datetime.utcnow()

                        # Find AI summary for this attachment
                        for ai in ai_list:
                            ai_summary_data = json.loads(ai['ai_summary']) if isinstance(ai['ai_summary'], str) else ai['ai_summary']
                            if ai_summary_data:
                                att_record.ai_summary = ai_summary_data
                                att_record.ai_summary_status = 'summarized'
                                att_record.ai_summarized_at = parse_datetime(ai.get('analyzed_at'))
                                stats['ai_summaries_added'] += 1
                                break  # Use first AI summary found

                        db.add(att_record)
                        stats['attachments_inserted'] += 1

                else:
                    # Dry run - just count
                    if existing:
                        stats['opportunities_updated'] += 1
                    else:
                        stats['opportunities_inserted'] += 1

                # Progress update every 100
                if (i + 1) % 100 == 0:
                    print(f"  Processed {i + 1:,} / {len(opportunities):,} opportunities...")
                    if not dry_run:
                        db.commit()

            except Exception as e:
                stats['errors'].append(f"{opp.get('opportunity_id')}: {str(e)}")
                if len(stats['errors']) <= 5:
                    print(f"  Error: {opp.get('opportunity_id')}: {e}")

        if not dry_run:
            db.commit()
            print(f"\n  Committed all changes to database")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Import SAM.gov scraper data into BidKing")
    parser.add_argument(
        "--source",
        default=str(Path.home() / "Projects/sam-mass-scraper/bidking_sam.db"),
        help="Path to source SQLite database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview import without making changes"
    )
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"Error: Source database not found: {source_path}")
        sys.exit(1)

    print("=" * 60)
    print("BidKing Bulk Import from Local SAM.gov Scraper")
    print("=" * 60)
    print(f"\nSource: {source_path}")
    print(f"Target: BidKing database ({settings.database_url[:50]}...)")
    print()

    # Load source data
    opportunities, attachments, ai_analyses = load_source_data(str(source_path))

    if not opportunities:
        print("No opportunities found in source database")
        sys.exit(1)

    # Perform import
    print("\nStarting import...")
    stats = import_to_bidking(opportunities, attachments, ai_analyses, dry_run=args.dry_run)

    # Print results
    print("\n" + "=" * 60)
    print("Import Complete" + (" (DRY RUN)" if args.dry_run else ""))
    print("=" * 60)
    print(f"  Opportunities inserted: {stats['opportunities_inserted']:,}")
    print(f"  Opportunities updated:  {stats['opportunities_updated']:,}")
    print(f"  Contacts inserted:      {stats['contacts_inserted']:,}")
    print(f"  Attachments inserted:   {stats['attachments_inserted']:,}")
    print(f"  AI summaries added:     {stats['ai_summaries_added']:,}")

    if stats['errors']:
        print(f"\n  Errors: {len(stats['errors'])}")
        for err in stats['errors'][:10]:
            print(f"    - {err}")
        if len(stats['errors']) > 10:
            print(f"    ... and {len(stats['errors']) - 10} more")


if __name__ == "__main__":
    main()
