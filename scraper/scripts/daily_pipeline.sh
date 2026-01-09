#!/bin/bash
#
# Daily SAM.gov Full Pipeline
#
# Complete workflow:
# 1. Scrape new opportunities from SAM.gov (using local proxies)
# 2. Download PDF attachments
# 3. Extract text from PDFs
# 4. Run AI analysis (local Ollama)
# 5. Sync to BidKing production on Fly.io
#
# Cron setup (run at 6 AM daily):
#   0 6 * * * /home/peteylinux/Projects/BidKing/scraper/scripts/daily_pipeline.sh
#

set -e

# Configuration - Updated paths for BidKing integration
SCRAPER_DIR="/home/peteylinux/Projects/BidKing/scraper"
BIDKING_DIR="/home/peteylinux/Projects/BidKing"
LOGS_DIR="${SCRAPER_DIR}/logs"
VENV="${SCRAPER_DIR}/venv"
DATE=$(date +%Y-%m-%d)
DAYS_TO_SCRAPE=2
PDF_LIMIT=500
AI_LIMIT=200

# Sync secret for Fly.io authentication
export BIDKING_SYNC_SECRET="7b5e6e89762d0ef41e0eaf4fb0810707ed22c0e7d022865595afbe65a19ba7c2"

# Log file
mkdir -p "$LOGS_DIR"
LOG_FILE="${LOGS_DIR}/pipeline_${DATE}.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=============================================="
log "DAILY SAM.GOV FULL PIPELINE - $DATE"
log "=============================================="

# Lock file to prevent concurrent runs
LOCKFILE="/tmp/sam_daily_pipeline.lock"
if [ -f "$LOCKFILE" ]; then
    PID=$(cat "$LOCKFILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        log "ERROR: Another instance running (PID $PID). Exiting."
        exit 1
    fi
    rm -f "$LOCKFILE"
fi
echo $$ > "$LOCKFILE"
trap "rm -f $LOCKFILE" EXIT

cd "$SCRAPER_DIR"

# Check if venv exists, if not create it
if [ ! -d "$VENV" ]; then
    log "Creating virtual environment..."
    python3 -m venv "$VENV"
    source "${VENV}/bin/activate"
    pip install -r requirements.txt
else
    source "${VENV}/bin/activate"
fi

# ============================================
# STEP 1: Scrape new opportunities
# ============================================
log ""
log "STEP 1: Scraping SAM.gov (last $DAYS_TO_SCRAPE days)"
log "----------------------------------------------"

INITIAL_COUNT=$(sqlite3 bidking_sam.db "SELECT COUNT(*) FROM opportunities" 2>/dev/null || echo "0")
log "Initial count: $INITIAL_COUNT"

python3 scripts/daily_scrape.py \
    --days "$DAYS_TO_SCRAPE" \
    --concurrent 10 \
    --proxy-file "${SCRAPER_DIR}/webshare_datacenter_proxies.txt" \
    2>&1 | tee -a "$LOG_FILE"

AFTER_SCRAPE=$(sqlite3 bidking_sam.db "SELECT COUNT(*) FROM opportunities")
NEW_OPPS=$((AFTER_SCRAPE - INITIAL_COUNT))
log "New opportunities: $NEW_OPPS"

# ============================================
# STEP 2: Download PDF attachments
# ============================================
log ""
log "STEP 2: Downloading PDFs (limit: $PDF_LIMIT)"
log "----------------------------------------------"

PENDING_PDFS=$(sqlite3 bidking_sam.db "SELECT COUNT(*) FROM attachments WHERE pdf_downloaded = 0 AND (filename LIKE '%.pdf' OR mime_type LIKE '%pdf%')")
log "PDFs pending download: $PENDING_PDFS"

if [ "$PENDING_PDFS" -gt 0 ]; then
    python3 -c "
import asyncio
import sys
sys.path.insert(0, '.')
from scripts.daily_scrape import download_new_pdfs
from database import Database
from pathlib import Path

async def main():
    db = Database('bidking_sam.db')
    await download_new_pdfs(db, Path('pdfs'), limit=$PDF_LIMIT)

asyncio.run(main())
" 2>&1 | tee -a "$LOG_FILE"
fi

DOWNLOADED=$(sqlite3 bidking_sam.db "SELECT COUNT(*) FROM attachments WHERE pdf_downloaded = 1")
log "Total PDFs downloaded: $DOWNLOADED"

# ============================================
# STEP 3: Extract text from PDFs
# ============================================
log ""
log "STEP 3: Extracting text from PDFs"
log "----------------------------------------------"

PENDING_EXTRACT=$(sqlite3 bidking_sam.db "SELECT COUNT(*) FROM attachments WHERE pdf_downloaded = 1 AND text_extracted = 0")
log "PDFs pending extraction: $PENDING_EXTRACT"

if [ "$PENDING_EXTRACT" -gt 0 ]; then
    python3 two_phase_analyzer.py --phase1 --limit $PDF_LIMIT 2>&1 | tee -a "$LOG_FILE"
fi

EXTRACTED=$(sqlite3 bidking_sam.db "SELECT COUNT(*) FROM attachments WHERE text_extracted = 1")
log "Total text extracted: $EXTRACTED"

# ============================================
# STEP 4: AI Analysis (if Ollama is running)
# ============================================
log ""
log "STEP 4: AI Analysis (limit: $AI_LIMIT)"
log "----------------------------------------------"

# Check if Ollama is running
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    log "Ollama detected, running AI analysis..."

    PENDING_AI=$(sqlite3 bidking_sam.db "
        SELECT COUNT(DISTINCT a.opportunity_id)
        FROM attachments a
        WHERE a.text_extracted = 1
        AND a.opportunity_id NOT IN (SELECT opportunity_id FROM opportunity_analysis WHERE status = 'completed')
    " 2>/dev/null || echo "0")
    log "Opportunities pending AI analysis: $PENDING_AI"

    if [ "$PENDING_AI" -gt 0 ]; then
        python3 two_phase_analyzer.py --phase2 --limit $AI_LIMIT 2>&1 | tee -a "$LOG_FILE"
    fi

    AI_DONE=$(sqlite3 bidking_sam.db "SELECT COUNT(*) FROM opportunity_analysis WHERE status = 'completed'" 2>/dev/null || echo "0")
    log "Total AI analyzed: $AI_DONE"
else
    log "Ollama not running, skipping AI analysis"
    log "To enable: ollama serve & ollama pull qwen2.5:14b-instruct"
fi

# ============================================
# STEP 5: Sync to BidKing Fly.io
# ============================================
log ""
log "STEP 5: Syncing to BidKing production"
log "----------------------------------------------"

# Check if BidKing API is healthy
if curl -s "https://bidking-api.fly.dev/health" | grep -q "healthy"; then
    log "BidKing API: healthy"

    cd "$BIDKING_DIR"
    python3 scripts/daily_sync_to_flyio.py \
        --source "${SCRAPER_DIR}/bidking_sam.db" \
        --days-back "$DAYS_TO_SCRAPE" \
        2>&1 | tee -a "$LOG_FILE"

    BIDKING_COUNT=$(curl -s "https://bidking-api.fly.dev/api/v1/opportunities?page_size=1" | grep -o '"total":[0-9]*' | grep -o '[0-9]*' || echo "?")
    log "BidKing production count: $BIDKING_COUNT"
else
    log "WARNING: BidKing API not responding, skipping sync"
fi

# ============================================
# Summary
# ============================================
log ""
log "=============================================="
log "PIPELINE COMPLETE"
log "=============================================="
log "New opportunities scraped: $NEW_OPPS"
log "Total in local DB: $AFTER_SCRAPE"
log "PDFs downloaded: $DOWNLOADED"
log "Text extracted: $EXTRACTED"
log "Log: $LOG_FILE"
