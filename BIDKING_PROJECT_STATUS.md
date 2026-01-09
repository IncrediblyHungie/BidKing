# BidKing - Federal Contract Alert Service
## Complete Project Status & Architecture Documentation
**Last Updated:** December 23, 2025
**Status:** Production Ready

---

## Executive Summary

BidKing is a production-ready SaaS platform for discovering and tracking federal contracting opportunities under $100K. It helps small businesses and solo contractors find, analyze, and pursue federal contracts from SAM.gov and USAspending.gov.

### Production URLs
| Service | URL | Stack |
|---------|-----|-------|
| **Frontend** | https://bidking-web.fly.dev | React 19 + Vite + Tailwind |
| **Backend API** | https://bidking-api.fly.dev | FastAPI + SQLAlchemy |
| **Auth** | kihbcuxmlpzjbcrxirkq.supabase.co | Supabase Auth |

### Quick Stats
- **Backend Files:** 58 Python files
- **Frontend Files:** 125 TypeScript files
- **Database Tables:** 20 tables
- **API Endpoints:** 70+ endpoints
- **Subscription Tiers:** 3 (Free, Starter $29/mo, Pro $79/mo)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND (React)                              │
│  Landing → Auth → Dashboard → Opportunities → Recompetes → Pipeline     │
│                    → Analytics → Alerts → Onboarding                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          BACKEND API (FastAPI)                           │
│  /api/v1/opportunities  │  /api/v1/alerts    │  /api/v1/company         │
│  /api/v1/market         │  /api/v1/users     │  /api/v1/subscriptions   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│  PostgreSQL 15  │    │  External APIs      │    │  Background Jobs    │
│  (SQLite local) │    │  • SAM.gov          │    │  • APScheduler      │
│                 │    │  • USAspending.gov  │    │  • Celery + Redis   │
│  20 tables      │    │  • Anthropic Claude │    │  • 6 scheduled jobs │
└─────────────────┘    │  • Stripe           │    └─────────────────────┘
                       │  • Resend Email     │
                       └─────────────────────┘
```

---

## Tech Stack

### Frontend
| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19.0 | UI Framework |
| TypeScript | 5.7 | Type Safety |
| Vite | 6.0 | Build Tool |
| Tailwind CSS | 4.0 | Styling |
| Zustand | 5.0 | State Management |
| React Query | 5.x | Data Fetching |
| React Router | 7.1 | Navigation |
| ApexCharts | - | Visualizations |

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| FastAPI | 0.109.2 | Web Framework |
| SQLAlchemy | 2.0 | ORM |
| Pydantic | 2.x | Validation |
| APScheduler | 3.x | Job Scheduling |
| Celery | 5.x | Task Queue |
| Redis | - | Cache/Queue |

### External Services
| Service | Purpose |
|---------|---------|
| Supabase | Authentication |
| Stripe | Payments |
| Anthropic Claude | AI Analysis |
| Resend | Email |
| SAM.gov API | Opportunities |
| USAspending.gov | Award Data |

---

## Project Structure

### Backend (`/app`)
```
app/
├── api/                        # FastAPI route handlers
│   ├── __init__.py            # Router registration
│   ├── auth.py                # User authentication
│   ├── opportunities.py       # Contract opportunities
│   ├── alerts.py              # Alert profile CRUD
│   ├── market.py              # Market intelligence
│   ├── subscriptions.py       # Stripe integration
│   ├── users.py               # User profile
│   ├── profile.py             # Company profile & onboarding
│   └── webhooks.py            # Stripe webhooks
│
├── models/                     # SQLAlchemy ORM models
│   ├── user.py                # User with subscriptions
│   ├── opportunity.py         # SAM.gov contracts
│   ├── alert_profile.py       # Alert configurations
│   ├── market_data.py         # Awards & recompetes
│   ├── subscription.py        # Subscription tracking
│   └── company.py             # Company profiles
│
├── schemas/                    # Pydantic response models
│   ├── opportunity.py
│   ├── alert_profile.py
│   ├── user.py
│   └── company.py
│
├── services/                   # Business logic
│   ├── scheduler.py           # Background jobs
│   ├── stripe_service.py      # Payment processing
│   ├── ai_summarization.py    # Claude AI integration
│   ├── scoring_service.py     # Personalized scoring
│   ├── capability_analysis_service.py
│   └── text_mining_service.py
│
├── config.py                   # App settings
├── database.py                 # DB connection
└── main.py                     # FastAPI app entry
```

### Frontend (`/frontend/src`)
```
frontend/src/
├── pages/
│   ├── Landing/LandingPage.tsx
│   ├── AuthPages/SignIn.tsx, SignUp.tsx
│   ├── Dashboard/Home.tsx
│   ├── Opportunities/OpportunitiesList.tsx, OpportunityDetail.tsx
│   ├── Recompetes/RecompetesList.tsx, RecompeteDetail.tsx
│   ├── Pipeline/PipelinePage.tsx
│   ├── Analytics/AnalyticsPage.tsx
│   ├── Alerts/AlertProfilesList.tsx
│   └── Onboarding/CompanyOnboardingPage.tsx
│
├── api/
│   ├── client.ts              # Axios + auth
│   ├── opportunities.ts
│   ├── alerts.ts
│   ├── company.ts
│   ├── market.ts
│   └── subscriptions.ts
│
├── stores/                     # Zustand stores
│   ├── authStore.ts
│   ├── opportunitiesStore.ts
│   ├── alertsStore.ts
│   ├── profileStore.ts
│   └── companyStore.ts
│
├── components/
│   ├── auth/                  # Auth forms
│   ├── layout/                # Sidebar, header
│   ├── form/                  # Form controls
│   ├── ui/                    # Button, Badge, etc.
│   └── charts/                # ApexCharts
│
├── types/index.ts
├── lib/supabase.ts
└── App.tsx
```

---

## Database Schema

### Core Tables

#### 1. users
```sql
- id, email, password_hash
- company_name
- subscription_tier (free, starter, pro)
- email_reminders_enabled, deadline_warning_days
- supabase_id
```

#### 2. subscriptions
```sql
- user_id, stripe_customer_id, stripe_subscription_id
- tier, status
- current_period_start, current_period_end
```

#### 3. opportunities (SAM.gov)
```sql
- notice_id (PK), solicitation_number
- title, description, notice_type
- posted_date, response_deadline, archive_date
- agency_name, department_name
- naics_code, psc_code, set_aside_type
- pop_city, pop_state, pop_zip
- status (active, archived)
```

#### 4. opportunity_attachments
```sql
- opportunity_id, filename, url
- text_content (extracted PDF text)
- ai_summary (Claude analysis JSON)
- extraction_status (pending, extracted, failed, skipped)
```

#### 5. saved_opportunities (Pipeline)
```sql
- user_id, opportunity_id
- status (watching, researching, preparing, submitted, won, lost, archived)
- priority (1-5), notes, reminder_date
- stage_changed_at
```

#### 6. alert_profiles
```sql
- user_id, name
- naics_codes[], keywords[], states[], agencies[]
- alert_frequency (realtime, daily, weekly)
```

#### 7. recompete_opportunities
```sql
- award_id, piid
- period_of_performance_end, days_until_expiration
- incumbent_name, incumbent_uei
- total_value, naics_code, awarding_agency_name
```

#### 8. contract_awards (USAspending)
```sql
- award_id, piid
- base_and_all_options_value, total_obligation
- period_of_performance_start, period_of_performance_end
- awarding_agency_name, recipient_uei, recipient_name
- naics_code, psc_code
```

#### 9. company_profiles
```sql
- user_id, company_name
- duns_number, uei, cage_code
- business_size, employee_count, annual_revenue
- facility_clearance, has_sci_capability
- preferred_contract_min/max
- headquarters_state, preferred_states[]
- onboarding_completed, profile_completeness
```

#### 10. company_naics
```sql
- company_profile_id, naics_code
- years_of_experience, primary (bool)
```

#### 11. company_certifications
```sql
- company_profile_id
- certification_type (8a, WOSB, SB, SDVOSB, HUBZone, etc.)
- certification_number, expiration_date
```

#### 12. opportunity_scores
```sql
- opportunity_id, user_id
- overall_score (0-100)
- capability_score, eligibility_score, scale_score
- score_reasons (JSON)
```

---

## API Endpoints

### Public Endpoints (No Auth)

#### Opportunities
```
GET  /api/v1/public/opportunities
     ?search=&naics=&state=&agency=&set_aside=&posted_within=
     &page=1&page_size=20&sort_by=posted_date&sort_order=desc

GET  /api/v1/public/opportunities/{id}
GET  /api/v1/public/opportunities/{id}/ai-summary
GET  /api/v1/public/opportunities/stats
GET  /api/v1/public/opportunities/export/csv
```

#### Recompetes
```
GET  /api/v1/public/recompetes
     ?search=&naics_code=&agency=&state=&min_days=&max_days=
     &min_value=&max_value=&sort_by=expiration&page=1&page_size=20

GET  /api/v1/public/recompetes/{id}
GET  /api/v1/public/recompetes/{id}/contract-history
GET  /api/v1/public/recompetes/{id}/incumbent-profile
GET  /api/v1/public/recompetes/{id}/related-contracts
GET  /api/v1/public/recompetes/{id}/matched-opportunities
GET  /api/v1/public/recompetes/export/csv
```

#### Analytics
```
GET  /api/v1/analytics/market-overview
GET  /api/v1/analytics/value-distribution
GET  /api/v1/analytics/by-naics?limit=10
GET  /api/v1/analytics/by-agency?limit=10
GET  /api/v1/analytics/top-incumbents?limit=10
```

### Authenticated Endpoints (Supabase JWT)

#### Pipeline/Saved
```
GET    /api/v1/opportunities/saved/list?status_filter=watching
POST   /api/v1/opportunities/saved
PATCH  /api/v1/opportunities/saved/{id}
DELETE /api/v1/opportunities/saved/{id}
GET    /api/v1/opportunities/saved/stats
GET    /api/v1/opportunities/saved/export/csv
```

#### Alert Profiles
```
GET    /api/v1/alerts
POST   /api/v1/alerts
GET    /api/v1/alerts/{id}
PATCH  /api/v1/alerts/{id}
DELETE /api/v1/alerts/{id}
POST   /api/v1/alerts/{id}/test
```

#### Company Profile
```
GET    /api/v1/company/profile
PATCH  /api/v1/company/profile
POST   /api/v1/company/onboarding/complete
POST   /api/v1/company/onboarding/skip
GET    /api/v1/company/onboarding/status
GET    /api/v1/company/profile/naics
POST   /api/v1/company/profile/naics
DELETE /api/v1/company/profile/naics/{id}
GET    /api/v1/company/profile/certifications
POST   /api/v1/company/profile/certifications
DELETE /api/v1/company/profile/certifications/{id}
GET    /api/v1/company/scoring/debug
```

#### Subscriptions
```
GET    /api/v1/subscriptions/tiers
GET    /api/v1/subscriptions/current
POST   /api/v1/subscriptions/checkout
GET    /api/v1/subscriptions/portal
POST   /api/v1/subscriptions/webhook
```

### Admin Endpoints
```
POST   /api/v1/admin/migrate
POST   /api/v1/admin/recompetes/backfill-values
POST   /api/v1/admin/opportunities/ai-summarize?limit=100&force=false
POST   /admin/scheduler/run/backfill_attachments
POST   /admin/scheduler/run/extract_pdf
POST   /admin/scheduler/run/ai_summarize
```

---

## Feature Details

### 1. Opportunity Discovery
- **Text Search** - Title, description, attachment content
- **Filters** - NAICS, state, agency, set-aside, deadline range
- **Scoring** - 0-100 likelihood of <$100K contract
- **Pagination** - Configurable page size (1-100)
- **CSV Export** - Download filtered results

### 2. AI-Powered Analysis (Claude)
**Scheduled Pipeline:**
1. **7:30 AM UTC** - Fetch PDF attachments from SAM.gov
2. **8:00 AM UTC** - Extract text from PDFs (pypdf)
3. **Every 4 hours** - Run Claude analysis on unprocessed

**Extracted Fields:**
- Summary, estimated value (with basis)
- Period of performance, contract type
- Clearance required (None → TS/SCI)
- Technologies, labor categories
- Certifications required
- Work location, incumbent

### 3. Recompete Tracking
- **Expiring Contracts** - Contracts ending within 365 days
- **Filters** - NAICS, agency, state, days until expiration, value range
- **Enrichment** (lazy-loaded):
  - Contract history on same PIID
  - Incumbent company profile
  - Related contracts
  - Matching SAM.gov opportunities (scored 0-100)

### 4. Pipeline CRM
- **Kanban View** - Visual board with drag-and-drop
- **Stages** - watching → researching → preparing → submitted → won/lost/archived
- **Features:**
  - Priority levels (1-5)
  - Notes field
  - Reminder dates
  - Stage change timestamps
- **Stats Dashboard** - Count by stage, upcoming deadlines

### 5. Market Analytics
- **Overview** - Total contracts, value ($66B+), average size
- **Value Distribution** - Contracts by size bucket
- **NAICS Leaderboard** - Top 10 by contract value
- **Agency Analysis** - Top 10 by spending
- **Top Incumbents** - Companies with most expiring contracts

### 6. Company Onboarding & Scoring
**Profile Fields:**
- Company basics (name, UEI, CAGE, size)
- NAICS codes with experience levels
- Certifications (8(a), WOSB, SDVOSB, HUBZone)
- Security clearance levels
- Contract preferences (size, type, geography)

**6-Dimension Scoring:**
| Dimension | Weight | Description |
|-----------|--------|-------------|
| Capability | 25% | NAICS match + keyword matching |
| Eligibility | 20% | Set-aside + certification match |
| Scale Fit | 15% | Contract value vs company capacity |
| Win Probability | 15% | Clearance + agency experience |
| Strategic Fit | 10% | Contract type preferences |
| Timeline | 15% | Deadline feasibility |

---

## Subscription Tiers

| Feature | Free | Starter ($29/mo) | Pro ($79/mo) |
|---------|------|------------------|--------------|
| Alert Profiles | 1 | 5 | 20 |
| Alerts/Month | 10 | 100 | 500 |
| Saved Opportunities | 10 | 100 | 1000 |
| API Calls/Hour | 100 | 500 | 2000 |
| Instant Alerts | No | Yes | Yes |
| Labor Pricing | No | Yes | Yes |
| CSV Export | No | Yes | Yes |
| Recompetes Access | No | No | Yes |
| SMS Alerts | No | No | Yes |

---

## Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| `sync_sam_gov_job` | Every 6 hours | Fetch opportunities from SAM.gov |
| `sync_usaspending_job` | Daily 6:00 AM UTC | Fetch awards for recompetes |
| `backfill_attachments_job` | Daily 7:30 AM UTC | Get PDF URLs from SAM.gov |
| `extract_pdf_text_job` | Daily 8:00 AM UTC + startup | Extract text from PDFs |
| `ai_summarization_job` | Every 4 hours + startup | Run Claude analysis |
| `send_pipeline_reminders_job` | Daily 9:00 AM UTC | Email deadline reminders |

---

## Environment Variables

### Backend
```bash
DATABASE_URL=postgresql://user:pass@host:5432/db
REDIS_URL=redis://localhost:6379

# SAM.gov API
SAM_GOV_API_KEY=SAM-xxxxx

# Supabase Auth
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_JWT_SECRET=xxx

# AI
ANTHROPIC_API_KEY=sk-ant-xxx

# Payments
STRIPE_SECRET_KEY=sk_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# Email
RESEND_API_KEY=re_xxx
```

### Frontend
```bash
VITE_API_URL=https://bidking-api.fly.dev
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=xxx
```

---

## Deployment

### Fly.io Configuration

**API (`fly.toml`):**
```toml
app = "bidking-api"
primary_region = "sjc"

[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = "off"
  auto_start_machines = true
  min_machines_running = 1

[[vm]]
  memory = "1gb"
  cpu_kind = "shared"
  cpus = 1

[mounts]
  source = "bidking_data"
  destination = "/app/data"
```

### Deploy Commands
```bash
# API
cd /home/peteylinux/Projects/BidKing
/root/.fly/bin/flyctl deploy -a bidking-api

# Frontend
cd /home/peteylinux/Projects/BidKing/frontend
npm run build
/root/.fly/bin/flyctl deploy -a bidking-web

# Admin tasks
curl -X POST https://bidking-api.fly.dev/api/v1/admin/migrate
curl -X POST https://bidking-api.fly.dev/api/v1/admin/recompetes/backfill-values
```

---

## Recent Changes (December 2025)

### December 21, 2025
- **Fixed AI Analysis Endpoint** - Created missing `/opportunities/{id}/ai-summary`
- **Fixed Expired Opportunities** - Dashboard now excludes expired contracts
- **Added manual scheduler triggers** - Admin endpoints for backfill/extract/analyze

### December 12, 2025
- **Analytics Dashboard** - Full market intelligence with charts
- **CSV Export** - Bulk export for all list views
- **Recompete Enrichment** - 4 enrichment endpoints with lazy loading

### December 11, 2025
- **Pipeline CRM** - Kanban board with stages and priorities
- **Social Login** - Google, Microsoft, LinkedIn OAuth

### December 10, 2025
- **Contract Value Backfill** - 1,709 recompetes with values
- **Value Filters** - Min/max contract value filtering

---

## Implementation Status

### Complete (100%)
- User authentication (Supabase + Social)
- Opportunity listing with filters
- Recompete tracking with enrichment
- Pipeline CRM (Kanban + List)
- Market analytics dashboard
- Alert profiles
- AI-powered PDF analysis
- CSV export
- Stripe subscriptions
- Email alerts

### In Progress
- Company onboarding wizard (UI complete, integration pending)
- Personalized scoring (algorithm designed, implementation pending)

### Planned
- USAspending past performance import
- Capability statement analysis
- Win/loss outcome tracking
- ML-based scoring improvements
- Mobile app

---

## Key Files Reference

### Critical Backend Files
| File | Lines | Purpose |
|------|-------|---------|
| `app/main.py` | ~2000 | FastAPI app, all routes |
| `app/services/scheduler.py` | ~850 | All background jobs |
| `app/services/ai_summarization.py` | ~400 | Claude integration |
| `app/services/scoring_service.py` | ~640 | Personalized scoring |
| `app/models/company.py` | ~510 | Company profile models |
| `app/api/profile.py` | ~1020 | Company API endpoints |
| `app/api/opportunities.py` | ~670 | Opportunity endpoints |

### Critical Frontend Files
| File | Lines | Purpose |
|------|-------|---------|
| `pages/Opportunities/OpportunitiesList.tsx` | ~600 | Main opportunity search |
| `pages/Opportunities/OpportunityDetail.tsx` | ~800 | Opportunity detail + AI |
| `pages/Pipeline/PipelinePage.tsx` | ~700 | Kanban CRM |
| `pages/Analytics/AnalyticsPage.tsx` | ~500 | Analytics dashboard |
| `pages/Onboarding/CompanyOnboardingPage.tsx` | ~1030 | Onboarding wizard |
| `stores/authStore.ts` | ~300 | Auth state management |
| `stores/companyStore.ts` | ~540 | Company profile state |

---

## Troubleshooting

### Common Issues

**1. Opportunities not loading:**
- Check `SAM_GOV_API_KEY` is set
- Run sync job: `POST /admin/scheduler/run/sync_sam_gov`

**2. AI analysis not showing:**
- Check `ANTHROPIC_API_KEY` is set
- Run pipeline: backfill_attachments → extract_pdf → ai_summarize

**3. Authentication failing:**
- Verify Supabase URL and JWT secret
- Check CORS configuration for frontend URL

**4. Pipeline save failing:**
- Run migration: `POST /api/v1/admin/migrate`
- Check user subscription limits

### Logs
```bash
# API logs
/root/.fly/bin/flyctl logs -a bidking-api

# Frontend build logs
/root/.fly/bin/flyctl logs -a bidking-web
```

---

## Contact & Resources

- **GitHub Issues:** https://github.com/anthropics/claude-code/issues
- **SAM.gov API Docs:** https://open.gsa.gov/api/get-opportunities-public-api/
- **USAspending API:** https://api.usaspending.gov/
- **Supabase Docs:** https://supabase.com/docs

---

*Generated by Claude Code - December 23, 2025*
