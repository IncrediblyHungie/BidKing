# BidKing Scraper Pipeline - In Progress

## Current Status (December 23, 2025)

### Completed
1. **Fixed SAM.gov scraper** - Added comprehensive type checking to handle variable API response formats
2. **Deployed to Fly.io** - Latest code deployed to bidking-api.fly.dev
3. **Ran scraper for NAICS 541511** - Completed with 130 opportunities in database

### In Progress (Running in Background)
Scrapers running for remaining NAICS codes:
- 541512 (Computer Systems Design)
- 541519 (Other Computer Related)
- 518210 (Data Processing/Hosting)
- 541690 (Scientific/Technical Consulting)

These take ~5-10 minutes each because they fetch 500 opportunities with 0.3s delay between API calls.

### Next Steps After Scrapers Complete

1. **Check opportunity count**:
   ```bash
   curl -s "https://bidking-api.fly.dev/api/v1/opportunities?page_size=1" | jq '.total'
   ```

2. **Run PDF extraction on all attachments**:
   ```bash
   curl -X POST "https://bidking-api.fly.dev/admin/scheduler/run/extract_pdf?limit=500"
   ```

3. **Run AI summarization** (uses Claude Sonnet to analyze PDFs):
   ```bash
   curl -X POST "https://bidking-api.fly.dev/admin/scheduler/run/ai_summarize?limit=100"
   ```

4. **Check extraction status**:
   ```bash
   curl "https://bidking-api.fly.dev/api/v1/admin/opportunities/extraction-status"
   ```

## Commands to Resume

### Re-run scrapers if needed
```bash
# Run all 5 NAICS codes
curl -X POST "https://bidking-api.fly.dev/admin/scheduler/run/scraper?naics_code=541511&max_results=500"
curl -X POST "https://bidking-api.fly.dev/admin/scheduler/run/scraper?naics_code=541512&max_results=500"
curl -X POST "https://bidking-api.fly.dev/admin/scheduler/run/scraper?naics_code=541519&max_results=500"
curl -X POST "https://bidking-api.fly.dev/admin/scheduler/run/scraper?naics_code=518210&max_results=500"
curl -X POST "https://bidking-api.fly.dev/admin/scheduler/run/scraper?naics_code=541690&max_results=500"
```

### Full pipeline (after scrapers complete)
```bash
# 1. Extract text from PDFs
curl -X POST "https://bidking-api.fly.dev/admin/scheduler/run/extract_pdf?limit=500"

# 2. AI summarize (Claude Sonnet - ~$0.08 per attachment)
curl -X POST "https://bidking-api.fly.dev/admin/scheduler/run/ai_summarize?limit=100"
```

## Key Files
- `app/services/sam_scraper.py` - SAM.gov internal API scraper (fixed type checking)
- `app/services/ai_summarization.py` - Claude Sonnet integration for PDF analysis
- `app/services/scheduler.py` - All background job definitions

## Expected Results
- ~110 biddable opportunities across 5 NAICS codes
- ~412 PDF attachments to extract and analyze
- AI cost estimate: ~$31-58 for all attachments with Sonnet
