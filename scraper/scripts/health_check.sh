#!/bin/bash
#
# Pipeline Health Check
#
# Checks if the daily pipeline ran successfully and sends desktop notification if not.
# Run this at 8 AM (2 hours after pipeline) via cron:
#   0 8 * * * /home/peteylinux/Projects/BidKing/scraper/scripts/health_check.sh
#

SCRAPER_DIR="/home/peteylinux/Projects/BidKing/scraper"
LOG_DIR="${SCRAPER_DIR}/logs"
TODAY=$(date +%Y-%m-%d)
LOG_FILE="${LOG_DIR}/pipeline_${TODAY}.log"
HEALTH_LOG="${LOG_DIR}/health_check.log"

# Function to send desktop notification
notify() {
    export DISPLAY=:0
    export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"
    notify-send -u critical "SAM.gov Pipeline" "$1" 2>/dev/null || true
    echo "[$(date)] $1" >> "$HEALTH_LOG"
}

# Check 1: Did today's pipeline log get created?
if [ ! -f "$LOG_FILE" ]; then
    notify "Pipeline did NOT run today! No log file found."
    exit 1
fi

# Check 2: Did it complete successfully?
if ! grep -q "PIPELINE COMPLETE" "$LOG_FILE"; then
    notify "Pipeline started but did NOT complete! Check $LOG_FILE"
    exit 1
fi

# Check 3: Were opportunities scraped?
NEW_OPPS=$(grep "New opportunities:" "$LOG_FILE" | tail -1 | grep -o '[0-9]*' || echo "0")
if [ "$NEW_OPPS" = "0" ]; then
    notify "Pipeline ran but found 0 new opportunities"
    # Not a hard failure - might just be no new postings
fi

# Check 4: Is BidKing API still healthy?
if ! curl -s "https://bidking-api.fly.dev/health" | grep -q "healthy"; then
    notify "BidKing API is DOWN!"
    exit 1
fi

# Check 5: Compare local vs production counts
LOCAL_COUNT=$(sqlite3 "${SCRAPER_DIR}/bidking_sam.db" "SELECT COUNT(*) FROM opportunities" 2>/dev/null || echo "0")
PROD_COUNT=$(curl -s "https://bidking-api.fly.dev/api/v1/opportunities?page_size=1" 2>/dev/null | grep -o '"total":[0-9]*' | grep -o '[0-9]*' || echo "0")

# If production is way behind local, sync may have failed
DIFF=$((LOCAL_COUNT - PROD_COUNT))
if [ "$DIFF" -gt 1000 ]; then
    notify "Production ($PROD_COUNT) is $DIFF behind local ($LOCAL_COUNT). Sync may have failed."
fi

# All good
echo "[$(date)] Health check passed. Local: $LOCAL_COUNT, Prod: $PROD_COUNT, New today: $NEW_OPPS" >> "$HEALTH_LOG"
