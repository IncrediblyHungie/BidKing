#!/usr/bin/env python3
"""
Daily SAM.gov Pipeline - One Command to Run Everything

Usage:
    python scripts/daily_pipeline.py /path/to/ContractOpportunitiesFullCSV.csv

This runs:
    1. CSV Import (filter, dedupe, queue)
    2. Fetch attachment metadata from SAM.gov API
    3. Download PDFs (no proxy, free!)
    4. AI Analysis with local Ollama

Each step only processes NEW items - safe to run multiple times.
"""

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

SCRAPER_DIR = Path(__file__).parent.parent


def run_step(name: str, cmd: list, timeout: int = None) -> bool:
    """Run a pipeline step and return success status."""
    print(f"\n{'='*60}")
    print(f"STEP: {name}")
    print(f"{'='*60}\n")

    try:
        result = subprocess.run(
            cmd,
            cwd=SCRAPER_DIR,
            timeout=timeout,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"WARNING: {name} timed out")
        return False
    except Exception as e:
        print(f"ERROR: {name} failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Daily SAM.gov import pipeline"
    )
    parser.add_argument(
        'csv_file',
        type=Path,
        help="Path to ContractOpportunitiesFullCSV.csv"
    )
    parser.add_argument(
        '--skip-download',
        action='store_true',
        help="Skip PDF download step"
    )
    parser.add_argument(
        '--skip-ai',
        action='store_true',
        help="Skip AI analysis step"
    )
    parser.add_argument(
        '--ai-limit',
        type=int,
        default=1000,
        help="Max opportunities to AI analyze (default: 1000)"
    )

    args = parser.parse_args()

    if not args.csv_file.exists():
        print(f"ERROR: CSV file not found: {args.csv_file}")
        return 1

    print("=" * 60)
    print("DAILY SAM.GOV PIPELINE")
    print("=" * 60)
    print(f"CSV: {args.csv_file}")

    # Step 1: Import CSV
    success = run_step(
        "Import CSV",
        [sys.executable, "scripts/daily_csv_import.py", str(args.csv_file), "--queue-ai"],
    )
    if not success:
        print("CSV import failed!")
        return 1

    # Step 2: Fetch attachment metadata
    success = run_step(
        "Fetch Attachment Metadata",
        [sys.executable, "scripts/fetch_attachments_metadata.py", "--limit", "1000"],
        timeout=600,  # 10 min timeout
    )
    if not success:
        print("WARNING: Attachment fetch had issues, continuing...")

    # Step 3: Download PDFs
    if not args.skip_download:
        success = run_step(
            "Download PDFs",
            [sys.executable, "scripts/download_attachments.py"],
            timeout=1800,  # 30 min timeout
        )
        if not success:
            print("WARNING: PDF download had issues, continuing...")
    else:
        print("\nSkipping PDF download (--skip-download)")

    # Step 4: AI Analysis
    if not args.skip_ai:
        success = run_step(
            "AI Analysis",
            [sys.executable, "local_ai_analyzer.py", "--limit", str(args.ai_limit)],
            timeout=7200,  # 2 hour timeout
        )
        if not success:
            print("WARNING: AI analysis had issues")
    else:
        print("\nSkipping AI analysis (--skip-ai)")

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)

    # Show final stats
    import sqlite3
    conn = sqlite3.connect(SCRAPER_DIR / "bidking_sam.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM opportunities")
    total_opps = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM attachments WHERE downloaded = 1")
    downloaded = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM opportunity_analysis WHERE status = 'completed'")
    analyzed = cursor.fetchone()[0]

    conn.close()

    print(f"Total opportunities: {total_opps:,}")
    print(f"Attachments downloaded: {downloaded:,}")
    print(f"AI analyses completed: {analyzed:,}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
