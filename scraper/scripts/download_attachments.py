#!/usr/bin/env python3
"""
Download attachments from SAM.gov opportunities.
Focuses on PDFs first, uses residential proxy.
"""

import asyncio
import httpx
import sqlite3
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "bidking_sam.db"
PROXY_FILE = BASE_DIR / "brightdata_proxy.txt"
PDF_DIR = BASE_DIR / "pdfs"

# Ensure PDF directory exists
PDF_DIR.mkdir(exist_ok=True)


def get_proxy():
    """Load residential proxy if available."""
    if not PROXY_FILE.exists():
        return None
    try:
        with open(PROXY_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and ':' in line:
                    parts = line.split(':')
                    if len(parts) >= 4:
                        host, port, user, passwd = parts[0], parts[1], parts[2], parts[3]
                        return f'http://{user}:{passwd}@{host}:{port}'
    except:
        pass
    return None


def get_pending_attachments(conn, limit=100, pdf_only=True):
    """Get attachments that haven't been downloaded yet. Prioritizes import_queue items."""
    cursor = conn.cursor()
    # Prioritize new imports (in import_queue) first, then older ones
    if pdf_only:
        cursor.execute("""
            SELECT a.id, a.opportunity_id, a.resource_id, a.filename, a.download_url
            FROM attachments a
            LEFT JOIN import_queue q ON a.opportunity_id = q.opportunity_id
            WHERE (a.downloaded IS NULL OR a.downloaded = 0)
              AND a.mime_type = '.pdf'
              AND a.access_level = 'public'
            ORDER BY CASE WHEN q.opportunity_id IS NOT NULL THEN 0 ELSE 1 END, a.id
            LIMIT ?
        """, (limit,))
    else:
        cursor.execute("""
            SELECT a.id, a.opportunity_id, a.resource_id, a.filename, a.download_url
            FROM attachments a
            LEFT JOIN import_queue q ON a.opportunity_id = q.opportunity_id
            WHERE (a.downloaded IS NULL OR a.downloaded = 0)
              AND a.access_level = 'public'
            ORDER BY CASE WHEN q.opportunity_id IS NOT NULL THEN 0 ELSE 1 END, a.id
            LIMIT ?
        """, (limit,))
    return cursor.fetchall()


async def download_file(client, url, filepath):
    """Download a file from URL."""
    try:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            f.write(response.content)

        return True
    except Exception as e:
        return str(e)


async def main():
    print("=" * 60)
    print("ATTACHMENT DOWNLOADER")
    print("=" * 60)

    proxy_url = get_proxy()
    if proxy_url:
        print(f"Using proxy: {proxy_url.split('@')[1]}")
    else:
        print("No proxy - using direct connection (free!)")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get counts
    cursor.execute("""SELECT COUNT(*) FROM attachments
                      WHERE (downloaded IS NULL OR downloaded = 0)
                      AND mime_type = '.pdf' AND access_level = 'public'""")
    pending_pdfs = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM attachments WHERE downloaded = 1")
    downloaded = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM attachments WHERE downloaded = -1")
    failed = cursor.fetchone()[0]
    print(f"Failed (auth required): {failed:,}")

    print(f"Pending PDF downloads: {pending_pdfs:,}")
    print(f"Already downloaded: {downloaded:,}")

    if pending_pdfs == 0:
        print("No pending downloads!")
        return

    # Download in batches
    batch_size = 20
    total_downloaded = 0
    total_errors = 0

    async with httpx.AsyncClient(proxy=proxy_url, timeout=120) as client:
        while True:
            attachments = get_pending_attachments(conn, limit=batch_size)
            if not attachments:
                break

            print(f"\nProcessing batch of {len(attachments)} files...")

            for att in attachments:
                att_id, opp_id, resource_id, filename, download_url = att

                # Create opportunity folder
                opp_dir = PDF_DIR / opp_id
                opp_dir.mkdir(exist_ok=True)

                # Clean filename
                safe_filename = "".join(c for c in filename if c.isalnum() or c in '._- ')[:100]
                if not safe_filename.endswith('.pdf'):
                    safe_filename += '.pdf'

                filepath = opp_dir / safe_filename

                # Download
                result = await download_file(client, download_url, filepath)

                if result is True:
                    # Update database - success
                    cursor.execute(
                        "UPDATE attachments SET local_path = ?, downloaded = 1 WHERE id = ?",
                        (str(filepath), att_id)
                    )
                    conn.commit()
                    total_downloaded += 1
                    print(f"  ✓ {safe_filename[:50]}")
                else:
                    # Update database - mark as failed so we skip it next time
                    cursor.execute(
                        "UPDATE attachments SET downloaded = -1, download_error = ? WHERE id = ?",
                        (str(result)[:500], att_id)
                    )
                    conn.commit()
                    total_errors += 1
                    print(f"  ✗ {safe_filename[:50]}: {result[:50]}")

                # Rate limit
                await asyncio.sleep(0.2)

            print(f"Progress: {total_downloaded:,} downloaded, {total_errors:,} errors")

            # Safety check
            if total_downloaded + total_errors >= 500:
                print("\nReached 500 file limit for this run")
                break

    print(f"\n{'=' * 60}")
    print(f"COMPLETE: Downloaded {total_downloaded:,}, Errors {total_errors:,}")

    cursor.execute("SELECT COUNT(*) FROM attachments WHERE downloaded = 1")
    print(f"Total downloaded: {cursor.fetchone()[0]:,}")

    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
