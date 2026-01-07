# BidKing SAM.gov Scraper

Local scraper and AI analysis engine for federal contract opportunities from SAM.gov.

## Overview

This scraper runs locally on your machine to:
1. **Scrape** new opportunities from SAM.gov API
2. **Download** PDF attachments
3. **Extract** text from PDFs using pypdf
4. **Analyze** opportunities using local Ollama AI (Qwen2.5:14b)
5. **Sync** results to BidKing production on Fly.io

## Directory Structure

```
scraper/
├── scripts/
│   ├── daily_pipeline.sh     # Main cron job - runs full pipeline
│   ├── daily_scrape.py       # SAM.gov scraper script
│   └── health_check.sh       # Monitoring and alerts
├── scraper.py                # Core SAM.gov API client
├── database.py               # SQLite database interface
├── proxy_manager.py          # Proxy rotation for scraping
├── two_phase_analyzer.py     # PDF extraction + AI analysis
├── local_ai_analyzer.py      # Ollama AI integration
├── bidking_sam.db            # SQLite database (10,250 opportunities)
├── webshare_datacenter_proxies.txt  # Proxy list
├── requirements.txt          # Python dependencies
├── logs/                     # Pipeline logs
└── pdfs/                     # Downloaded PDF attachments
```

## Setup

### 1. Create Virtual Environment

```bash
cd /home/peteylinux/Projects/BidKing/scraper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Install Ollama (for AI analysis)

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull the AI model
ollama pull qwen2.5:14b-instruct

# Start Ollama server (or use systemd)
ollama serve
```

### 3. Configure Cron Jobs

```bash
crontab -e
```

Add these lines:
```cron
# Daily SAM.gov scrape + sync to BidKing (6 AM)
0 6 * * * /home/peteylinux/Projects/BidKing/scraper/scripts/daily_pipeline.sh >> /home/peteylinux/Projects/BidKing/scraper/logs/cron.log 2>&1

# Health check for SAM.gov pipeline (8 AM)
0 8 * * * /home/peteylinux/Projects/BidKing/scraper/scripts/health_check.sh
```

## Manual Usage

### Run Full Pipeline

```bash
./scripts/daily_pipeline.sh
```

### Run Individual Steps

```bash
# Activate venv
source venv/bin/activate

# Step 1: Scrape new opportunities (last 2 days)
python3 scripts/daily_scrape.py --days 2 --concurrent 10 --proxy-file webshare_datacenter_proxies.txt

# Step 2: Extract text from PDFs
python3 two_phase_analyzer.py --phase1 --limit 500

# Step 3: Run AI analysis (requires Ollama)
python3 two_phase_analyzer.py --phase2 --limit 200

# Step 4: Sync to BidKing production
cd /home/peteylinux/Projects/BidKing
python3 scripts/daily_sync_to_flyio.py --source scraper/bidking_sam.db
```

## Database Schema

The SQLite database (`bidking_sam.db`) contains:

### opportunities
- `opportunity_id` - SAM.gov notice ID (primary key)
- `title`, `description` - Opportunity details
- `naics_code`, `psc_code` - Classification codes
- `agency_name`, `office_name` - Contracting agency
- `posted_date`, `response_deadline` - Key dates
- `set_aside_type` - Small business set-asides
- `sam_gov_link` - Direct link to SAM.gov

### attachments
- `opportunity_id` - Foreign key to opportunities
- `filename`, `download_url` - Attachment info
- `pdf_downloaded` - Whether PDF was downloaded
- `text_extracted` - Whether text was extracted
- `extracted_text` - Full text content

### opportunity_analysis
- `opportunity_id` - Foreign key to opportunities
- `status` - 'pending', 'completed', 'failed'
- `ai_summary` - JSON with AI analysis results

## AI Analysis Output

The AI extracts structured information from PDFs:
- **Summary** - Plain English description
- **Estimated Value** - Low/high range with basis
- **Period of Performance** - Contract duration
- **Clearance Required** - Security clearance level
- **Labor Categories** - Required roles
- **Technologies** - Tools and platforms mentioned
- **Certifications** - CMMI, ISO, FedRAMP, etc.

## Statistics (as of Jan 6, 2026)

| Metric | Count |
|--------|-------|
| Total Opportunities | 10,250 |
| PDFs Downloaded | 9,814 |
| Text Extracted | 2,664 |
| AI Analyzed | 2,652 |

## Troubleshooting

### Pipeline Not Running
Check cron log:
```bash
tail -f /home/peteylinux/Projects/BidKing/scraper/logs/cron.log
```

### Ollama Not Running
```bash
# Check if running
curl http://localhost:11434/api/tags

# Start manually
ollama serve &

# Or via systemd
sudo systemctl start ollama
```

### Database Locked
Only one process can write to SQLite at a time. Check for running processes:
```bash
ps aux | grep python3
```

### API Rate Limits
The scraper uses 0.5s delays between requests and proxy rotation. If seeing 429 errors, increase delay in `scraper.py`.

## Sync to BidKing

The daily pipeline automatically syncs to BidKing Fly.io production using:
```
/home/peteylinux/Projects/BidKing/scripts/daily_sync_to_flyio.py
```

This pushes opportunities to the `/api/v1/admin/bulk-import` endpoint in batches of 50.

## License

Internal BidKing tool - not for public distribution.
