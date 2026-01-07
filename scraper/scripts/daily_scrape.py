#!/usr/bin/env python3
"""
Daily SAM.gov Scraper

Scrapes new federal contract opportunities from SAM.gov posted in the last N days.
Uses the existing infrastructure with proxy rotation and SQLite storage.

Usage:
    python daily_scrape.py                    # Scrape last 7 days (default)
    python daily_scrape.py --days 1           # Scrape last 1 day
    python daily_scrape.py --days 30          # Scrape last 30 days
    python daily_scrape.py --download-pdfs    # Also download PDF attachments

Designed to run as a daily cron job.
"""

import asyncio
import sys
import os
import logging
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper import SAMScraper
from database import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent.parent / 'logs' / f'daily_scrape_{datetime.now().strftime("%Y%m%d")}.log'),
    ]
)
logger = logging.getLogger(__name__)


async def download_new_pdfs(db: Database, pdf_dir: Path, limit: int = 1000):
    """Download PDFs for opportunities that don't have them yet"""
    import httpx
    from proxy_manager import create_proxy_manager

    # Get attachments that need downloading
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.id, a.opportunity_id, a.resource_id, a.filename, a.download_url
            FROM attachments a
            WHERE a.pdf_downloaded = 0
              AND a.download_url IS NOT NULL
              AND (a.filename LIKE '%.pdf' OR a.mime_type LIKE '%pdf%')
            ORDER BY a.id DESC
            LIMIT ?
        """, (limit,))
        attachments = cursor.fetchall()

    if not attachments:
        logger.info("No new PDFs to download")
        return 0

    logger.info(f"Downloading {len(attachments)} new PDFs...")

    proxy_manager = create_proxy_manager()
    downloaded = 0

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        for att in attachments:
            att_id, opp_id, resource_id, filename, url = att

            try:
                # Create opportunity subdirectory
                opp_dir = pdf_dir / opp_id
                opp_dir.mkdir(parents=True, exist_ok=True)

                # Download file
                proxy = proxy_manager.get_proxy()
                proxy_url = proxy.url if proxy else None

                response = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
                    "Accept": "*/*",
                    "Referer": "https://sam.gov/"
                })

                if response.status_code == 200:
                    # Save file
                    safe_filename = filename.replace('/', '_').replace('\\', '_')[:100]
                    file_path = opp_dir / f"{resource_id}_{safe_filename}"

                    with open(file_path, 'wb') as f:
                        f.write(response.content)

                    # Update database
                    with db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE attachments
                            SET pdf_downloaded = 1, pdf_local_path = ?
                            WHERE id = ?
                        """, (str(file_path), att_id))
                        conn.commit()

                    downloaded += 1
                    if downloaded % 50 == 0:
                        logger.info(f"Downloaded {downloaded}/{len(attachments)} PDFs")
                else:
                    logger.warning(f"Failed to download {filename}: HTTP {response.status_code}")

            except Exception as e:
                logger.error(f"Error downloading {filename}: {e}")

            await asyncio.sleep(0.5)  # Rate limiting

    logger.info(f"Downloaded {downloaded} new PDFs")
    return downloaded


async def main():
    parser = argparse.ArgumentParser(description="Daily SAM.gov Scraper")
    parser.add_argument("--days", type=int, default=7, help="Number of days to scrape (default: 7)")
    parser.add_argument("--concurrent", type=int, default=10, help="Concurrent requests (default: 10)")
    parser.add_argument("--download-pdfs", action="store_true", help="Download PDF attachments after scraping")
    parser.add_argument("--pdf-limit", type=int, default=500, help="Max PDFs to download per run (default: 500)")
    parser.add_argument("--proxy-file", type=str,
                       default=str(Path(__file__).parent.parent / "webshare_datacenter_proxies.txt"),
                       help="Proxy file to use")
    args = parser.parse_args()

    # Paths
    base_dir = Path(__file__).parent.parent
    db_path = base_dir / "bidking_sam.db"
    pdf_dir = base_dir / "pdfs"
    logs_dir = base_dir / "logs"

    # Ensure directories exist
    logs_dir.mkdir(exist_ok=True)
    pdf_dir.mkdir(exist_ok=True)

    # Calculate date range
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=args.days)

    logger.info("=" * 60)
    logger.info("DAILY SAM.GOV SCRAPER")
    logger.info("=" * 60)
    logger.info(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    logger.info(f"Concurrent requests: {args.concurrent}")
    logger.info(f"Database: {db_path}")
    logger.info(f"Proxy file: {args.proxy_file}")

    # Initialize scraper
    scraper = SAMScraper(
        proxy_file=args.proxy_file,
        db_path=str(db_path),
        concurrent_requests=args.concurrent,
    )

    # Get initial stats
    initial_count = scraper.db.get_opportunity_count()
    logger.info(f"Initial opportunity count: {initial_count:,}")

    # Run scraper
    try:
        scraped = await scraper.scrape_date_range(start_date, end_date)
        logger.info(f"Scraped {scraped:,} opportunities")
    except KeyboardInterrupt:
        logger.info("Scrape interrupted by user")
        scraped = 0
    except Exception as e:
        logger.error(f"Scraper error: {e}")
        scraped = 0

    # Download PDFs if requested
    if args.download_pdfs:
        logger.info("")
        logger.info("=" * 60)
        logger.info("DOWNLOADING PDF ATTACHMENTS")
        logger.info("=" * 60)
        await download_new_pdfs(scraper.db, pdf_dir, limit=args.pdf_limit)

    # Final stats
    final_count = scraper.db.get_opportunity_count()
    new_count = final_count - initial_count

    logger.info("")
    logger.info("=" * 60)
    logger.info("DAILY SCRAPE COMPLETE")
    logger.info("=" * 60)
    logger.info(f"New opportunities added: {new_count:,}")
    logger.info(f"Total opportunities: {final_count:,}")

    # Get attachment stats
    with scraper.db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM attachments WHERE pdf_downloaded = 1")
        pdf_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM attachments WHERE text_extracted = 1")
        extracted_count = cursor.fetchone()[0]

    logger.info(f"PDFs downloaded: {pdf_count:,}")
    logger.info(f"Text extracted: {extracted_count:,}")


if __name__ == "__main__":
    asyncio.run(main())
