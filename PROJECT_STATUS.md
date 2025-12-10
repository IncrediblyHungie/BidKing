# BidKing - Federal Contract Alert Service

## Project Overview

BidKing is a SaaS platform that helps small businesses and solo contractors discover federal contract opportunities under $100K. It differentiates from competitors like GovWin ($7K+/yr) and GovTribe ($40/mo) by:

1. **Contract Size Scoring** - Unique algorithm to identify contracts likely under $100K (no competitor has this)
2. **Affordable Pricing** - $29/mo for features that cost $1000s elsewhere
3. **Labor Pricing Intelligence** - Free CALC API integration (GovTribe doesn't have this)
4. **Simplicity** - Set up in 5 minutes, not 5 days

---

## Target Customer

- Solo IT consultants
- 1-10 person software/consulting shops
- New-to-govcon businesses
- 8(a), WOSB, SDVOSB, HUBZone certified businesses

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Frontend** | |
| Framework | React 19 + Vite |
| Language | TypeScript |
| Styling | Tailwind CSS v4 |
| State Management | Zustand |
| Data Fetching | React Query + Axios |
| UI Template | TailAdmin React |
| **Backend** | |
| Framework | FastAPI (Python 3.11+) |
| Database | PostgreSQL 15 |
| Cache/Broker | Redis |
| Task Queue | Celery + Celery Beat |
| Email Service | Resend |
| Payments | Stripe |
| Deployment | Fly.io |
| Containerization | Docker |

---

## Data Sources

| Source | Purpose | Rate Limit | Cost |
|--------|---------|------------|------|
| SAM.gov Opportunities API | Contract opportunities | 1,000/day (entity-associated) | Free |
| USAspending.gov API | Award history, competitors | Unlimited | Free |
| GSA CALC API | Labor pricing benchmarks | Unlimited | Free |

---

## Pricing Tiers

| Tier | Price | Alert Profiles | Alerts/Month | Features |
|------|-------|----------------|--------------|----------|
| **Free** | $0 | 1 | 10 | Daily digest only |
| **Starter** | $29/mo | 5 | 100 | Instant alerts, labor pricing |
| **Pro** | $79/mo | 20 | 500 | Recompetes, API access, SMS |

---

## Development Phases

### Phase 0: Foundation [COMPLETE]
- [x] Create project structure
- [x] PROJECT_STATUS.md
- [x] Directory scaffold
- [x] Docker Compose setup
- [x] Requirements and dependencies
- [x] Environment configuration (.env.example)
- [x] Database models (user, subscription, alert_profile, opportunity, market_data)
- [x] Alembic migrations (initial schema with 15 tables)

### Phase 1: Core MVP [COMPLETE]
- [x] User authentication (register, login, email verify, password reset)
- [x] Stripe subscription integration (checkout, portal, webhooks)
- [x] Alert profile CRUD with tier-based limits
- [x] SAM.gov opportunity sync (Celery tasks)
- [x] Opportunity matching engine with scoring
- [x] Email alert system (instant + daily + weekly digest)
- [x] Basic dashboard API (stats, search, filters)

### Phase 2: Market Intelligence [COMPLETE]
- [x] USAspending client (award sync, recipient profiles)
- [x] NAICS statistics (award sizes, counts, distributions)
- [x] Award size distribution buckets
- [x] Top competitors by NAICS
- [x] CALC API client (labor rate lookups)
- [x] Labor pricing benchmarks with caching
- [x] Recompete opportunity tracking

### Phase 3: Polish & Launch [IN PROGRESS]
- [x] Frontend architecture (React + Vite + TailAdmin)
- [x] Authentication UI (SignIn, SignUp forms)
- [x] Opportunities listing and detail pages
- [x] Alert profile management pages
- [ ] Landing page (components copied, needs assembly)
- [ ] Onboarding flow
- [x] Email templates (HTML branded)
- [x] Error handling & logging
- [x] Rate limiting (tier-based)
- [x] Deploy configuration (Fly.io ready)

### Phase 4: Premium Features (Post-Launch)
- [x] Recompete tracking (included in MVP)
- [x] Saved opportunities pipeline
- [ ] CSV export
- [x] API access for Pro tier
- [ ] SMS alerts (Twilio)

---

## Project Structure

```
BidKing/
├── PROJECT_STATUS.md          # This file - planning & progress
├── README.md                  # Project overview
├── .env.example               # Environment template
├── .gitignore
├── docker-compose.yml         # Local development
├── docker-compose.prod.yml    # Production compose
├── Dockerfile
├── fly.toml                   # Fly.io config
├── deploy.sh                  # Deployment script
├── requirements.txt
├── alembic.ini
├── frontend/                  # React Frontend
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── App.tsx            # Routes and layout
│   │   ├── main.tsx           # Entry point
│   │   ├── api/               # API client and services
│   │   │   ├── client.ts      # Axios instance with auth
│   │   │   ├── auth.ts        # Auth API
│   │   │   ├── opportunities.ts
│   │   │   ├── alerts.ts
│   │   │   ├── market.ts
│   │   │   └── subscriptions.ts
│   │   ├── stores/            # Zustand state
│   │   │   ├── authStore.ts
│   │   │   ├── opportunitiesStore.ts
│   │   │   └── alertsStore.ts
│   │   ├── types/             # TypeScript types
│   │   │   └── index.ts
│   │   ├── pages/             # Page components
│   │   │   ├── Opportunities/
│   │   │   ├── Alerts/
│   │   │   ├── Dashboard/
│   │   │   ├── AuthPages/
│   │   │   └── Landing/
│   │   ├── components/        # Reusable components
│   │   └── layout/            # Layout components
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI entry point
│   ├── config.py              # Settings
│   ├── database.py            # DB connection
│   ├── dependencies.py        # FastAPI deps
│   ├── models/                # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── subscription.py
│   │   ├── alert_profile.py
│   │   ├── opportunity.py
│   │   ├── alert_sent.py
│   │   └── market_data.py
│   ├── schemas/               # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── auth.py
│   │   ├── alert_profile.py
│   │   ├── opportunity.py
│   │   └── market_data.py
│   ├── api/                   # API routes
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── alerts.py
│   │   ├── opportunities.py
│   │   ├── market.py
│   │   ├── subscriptions.py
│   │   └── webhooks.py
│   ├── services/              # Business logic
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── sam_gov_service.py
│   │   ├── usaspending_service.py
│   │   ├── calc_service.py
│   │   ├── matching_service.py
│   │   ├── email_service.py
│   │   ├── stripe_service.py
│   │   └── scoring_service.py
│   └── utils/
│       ├── __init__.py
│       ├── security.py
│       └── redis_client.py
├── worker/                    # Celery
│   ├── __init__.py
│   ├── celery_app.py
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── sam_sync.py
│   │   ├── alert_tasks.py
│   │   ├── email_tasks.py
│   │   ├── usaspending_tasks.py
│   │   └── calc_tasks.py
│   └── beat_schedule.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── ...
└── scripts/
    ├── seed_naics.py
    ├── test_sam_api.py
    └── setup_local.sh
```

---

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://bidking:bidking@localhost:5432/bidking

# Redis
REDIS_URL=redis://localhost:6379/0

# SAM.gov API
SAM_GOV_API_KEY=SAM-66d526c8-1ab1-42fb-96b0-6eddf8af1363

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_STARTER_MONTHLY=price_...
STRIPE_PRICE_STARTER_YEARLY=price_...
STRIPE_PRICE_PRO_MONTHLY=price_...
STRIPE_PRICE_PRO_YEARLY=price_...

# Resend (Email)
RESEND_API_KEY=re_...
FROM_EMAIL=alerts@bidking.com

# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# App
APP_ENV=development
APP_URL=http://localhost:8000
```

---

## API Endpoints (Planned)

### Authentication
- `POST /api/v1/auth/register` - Create account
- `POST /api/v1/auth/login` - Get access token
- `POST /api/v1/auth/verify-email` - Verify email
- `POST /api/v1/auth/forgot-password` - Request reset
- `POST /api/v1/auth/reset-password` - Reset password

### Users
- `GET /api/v1/users/me` - Get current user
- `PATCH /api/v1/users/me` - Update profile
- `GET /api/v1/users/me/usage` - Get usage stats

### Alert Profiles
- `GET /api/v1/alerts` - List alert profiles
- `POST /api/v1/alerts` - Create alert profile
- `GET /api/v1/alerts/{id}` - Get alert profile
- `PATCH /api/v1/alerts/{id}` - Update alert profile
- `DELETE /api/v1/alerts/{id}` - Delete alert profile

### Opportunities
- `GET /api/v1/opportunities` - Search opportunities
- `GET /api/v1/opportunities/{id}` - Get opportunity detail
- `GET /api/v1/opportunities/matched` - Get matched opportunities

### Market Intelligence
- `GET /api/v1/market/naics/{code}/statistics` - NAICS stats
- `GET /api/v1/market/naics/{code}/size-distribution` - Award sizes
- `GET /api/v1/market/naics/{code}/competitors` - Top competitors
- `GET /api/v1/market/labor-rates/{job_title}` - Labor pricing
- `GET /api/v1/market/labor-rates/common` - Common job rates
- `GET /api/v1/market/recompetes` - Expiring contracts (Pro)

### Subscriptions
- `GET /api/v1/subscriptions/plans` - List plans
- `POST /api/v1/subscriptions/checkout` - Create checkout
- `GET /api/v1/subscriptions/current` - Current subscription
- `POST /api/v1/subscriptions/portal` - Billing portal
- `POST /api/v1/webhooks/stripe` - Stripe webhooks

---

## Celery Tasks (Planned)

### SAM.gov Sync
- `fetch_opportunities_for_naics` - Fetch by NAICS code
- `fetch_all_opportunities` - Master sync task
- `insert_opportunities` - Database insert

### Alert Processing
- `process_instant_alerts` - Match new opps to profiles
- `send_daily_digests` - Compile daily emails
- `send_weekly_digests` - Compile weekly emails

### Email
- `send_instant_alert` - Single alert email
- `send_digest_email` - Digest email
- `send_welcome_email` - Welcome email

### Market Intelligence
- `sync_naics_statistics` - Update NAICS stats
- `calculate_naics_stats` - Per-NAICS calculation
- `find_recompete_opportunities` - Find expiring contracts
- `refresh_common_job_title_rates` - Update labor rates

### Beat Schedule
- Every hour: SAM.gov sync
- Every 5 min: Process instant alerts
- Daily 6 AM: Send daily digests
- Weekly Monday: Send weekly digests
- Daily 4 AM: USAspending stats refresh
- Weekly Sunday: Recompete scan
- Weekly Saturday: CALC labor rate refresh

---

## Database Schema Overview

### Core Tables
- `users` - User accounts
- `subscriptions` - Stripe subscriptions
- `alert_profiles` - User alert configurations
- `opportunities` - SAM.gov opportunities
- `alerts_sent` - Alert delivery history
- `opportunity_tracking` - User saved/tracked opps

### Market Intelligence Tables
- `contract_awards` - USAspending award data
- `naics_statistics` - Aggregated NAICS stats
- `recipients` - Competitor profiles
- `recompete_opportunities` - Expiring contracts
- `labor_rate_cache` - CALC pricing data
- `common_job_titles` - Job title mappings

---

## Progress Log

### 2024-12-09 - Frontend Implementation

**Templates Used:**
- TailAdmin React (free-react-tailwind-admin-dashboard) for dashboard UI
- React SaaS Template components for landing page

**Frontend Stack:**
- React 19 + Vite + TypeScript
- Tailwind CSS v4
- Zustand for state management
- React Query (@tanstack/react-query) for data fetching
- Axios with auth interceptors
- react-hot-toast for notifications

**Files Created:**

API Layer (`src/api/`):
- `client.ts` - Axios client with JWT auth, token refresh interceptor
- `auth.ts` - Authentication API (login, register, verify, password reset)
- `opportunities.ts` - Opportunities API (list, get, save, analysis, stats)
- `alerts.ts` - Alert profiles API (CRUD, test)
- `market.ts` - Market intelligence API (overview, NAICS, labor rates, recompetes)
- `subscriptions.ts` - Subscriptions API (tiers, checkout, portal, invoices)
- `index.ts` - API exports

State Management (`src/stores/`):
- `authStore.ts` - Authentication state (user, tokens, login/logout/register)
- `opportunitiesStore.ts` - Opportunities state (list, filters, pagination, save)
- `alertsStore.ts` - Alert profiles state (CRUD, toggle, test)
- `index.ts` - Store exports

Types (`src/types/`):
- `index.ts` - Full TypeScript types (User, Opportunity, AlertProfile, etc.)

Pages Created (`src/pages/`):
- `Opportunities/OpportunitiesList.tsx` - Searchable opportunities table with score badges
- `Opportunities/OpportunityDetail.tsx` - Full opportunity view with POC, deadline, save
- `Alerts/AlertProfilesList.tsx` - Alert profiles list with toggle/delete
- `Alerts/AlertProfileForm.tsx` - Create/edit alert profile form

Updated Files:
- `App.tsx` - Added routes for opportunities, alerts, dashboard
- `components/auth/SignInForm.tsx` - Connected to auth store + API
- `components/auth/SignUpForm.tsx` - Connected to auth store + API

**Routes Added:**
- `/` and `/dashboard` - Dashboard home
- `/opportunities` - Opportunities list with search/filter
- `/opportunities/:id` - Opportunity detail view
- `/alerts` - Alert profiles list
- `/alerts/create` - Create new alert profile
- `/alerts/:id/edit` - Edit alert profile
- `/signin` - Sign in page
- `/signup` - Sign up page

---

### 2024-12-01 - Full Backend Implementation
- Created complete project directory structure (30+ files)
- Set up Docker Compose for local development (PostgreSQL, Redis, API, Celery)
- Created all database models (15 tables)
- Set up Alembic migrations
- Implemented FastAPI application with all endpoints
- Created Celery task system with beat schedule
- Implemented Stripe subscription integration
- Built SAM.gov sync, USAspending sync, CALC sync
- Created scoring algorithm for contract size estimation
- Set up Fly.io deployment configuration

**Files Created:**
- `app/main.py` - FastAPI application
- `app/config.py` - Settings and subscription tiers
- `app/database.py` - SQLAlchemy setup
- `app/models/*.py` - All database models
- `app/schemas/*.py` - Pydantic validation schemas
- `app/api/*.py` - All API endpoints
- `app/services/*.py` - Scoring and Stripe services
- `app/utils/*.py` - Security and Redis utilities
- `worker/celery_app.py` - Celery configuration
- `worker/tasks/*.py` - All Celery tasks
- `fly.toml` - Fly.io deployment config
- `deploy.sh` - Deployment script

---

## Commands Reference

```bash
# Frontend Development
cd frontend
npm install                             # Install dependencies
npm run dev                             # Start dev server (localhost:5173)
npm run build                           # Build for production
npm run preview                         # Preview production build

# Local Development
docker-compose up -d                    # Start services
docker-compose logs -f                  # View logs
docker-compose down                     # Stop services

# Database
alembic upgrade head                    # Run migrations
alembic revision --autogenerate -m "msg" # Create migration

# Celery
celery -A worker.celery_app worker -l info      # Start worker
celery -A worker.celery_app beat -l info        # Start beat

# API
uvicorn app.main:app --reload           # Start API server

# Testing
pytest                                  # Run tests
pytest --cov=app                        # With coverage

# Deployment
./deploy.sh                             # Deploy to Fly.io
```

---

## Notes

- SAM.gov API key needs to be entity-associated for 1,000 requests/day
- USAspending and CALC APIs have no documented rate limits
- Stripe test mode for development, switch to live for production
- Redis used for both Celery broker and caching
