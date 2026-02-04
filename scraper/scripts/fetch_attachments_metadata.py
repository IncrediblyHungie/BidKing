#!/usr/bin/env python3
"""
Fetch attachment metadata from SAM.gov API for queued opportunities.

This script:
1. Reads opportunities from import_queue (needs_attachments = 1)
2. Fetches attachment metadata from SAM.gov API
3. Inserts attachment records into the database
4. Marks the queue item as processed

After this runs, use download_attachments.py to download the actual files.

Usage:
    python scripts/fetch_attachments_metadata.py
    python scripts/fetch_attachments_metadata.py --limit 100
"""

import argparse
import asyncio
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import httpx

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent.parent / 'logs' / 'fetch_attachments.log', mode='a'),
    ]
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "bidking_sam.db"
PROXY_FILE = BASE_DIR / "brightdata_proxy.txt"

# SAM.gov API
SAM_RESOURCES_URL = "https://sam.gov/api/prod/opps/v3/opportunities"


def get_proxy() -> Optional[str]:
    """Load residential proxy if available."""
    if not PROXY_FILE.exists():
        return None
    with open(PROXY_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and ':' in line:
                parts = line.split(':')
                if len(parts) >= 4:
                    host, port, user, passwd = parts[0], parts[1], parts[2], parts[3]
                    return f'http://{user}:{passwd}@{host}:{port}'
    return None


def get_queued_opportunities(conn: sqlite3.Connection, limit: int = 500) -> List[str]:
    """Get opportunity IDs that need attachment metadata fetched."""
    cursor = conn.execute("""
        SELECT opportunity_id FROM import_queue
        WHERE needs_attachments = 1
        LIMIT ?
    """, (limit,))
    return [row[0] for row in cursor.fetchall()]


def init_attachments_table(conn: sqlite3.Connection):
    """Create attachments table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            filename TEXT,
            mime_type TEXT,
            file_size INTEGER,
            access_level TEXT DEFAULT 'public',
            posted_date TEXT,
            download_url TEXT,
            downloaded INTEGER DEFAULT 0,
            pdf_local_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(opportunity_id, resource_id),
            FOREIGN KEY (opportunity_id) REFERENCES opportunities(opportunity_id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_attachments_opp_id ON attachments(opportunity_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_attachments_downloaded ON attachments(downloaded)
    """)
    conn.commit()


async def fetch_attachments(
    client: httpx.AsyncClient,
    opp_id: str,
) -> List[Dict]:
    """Fetch attachment metadata from SAM.gov API."""
    url = f"{SAM_RESOURCES_URL}/{opp_id}/resources"

    try:
        response = await client.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.debug(f"No resources found for {opp_id}")
            return []
        logger.warning(f"HTTP error for {opp_id}: {e.response.status_code}")
        return []
    except Exception as e:
        logger.error(f"Error fetching {opp_id}: {e}")
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
                "opportunity_id": opp_id,
                "resource_id": resource_id,
                "filename": att.get("name", "unknown"),
                "mime_type": att.get("mimeType", ""),
                "file_size": att.get("size", 0),
                "access_level": att.get("accessLevel", "public"),
                "posted_date": att.get("postedDate"),
                "download_url": f"https://sam.gov/api/prod/opps/v3/opportunities/resources/files/{resource_id}/download",
            })

    return attachments


def save_attachments(conn: sqlite3.Connection, attachments: List[Dict]) -> int:
    """Save attachment records to database. Returns count inserted."""
    inserted = 0
    for att in attachments:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO attachments (
                    opportunity_id, resource_id, filename, mime_type,
                    file_size, access_level, posted_date, download_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                att['opportunity_id'],
                att['resource_id'],
                att['filename'],
                att['mime_type'],
                att['file_size'],
                att['access_level'],
                att['posted_date'],
                att['download_url'],
            ))
            if conn.total_changes:
                inserted += 1
        except sqlite3.Error as e:
            logger.error(f"Error saving attachment: {e}")
    return inserted


def mark_attachments_fetched(conn: sqlite3.Connection, opp_id: str):
    """Mark opportunity as having attachments fetched."""
    conn.execute("""
        UPDATE import_queue
        SET needs_attachments = 0, attachments_completed_at = ?
        WHERE opportunity_id = ?
    """, (datetime.now().isoformat(), opp_id))


async def process_batch(
    client: httpx.AsyncClient,
    conn: sqlite3.Connection,
    opp_ids: List[str],
    batch_num: int,
    total_batches: int,
) -> Dict[str, int]:
    """Process a batch of opportunities sequentially to avoid rate limits."""
    stats = {'fetched': 0, 'attachments': 0, 'no_attachments': 0, 'errors': 0}

    for opp_id in opp_ids:
        try:
            attachments = await fetch_attachments(client, opp_id)
            if attachments:
                save_attachments(conn, attachments)
                stats['attachments'] += len(attachments)
            else:
                stats['no_attachments'] += 1

            mark_attachments_fetched(conn, opp_id)
            stats['fetched'] += 1

            # Small delay between requests to avoid rate limiting
            await asyncio.sleep(0.2)

        except Exception as e:
            logger.error(f"Error for {opp_id}: {e}")
            stats['errors'] += 1

    conn.commit()
    logger.info(f"Batch {batch_num}/{total_batches}: {stats['fetched']} opps, {stats['attachments']} attachments")
    return stats


async def main(limit: int = 500, batch_size: int = 20):
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Fetch Attachment Metadata from SAM.gov")
    logger.info("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    init_attachments_table(conn)

    # Get queued opportunities
    opp_ids = get_queued_opportunities(conn, limit)
    if not opp_ids:
        logger.info("No opportunities in queue needing attachments")
        conn.close()
        return

    logger.info(f"Found {len(opp_ids)} opportunities to fetch")

    # Setup HTTP client (no proxy needed for metadata fetch)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }

    total_stats = {'fetched': 0, 'attachments': 0, 'no_attachments': 0, 'errors': 0}

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        # Process in batches
        batches = [opp_ids[i:i+batch_size] for i in range(0, len(opp_ids), batch_size)]
        total_batches = len(batches)

        for i, batch in enumerate(batches, 1):
            stats = await process_batch(client, conn, batch, i, total_batches)
            for k, v in stats.items():
                total_stats[k] += v

            # Small delay between batches to be nice to the API
            if i < total_batches:
                await asyncio.sleep(1)

    conn.close()

    # Print summary
    print("\n" + "=" * 40)
    print("FETCH SUMMARY")
    print("=" * 40)
    print(f"Opportunities processed: {total_stats['fetched']}")
    print(f"Attachments found:       {total_stats['attachments']}")
    print(f"No attachments:          {total_stats['no_attachments']}")
    print(f"Errors:                  {total_stats['errors']}")
    print("=" * 40)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Fetch attachment metadata from SAM.gov")
    parser.add_argument('--limit', type=int, default=500, help="Max opportunities to process")
    parser.add_argument('--batch-size', type=int, default=20, help="Concurrent requests per batch")
    args = parser.parse_args()

    asyncio.run(main(args.limit, args.batch_size))
