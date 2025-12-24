"""
BidKing API - Federal Contract Alert Service

Main FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Runs on startup and shutdown.
    """
    # Startup
    print("BidKing API starting up...")

    # Create database tables
    from app.database import engine, Base
    from app.models import (
        User, Subscription, UsageTracking, AlertProfile,
        Opportunity, PointOfContact, SavedOpportunity, AlertSent,
        ContractAward, NAICSStatistics, Recipient, RecompeteOpportunity,
        LaborRateCache, CommonJobTitle, OpportunityAttachment, OpportunityHistory,
        # Company & Scoring models
        CompanyProfile, CompanyNAICS, CompanyCertification,
        PastPerformance, CapabilityStatement, OpportunityMetadata,
        OpportunityScore, OpportunityDecision
    )
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

    # Start background scheduler
    from app.services.scheduler import start_scheduler
    print("Starting background scheduler...")
    start_scheduler()
    print("Scheduler started!")

    yield

    # Shutdown
    print("BidKing API shutting down...")
    from app.services.scheduler import stop_scheduler
    stop_scheduler()


# Create FastAPI application
app = FastAPI(
    title="BidKing API",
    description="Federal Contract Alert Service - Find opportunities under $100K",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(",") if settings.cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Rate limit headers middleware
@app.middleware("http")
async def add_rate_limit_headers(request: Request, call_next):
    """Add rate limit headers to responses."""
    response = await call_next(request)

    # Add rate limit info if available
    if hasattr(request.state, "rate_limit_info"):
        info = request.state.rate_limit_info
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset_in"])

    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    import logging
    import traceback
    logger = logging.getLogger(__name__)
    logger.exception(f"Unhandled exception: {exc}")

    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "type": type(exc).__name__,
            "traceback": traceback.format_exc() if settings.debug else None,
        },
    )


# Include API routes
app.include_router(api_router, prefix="/api/v1")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "name": "BidKing API",
        "version": "1.0.0",
        "description": "Federal Contract Alert Service",
        "docs": "/docs" if settings.debug else "Disabled in production",
        "health": "/api/v1/webhooks/health",
    }


# Health check at root level
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


# Manual sync endpoint for populating opportunities
@app.post("/admin/sync-opportunities")
async def sync_opportunities_manual(days_back: int = 30, fetch_details: bool = True):
    """
    Manually trigger SAM.gov opportunity sync.

    This is a synchronous endpoint for initial data population.
    Set fetch_details=true to fetch full descriptions and attachments (slower but more complete).
    """
    import httpx
    from app.database import SessionLocal
    from app.models import Opportunity, PointOfContact, OpportunityAttachment, OpportunityHistory
    from sqlalchemy.dialects.postgresql import insert
    from datetime import timedelta

    # Software development and IT-related NAICS codes
    NAICS_CODES = [
        "541511",  # Custom Computer Programming Services
        "541512",  # Computer Systems Design Services
        "541519",  # Other Computer Related Services
        "518210",  # Data Processing, Hosting, and Related Services
    ]

    total_synced = 0
    total_fetched = 0
    errors = []
    debug_info = []

    posted_from = (datetime.utcnow() - timedelta(days=days_back)).strftime("%m/%d/%Y")
    posted_to = datetime.utcnow().strftime("%m/%d/%Y")

    debug_info.append(f"Date range: {posted_from} to {posted_to}")
    debug_info.append(f"API key set: {'Yes' if settings.sam_gov_api_key else 'No'}")
    debug_info.append(f"Fetch details: {fetch_details}")

    def fetch_description_content(desc_url: str, client: httpx.Client) -> str:
        """Fetch the actual description text from SAM.gov description API."""
        if not desc_url or not desc_url.startswith("http"):
            return desc_url or ""
        try:
            # Add API key if it's a SAM.gov API URL
            if "api.sam.gov" in desc_url:
                separator = "&" if "?" in desc_url else "?"
                desc_url = f"{desc_url}{separator}api_key={settings.sam_gov_api_key}"
            response = client.get(desc_url, timeout=30.0)
            if response.status_code == 200:
                # The API returns plain text or JSON with description
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    data = response.json()
                    return data.get("description", str(data))
                return response.text
        except Exception as e:
            debug_info.append(f"Description fetch error: {str(e)[:50]}")
        return ""

    import time
    for i, naics_code in enumerate(NAICS_CODES):
        # Add delay between requests to avoid rate limiting
        if i > 0:
            time.sleep(2)  # 2 second delay between NAICS codes
        try:
            url = "https://api.sam.gov/opportunities/v2/search"
            params = {
                "api_key": settings.sam_gov_api_key,
                "postedFrom": posted_from,
                "postedTo": posted_to,
                "ncode": naics_code,
                "limit": 500,
                "offset": 0,
            }

            with httpx.Client(timeout=60.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                opportunities = data.get("opportunitiesData", [])
                total_fetched += len(opportunities)
                debug_info.append(f"NAICS {naics_code}: {len(opportunities)} fetched")

                with SessionLocal() as db:
                    for opp_data in opportunities:
                        try:
                            notice_id = opp_data.get("noticeId")
                            if not notice_id:
                                continue

                            # Simple scoring - just use 50 as default
                            score = 50

                            # Parse place of performance
                            pop = opp_data.get("placeOfPerformance") or {}
                            pop_state_obj = pop.get("state") or {}
                            pop_city_obj = pop.get("city") or {}
                            pop_country_obj = pop.get("country") or {}

                            # Parse award details if present
                            award = opp_data.get("award") or {}

                            # Parse office address
                            office_addr = opp_data.get("officeAddress") or {}
                            contracting_office_address = None
                            if office_addr:
                                contracting_office_address = {
                                    "street": office_addr.get("streetAddress"),
                                    "city": office_addr.get("city"),
                                    "state": office_addr.get("state"),
                                    "zip": office_addr.get("zipcode"),
                                    "country": office_addr.get("countryCode"),
                                }

                            # Get full parent path for agency hierarchy
                            full_path = opp_data.get("fullParentPathName", "")
                            path_parts = full_path.split(".") if full_path else []
                            department = path_parts[0] if len(path_parts) > 0 else opp_data.get("departmentName")
                            sub_tier = path_parts[1] if len(path_parts) > 1 else None

                            # Fetch description content if it's a URL
                            description = opp_data.get("description", "")
                            if fetch_details and description and description.startswith("http"):
                                description = fetch_description_content(description, client)
                                time.sleep(0.3)  # Rate limiting

                            opp_record = {
                                "notice_id": notice_id,
                                "solicitation_number": opp_data.get("solicitationNumber"),
                                "title": opp_data.get("title", "")[:500],
                                "description": description,
                                "posted_date": _parse_date_manual(opp_data.get("postedDate")),
                                "original_published_date": _parse_datetime_manual(opp_data.get("publishDate")),
                                "response_deadline": _parse_datetime_manual(opp_data.get("responseDeadLine")),
                                "archive_date": _parse_date_manual(opp_data.get("archiveDate")),
                                "original_inactive_date": _parse_date_manual(opp_data.get("inactiveDate")),
                                "notice_type": opp_data.get("type"),
                                "related_notice_id": opp_data.get("relatedNotice", {}).get("noticeId") if isinstance(opp_data.get("relatedNotice"), dict) else opp_data.get("relatedNotice"),
                                "naics_code": opp_data.get("naicsCode"),
                                "naics_description": opp_data.get("classificationCode", {}).get("description") if isinstance(opp_data.get("classificationCode"), dict) else None,
                                "psc_code": opp_data.get("psc", {}).get("code") if isinstance(opp_data.get("psc"), dict) else opp_data.get("pscCode"),
                                "psc_description": opp_data.get("psc", {}).get("description") if isinstance(opp_data.get("psc"), dict) else None,
                                "department_name": department,
                                "sub_tier": sub_tier,
                                "agency_name": department,
                                "office_name": opp_data.get("officeName") or opp_data.get("office"),
                                "contracting_office_address": contracting_office_address,
                                "pop_city": pop_city_obj.get("name") if isinstance(pop_city_obj, dict) else str(pop_city_obj) if pop_city_obj else None,
                                "pop_state": pop_state_obj.get("code") if isinstance(pop_state_obj, dict) else str(pop_state_obj) if pop_state_obj else None,
                                "pop_zip": pop.get("zip"),
                                "pop_country": pop_country_obj.get("code") if isinstance(pop_country_obj, dict) else str(pop_country_obj) if pop_country_obj else None,
                                "set_aside_type": opp_data.get("typeOfSetAside"),
                                "set_aside_description": opp_data.get("typeOfSetAsideDescription"),
                                "authority": opp_data.get("additionalInfoLink"),  # Sometimes contains authority info
                                "award_number": award.get("awardNumber") if award else opp_data.get("awardNumber"),
                                "award_date": _parse_date_manual(award.get("awardDate")) if award else _parse_date_manual(opp_data.get("awardDate")),
                                "award_amount": award.get("amount") if award else None,
                                "awardee_name": award.get("awardee", {}).get("name") if award and award.get("awardee") else None,
                                "awardee_uei": award.get("awardee", {}).get("ueiSAM") if award and award.get("awardee") else None,
                                "likelihood_score": score,
                                "ui_link": f"https://sam.gov/opp/{notice_id}/view",
                                "raw_data": opp_data,
                                "status": "active",
                                "fetched_at": datetime.utcnow(),
                            }

                            stmt = insert(Opportunity).values(**opp_record)
                            stmt = stmt.on_conflict_do_update(
                                index_elements=["notice_id"],
                                set_={
                                    "title": stmt.excluded.title,
                                    "description": stmt.excluded.description,
                                    "response_deadline": stmt.excluded.response_deadline,
                                    "archive_date": stmt.excluded.archive_date,
                                    "naics_description": stmt.excluded.naics_description,
                                    "psc_code": stmt.excluded.psc_code,
                                    "psc_description": stmt.excluded.psc_description,
                                    "set_aside_description": stmt.excluded.set_aside_description,
                                    "contracting_office_address": stmt.excluded.contracting_office_address,
                                    "award_number": stmt.excluded.award_number,
                                    "award_date": stmt.excluded.award_date,
                                    "award_amount": stmt.excluded.award_amount,
                                    "awardee_name": stmt.excluded.awardee_name,
                                    "awardee_uei": stmt.excluded.awardee_uei,
                                    "likelihood_score": stmt.excluded.likelihood_score,
                                    "raw_data": stmt.excluded.raw_data,
                                    "fetched_at": stmt.excluded.fetched_at,
                                    "updated_at": datetime.utcnow(),
                                },
                            )
                            result = db.execute(stmt)

                            # Get the opportunity ID for related data
                            opp = db.query(Opportunity).filter(Opportunity.notice_id == notice_id).first()
                            if opp:
                                # Sync Points of Contact
                                pocs = opp_data.get("pointOfContact") or []
                                if isinstance(pocs, dict):
                                    pocs = [pocs]
                                for poc_data in pocs:
                                    if poc_data.get("email") or poc_data.get("fullName"):
                                        existing_poc = db.query(PointOfContact).filter(
                                            PointOfContact.opportunity_id == opp.id,
                                            PointOfContact.email == poc_data.get("email")
                                        ).first()
                                        if not existing_poc:
                                            poc = PointOfContact(
                                                opportunity_id=opp.id,
                                                contact_type=poc_data.get("type", "primary"),
                                                name=poc_data.get("fullName"),
                                                title=poc_data.get("title"),
                                                email=poc_data.get("email"),
                                                phone=poc_data.get("phone"),
                                                fax=poc_data.get("fax"),
                                            )
                                            db.add(poc)

                                # Sync Attachments/Links
                                if fetch_details:
                                    resources = opp_data.get("resourceLinks") or opp_data.get("attachments") or []
                                    if isinstance(resources, dict):
                                        resources = [resources]
                                    for res in resources:
                                        if res.get("url") or res.get("link"):
                                            existing_att = db.query(OpportunityAttachment).filter(
                                                OpportunityAttachment.opportunity_id == opp.id,
                                                OpportunityAttachment.url == (res.get("url") or res.get("link"))
                                            ).first()
                                            if not existing_att:
                                                att = OpportunityAttachment(
                                                    opportunity_id=opp.id,
                                                    name=res.get("name") or res.get("filename") or res.get("description"),
                                                    description=res.get("description"),
                                                    url=res.get("url") or res.get("link"),
                                                    resource_type=res.get("type", "link"),
                                                    file_type=res.get("mimeType"),
                                                    file_size=res.get("fileSize"),
                                                )
                                                db.add(att)

                            if result.rowcount > 0:
                                total_synced += 1
                        except Exception as e:
                            errors.append(f"Insert error for {opp_data.get('noticeId', 'unknown')}: {str(e)[:100]}")
                            continue

                    db.commit()

        except Exception as e:
            errors.append(f"NAICS {naics_code}: {str(e)}")

    return {
        "status": "completed",
        "total_fetched": total_fetched,
        "total_synced": total_synced,
        "naics_codes_processed": len(NAICS_CODES),
        "errors": errors[:20],  # Limit error output
        "debug": debug_info,
    }


def _parse_date_manual(date_str):
    """Parse date string to date object."""
    if not date_str:
        return None
    try:
        for fmt in ["%Y-%m-%d", "%m/%d/%Y"]:
            try:
                return datetime.strptime(date_str[:10], fmt).date()
            except ValueError:
                continue
        return None
    except Exception:
        return None


def _parse_datetime_manual(dt_str):
    """Parse datetime string to datetime object."""
    if not dt_str:
        return None
    try:
        if "T" in dt_str:
            dt_str = dt_str.replace("Z", "+00:00")
            return datetime.fromisoformat(dt_str.replace("+0000", "+00:00"))
        return datetime.strptime(dt_str, "%Y-%m-%d")
    except Exception:
        return None


# Manual USAspending sync endpoint for populating market intelligence data
@app.post("/admin/sync-usaspending")
async def sync_usaspending_manual(days_back: int = 90):
    """
    Manually trigger USAspending.gov contract awards sync.

    This endpoint:
    - Fetches recent contract awards from USAspending API
    - Populates ContractAward table
    - Creates RecompeteOpportunity records for contracts expiring within 365 days
    - NO API key required (public API)
    - NO rate limits (unlike SAM.gov)
    """
    import httpx
    from decimal import Decimal
    from app.database import SessionLocal
    from app.models import ContractAward, RecompeteOpportunity, Recipient
    from sqlalchemy.dialects.postgresql import insert

    USASPENDING_API_BASE = "https://api.usaspending.gov/api/v2"

    # NAICS codes for IT/Data/Cloud services
    NAICS_CODES = [
        "541511",  # Custom Computer Programming Services
        "541512",  # Computer Systems Design Services
        "541519",  # Other Computer Related Services
        "518210",  # Data Processing/Hosting - AWS, ETL
        "541690",  # Scientific/Technical Consulting - Data science
    ]

    total_awards_synced = 0
    total_recompetes_created = 0
    errors = []
    debug_info = []

    # Calculate date range
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    debug_info.append(f"Date range: {start_date} to {end_date}")
    debug_info.append(f"NAICS codes: {NAICS_CODES}")

    for naics_code in NAICS_CODES:
        try:
            url = f"{USASPENDING_API_BASE}/search/spending_by_award/"

            payload = {
                "filters": {
                    "time_period": [
                        {"start_date": start_date, "end_date": end_date}
                    ],
                    "award_type_codes": ["A", "B", "C", "D"],  # Contracts only
                    "naics_codes": [naics_code],
                },
                "fields": [
                    "Award ID",
                    "Recipient Name",
                    "Recipient UEI",
                    "Award Amount",
                    "Total Obligation",
                    "Start Date",
                    "End Date",
                    "Awarding Agency",
                    "Awarding Sub Agency",
                    "Award Type",
                    "NAICS Code",
                    "NAICS Description",
                    "PSC Code",
                    "Place of Performance City",
                    "Place of Performance State",
                    "Place of Performance Zip",
                    "generated_internal_id",
                ],
                "page": 1,
                "limit": 100,
                "sort": "Award Amount",
                "order": "desc",
            }

            naics_synced = 0
            naics_recompetes = 0

            with httpx.Client(timeout=60.0) as client:
                while True:
                    response = client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()

                    results = data.get("results", [])
                    if not results:
                        break

                    with SessionLocal() as db:
                        for award in results:
                            try:
                                award_id = award.get("generated_internal_id") or award.get("Award ID")
                                if not award_id:
                                    continue

                                # Parse dates
                                start_dt = _parse_date_manual(award.get("Start Date"))
                                end_dt = _parse_date_manual(award.get("End Date"))

                                award_record = {
                                    "award_id": award_id,
                                    "piid": award.get("Award ID"),
                                    "award_type": award.get("Award Type") or "contract",
                                    "total_obligation": Decimal(str(award.get("Total Obligation") or 0)),
                                    "base_and_all_options_value": Decimal(str(award.get("Award Amount") or 0)),
                                    "award_date": start_dt,
                                    "period_of_performance_start": start_dt,
                                    "period_of_performance_end": end_dt,
                                    "naics_code": naics_code,
                                    "naics_description": award.get("NAICS Description"),
                                    "psc_code": award.get("PSC Code"),
                                    "awarding_agency_name": award.get("Awarding Agency"),
                                    "awarding_sub_agency_name": award.get("Awarding Sub Agency"),
                                    "recipient_uei": award.get("Recipient UEI"),
                                    "recipient_name": award.get("Recipient Name"),
                                    "pop_city": award.get("Place of Performance City"),
                                    "pop_state": award.get("Place of Performance State"),
                                    "pop_zip": award.get("Place of Performance Zip"),
                                    "fetched_at": datetime.utcnow(),
                                }

                                stmt = insert(ContractAward).values(**award_record)
                                stmt = stmt.on_conflict_do_update(
                                    index_elements=["award_id"],
                                    set_={
                                        "total_obligation": stmt.excluded.total_obligation,
                                        "period_of_performance_end": stmt.excluded.period_of_performance_end,
                                        "fetched_at": stmt.excluded.fetched_at,
                                    },
                                )
                                db.execute(stmt)
                                naics_synced += 1

                                # Create recompete opportunity if expiring within 365 days from today
                                # Contract must have a future end date (not already expired)
                                today = datetime.utcnow().date()
                                if end_dt and end_dt >= today and end_dt <= (today + timedelta(days=365)):
                                    recompete_record = {
                                        "award_id": award_id,
                                        "piid": award.get("Award ID") or award_id,
                                        "period_of_performance_end": end_dt,
                                        "naics_code": naics_code,
                                        "total_value": Decimal(str(award.get("Award Amount") or 0)),
                                        "awarding_agency_name": award.get("Awarding Agency"),
                                        "incumbent_name": award.get("Recipient Name"),
                                        "incumbent_uei": award.get("Recipient UEI"),
                                        "status": "upcoming",
                                        "updated_at": datetime.utcnow(),
                                    }

                                    recompete_stmt = insert(RecompeteOpportunity).values(**recompete_record)
                                    recompete_stmt = recompete_stmt.on_conflict_do_update(
                                        index_elements=["award_id"],
                                        set_={
                                            "period_of_performance_end": recompete_stmt.excluded.period_of_performance_end,
                                            "total_value": recompete_stmt.excluded.total_value,
                                            "updated_at": recompete_stmt.excluded.updated_at,
                                        },
                                    )
                                    db.execute(recompete_stmt)
                                    naics_recompetes += 1

                                # Update recipient info
                                if award.get("Recipient UEI"):
                                    recipient_record = {
                                        "uei": award.get("Recipient UEI"),
                                        "name": award.get("Recipient Name"),
                                        "last_updated": datetime.utcnow(),
                                    }
                                    recipient_stmt = insert(Recipient).values(**recipient_record)
                                    recipient_stmt = recipient_stmt.on_conflict_do_update(
                                        index_elements=["uei"],
                                        set_={
                                            "name": recipient_stmt.excluded.name,
                                            "last_updated": recipient_stmt.excluded.last_updated,
                                        },
                                    )
                                    db.execute(recipient_stmt)

                            except Exception as e:
                                continue

                        db.commit()

                    # Check for more pages (max 5 pages per NAICS to avoid too much data)
                    if len(results) < payload["limit"] or payload["page"] >= 5:
                        break

                    payload["page"] += 1

            total_awards_synced += naics_synced
            total_recompetes_created += naics_recompetes
            debug_info.append(f"NAICS {naics_code}: {naics_synced} awards, {naics_recompetes} recompetes")

        except Exception as e:
            errors.append(f"NAICS {naics_code}: {str(e)}")

    return {
        "status": "completed",
        "total_awards_synced": total_awards_synced,
        "total_recompetes_created": total_recompetes_created,
        "naics_codes_processed": len(NAICS_CODES),
        "errors": errors,
        "debug": debug_info,
    }


# Generate recompetes from existing awards in database
@app.post("/admin/generate-recompetes")
async def generate_recompetes_from_awards(days_ahead: int = 365):
    """
    Scan existing contract awards and create recompete opportunities
    for any contracts expiring within the specified days.

    Run this AFTER sync-usaspending to process the synced awards.
    """
    from decimal import Decimal
    from app.database import SessionLocal
    from app.models import ContractAward, RecompeteOpportunity
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    today = datetime.utcnow().date()
    end_date = today + timedelta(days=days_ahead)

    total_recompetes = 0
    errors = []
    debug_info = []

    debug_info.append(f"Looking for awards with end dates between: {today} and {end_date}")

    with SessionLocal() as db:
        # Query awards with future end dates
        awards = db.query(ContractAward).filter(
            ContractAward.period_of_performance_end >= today,
            ContractAward.period_of_performance_end <= end_date,
        ).all()

        debug_info.append(f"Found {len(awards)} awards with expiring contracts")

        for i, award in enumerate(awards):
            try:
                # Check if recompete already exists
                existing = db.query(RecompeteOpportunity).filter(
                    RecompeteOpportunity.award_id == award.award_id
                ).first()

                if existing:
                    # Update existing - prefer base_and_all_options_value over total_obligation
                    existing.period_of_performance_end = award.period_of_performance_end
                    existing.total_value = award.base_and_all_options_value or award.total_obligation or Decimal("0")
                    existing.updated_at = datetime.utcnow()
                else:
                    # Create new - prefer base_and_all_options_value over total_obligation
                    recompete = RecompeteOpportunity(
                        award_id=award.award_id,
                        piid=award.piid or award.award_id,
                        period_of_performance_end=award.period_of_performance_end,
                        naics_code=award.naics_code,
                        total_value=award.base_and_all_options_value or award.total_obligation or Decimal("0"),
                        awarding_agency_name=award.awarding_agency_name,
                        incumbent_name=award.recipient_name,
                        incumbent_uei=award.recipient_uei,
                        status="upcoming",
                    )
                    db.add(recompete)

                total_recompetes += 1

                # Commit in batches
                if i > 0 and i % 100 == 0:
                    db.commit()

            except Exception as e:
                errors.append(f"Award {award.award_id}: {str(e)}")
                if len(errors) <= 5:
                    debug_info.append(f"Error on award {award.award_id}: {str(e)}")
                continue

        db.commit()

    return {
        "status": "completed",
        "total_recompetes_created": total_recompetes,
        "error_count": len(errors),
        "debug": debug_info,
    }


# Backfill recompete values from awards table
@app.post("/api/v1/admin/recompetes/backfill-values")
async def backfill_recompete_values():
    """
    Backfill total_value on recompetes from the linked award's base_and_all_options_value.
    Run this after initial sync to populate values.
    """
    from app.database import SessionLocal
    from app.models import RecompeteOpportunity
    from app.models.market_data import ContractAward

    updated = 0
    not_found = 0
    with SessionLocal() as db:
        # Get all recompetes with null or zero total_value
        recompetes = db.query(RecompeteOpportunity).filter(
            (RecompeteOpportunity.total_value == None) | (RecompeteOpportunity.total_value == 0)
        ).all()

        for r in recompetes:
            # Find the linked award
            award = db.query(ContractAward).filter(
                ContractAward.award_id == r.award_id
            ).first()

            if award:
                # Use base_and_all_options_value (full contract ceiling) if available
                value = award.base_and_all_options_value or award.total_obligation
                if value:
                    r.total_value = value
                    updated += 1
            else:
                not_found += 1

        db.commit()

    return {
        "status": "completed",
        "recompetes_updated": updated,
        "awards_not_found": not_found,
        "total_checked": len(recompetes),
    }


@app.post("/api/v1/admin/opportunities/ai-summarize")
async def trigger_ai_summarization(limit: int = 50, force: bool = False):
    """
    Manually trigger AI summarization of PDF attachments.

    This analyzes extracted PDF text using Claude to generate structured summaries
    including estimated contract value, clearance requirements, technologies, etc.

    Args:
        limit: Max number of PDFs to process (default: 50)
        force: Re-summarize even if already done (default: False)

    Note: This is automatically scheduled every 4 hours and on startup.
    """
    from app.services.ai_summarization import batch_summarize_attachments

    results = batch_summarize_attachments(limit=limit, force=force)

    return {
        "status": "completed",
        "processed": results["processed"],
        "summarized": results["summarized"],
        "failed": results["failed"],
        "skipped": results["skipped"],
        "errors": results["errors"][:10] if results["errors"] else [],
    }


# Public recompetes endpoint (no auth required)
@app.get("/api/v1/public/recompetes")
async def get_public_recompetes(
    naics_code: str = None,
    days_ahead: int = 365,
    page: int = 1,
    page_size: int = 25,
    search: str = None,
    agency: str = None,
    min_value: float = None,
    max_value: float = None,
    sort_by: str = "expiration",
    sort_order: str = "asc",
):
    """
    Get upcoming recompete opportunities (contracts expiring soon).

    This is a public endpoint - no authentication required.
    Shows contracts expiring within the specified days that will be re-bid.

    Filters:
    - naics_code: Filter by NAICS code
    - search: Search PIID, agency name, and incumbent name
    - agency: Filter by agency name (partial match)
    - min_value/max_value: Filter by contract value range
    - sort_by: expiration, value, agency, naics, incumbent, contract (default: expiration)
    - sort_order: asc or desc (default: asc)
    """
    from app.database import SessionLocal
    from app.models import RecompeteOpportunity
    from sqlalchemy import or_

    today = datetime.utcnow().date()
    end_date = today + timedelta(days=days_ahead)

    # Ensure page is at least 1
    page = max(1, page)
    # Limit page_size to reasonable bounds
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size

    with SessionLocal() as db:
        query = db.query(RecompeteOpportunity).filter(
            RecompeteOpportunity.period_of_performance_end.between(today, end_date),
        )

        # NAICS filter
        if naics_code:
            query = query.filter(RecompeteOpportunity.naics_code == naics_code)

        # Keyword search (PIID, agency, incumbent)
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    RecompeteOpportunity.piid.ilike(search_term),
                    RecompeteOpportunity.awarding_agency_name.ilike(search_term),
                    RecompeteOpportunity.incumbent_name.ilike(search_term),
                    RecompeteOpportunity.award_id.ilike(search_term),
                )
            )

        # Agency filter
        if agency:
            query = query.filter(RecompeteOpportunity.awarding_agency_name.ilike(f"%{agency}%"))

        # Value range filters
        if min_value is not None:
            query = query.filter(RecompeteOpportunity.total_value >= min_value)
        if max_value is not None:
            query = query.filter(RecompeteOpportunity.total_value <= max_value)

        total = query.count()
        total_pages = (total + page_size - 1) // page_size  # Ceiling division

        # Sorting
        if sort_by == "value":
            order_col = RecompeteOpportunity.total_value
        elif sort_by == "agency":
            order_col = RecompeteOpportunity.awarding_agency_name
        elif sort_by == "naics":
            order_col = RecompeteOpportunity.naics_code
        elif sort_by == "incumbent":
            order_col = RecompeteOpportunity.incumbent_name
        elif sort_by == "contract":
            order_col = RecompeteOpportunity.piid
        else:  # Default to expiration
            order_col = RecompeteOpportunity.period_of_performance_end

        if sort_order == "desc":
            order_col = order_col.desc()
        else:
            order_col = order_col.asc()

        recompetes = query.order_by(order_col).offset(offset).limit(page_size).all()

        items = []
        for r in recompetes:
            items.append({
                "id": str(r.id),
                "award_id": r.award_id,
                "piid": r.piid,
                "period_of_performance_end": r.period_of_performance_end.isoformat() if r.period_of_performance_end else None,
                "days_until_expiration": (r.period_of_performance_end - today).days if r.period_of_performance_end else None,
                "naics_code": r.naics_code,
                "total_value": float(r.total_value) if r.total_value else None,
                "awarding_agency_name": r.awarding_agency_name,
                "incumbent_name": r.incumbent_name,
                "status": r.status,
            })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "days_ahead": days_ahead,
    }


# Get filter options for recompetes (agencies, NAICS codes in use)
@app.get("/api/v1/public/recompetes/filters")
async def get_recompete_filter_options():
    """
    Get available filter options for recompetes.
    Returns unique agencies and NAICS codes currently in the database.
    """
    from app.database import SessionLocal
    from app.models import RecompeteOpportunity
    from sqlalchemy import func, distinct

    today = datetime.utcnow().date()
    end_date = today + timedelta(days=365)

    with SessionLocal() as db:
        # Get unique agencies with counts
        agencies = db.query(
            RecompeteOpportunity.awarding_agency_name,
            func.count(RecompeteOpportunity.id).label('count')
        ).filter(
            RecompeteOpportunity.period_of_performance_end.between(today, end_date),
            RecompeteOpportunity.awarding_agency_name.isnot(None)
        ).group_by(
            RecompeteOpportunity.awarding_agency_name
        ).order_by(
            func.count(RecompeteOpportunity.id).desc()
        ).limit(50).all()

        # Get unique NAICS codes with counts
        naics_codes = db.query(
            RecompeteOpportunity.naics_code,
            func.count(RecompeteOpportunity.id).label('count')
        ).filter(
            RecompeteOpportunity.period_of_performance_end.between(today, end_date),
            RecompeteOpportunity.naics_code.isnot(None)
        ).group_by(
            RecompeteOpportunity.naics_code
        ).order_by(
            func.count(RecompeteOpportunity.id).desc()
        ).all()

        # Get value range
        value_stats = db.query(
            func.min(RecompeteOpportunity.total_value),
            func.max(RecompeteOpportunity.total_value),
            func.avg(RecompeteOpportunity.total_value)
        ).filter(
            RecompeteOpportunity.period_of_performance_end.between(today, end_date),
            RecompeteOpportunity.total_value.isnot(None)
        ).first()

    return {
        "agencies": [{"name": a[0], "count": a[1]} for a in agencies if a[0]],
        "naics_codes": [{"code": n[0], "count": n[1]} for n in naics_codes if n[0]],
        "value_range": {
            "min": float(value_stats[0]) if value_stats[0] else 0,
            "max": float(value_stats[1]) if value_stats[1] else 0,
            "avg": float(value_stats[2]) if value_stats[2] else 0,
        }
    }


# Get single recompete with full details
@app.get("/api/v1/public/recompetes/{recompete_id}")
async def get_recompete_detail(recompete_id: str):
    """
    Get detailed information about a specific recompete opportunity.

    Includes the original contract award data if available.
    """
    from uuid import UUID
    from app.database import SessionLocal
    from app.models import RecompeteOpportunity, ContractAward

    today = datetime.utcnow().date()

    with SessionLocal() as db:
        # Get recompete
        recompete = db.query(RecompeteOpportunity).filter(
            RecompeteOpportunity.id == UUID(recompete_id)
        ).first()

        if not recompete:
            return {"error": "Recompete not found"}, 404

        # Get the original contract award for more details
        award = db.query(ContractAward).filter(
            ContractAward.award_id == recompete.award_id
        ).first()

        result = {
            "id": str(recompete.id),
            "award_id": recompete.award_id,
            "piid": recompete.piid,
            "period_of_performance_end": recompete.period_of_performance_end.isoformat() if recompete.period_of_performance_end else None,
            "days_until_expiration": (recompete.period_of_performance_end - today).days if recompete.period_of_performance_end else None,
            "naics_code": recompete.naics_code,
            "total_value": float(recompete.total_value) if recompete.total_value else None,
            "awarding_agency_name": recompete.awarding_agency_name,
            "incumbent_name": recompete.incumbent_name,
            "incumbent_uei": recompete.incumbent_uei,
            "status": recompete.status,
            "linked_opportunity_id": recompete.linked_opportunity_id,
            "created_at": recompete.created_at.isoformat() if recompete.created_at else None,
            "updated_at": recompete.updated_at.isoformat() if recompete.updated_at else None,
        }

        # Add contract award details if available
        if award:
            result["contract_details"] = {
                "award_type": award.award_type,
                "award_type_description": award.award_type_description,
                "total_obligation": float(award.total_obligation) if award.total_obligation else None,
                "base_and_all_options_value": float(award.base_and_all_options_value) if award.base_and_all_options_value else None,
                "award_date": award.award_date.isoformat() if award.award_date else None,
                "period_of_performance_start": award.period_of_performance_start.isoformat() if award.period_of_performance_start else None,
                "naics_description": award.naics_description,
                "psc_code": award.psc_code,
                "psc_description": award.psc_description,
                "awarding_sub_agency_name": award.awarding_sub_agency_name,
                "awarding_office_name": award.awarding_office_name,
                "recipient_uei": award.recipient_uei,
                "recipient_city": award.recipient_city,
                "recipient_state": award.recipient_state,
                "pop_city": award.pop_city,
                "pop_state": award.pop_state,
                "pop_zip": award.pop_zip,
                "competition_type": award.competition_type,
                "number_of_offers": award.number_of_offers,
                "set_aside_type": award.set_aside_type,
            }

            # Build USAspending link
            if award.award_id:
                result["usaspending_link"] = f"https://www.usaspending.gov/award/{award.award_id}"

    return result


# Scheduler status and control endpoints
@app.get("/admin/scheduler/status")
async def get_scheduler_status():
    """Get current scheduler status and job information."""
    from app.services.scheduler import get_scheduler_status
    return get_scheduler_status()


@app.post("/admin/scheduler/run/{job_name}")
async def run_scheduler_job(
    job_name: str,
    naics_code: str = "541511",
    max_results: int = 100,
):
    """
    Manually trigger a specific scheduler job.

    Available jobs:
    - usaspending: Sync USAspending contract awards
    - samgov: Sync SAM.gov opportunities (rate-limited public API)
    - scraper: Sync SAM.gov via internal API (NO rate limits - recommended!)
    - cleanup: Clean up expired recompetes
    - backfill_attachments: Backfill attachments via SAM.gov internal API
    - extract_pdf: Extract text from PDF attachments
    - ai_summarize: AI analyze PDF attachments

    For 'scraper' job:
    - naics_code: NAICS code to sync (default: 541511 Custom Programming)
    - max_results: Maximum opportunities to fetch (default: 100)

    Example:
    - POST /admin/scheduler/run/scraper?naics_code=541511&max_results=500
    """
    from app.services.scheduler import (
        sync_usaspending_job,
        sync_sam_gov_job,
        cleanup_expired_recompetes_job,
        backfill_attachments_job,
        extract_pdf_text_job,
        ai_summarization_job,
        scraper_sync_job,
    )

    jobs = {
        "usaspending": sync_usaspending_job,
        "samgov": sync_sam_gov_job,
        "scraper": lambda: scraper_sync_job(naics_code=naics_code, max_results=max_results, biddable_only=True),
        "cleanup": cleanup_expired_recompetes_job,
        "backfill_attachments": backfill_attachments_job,
        "extract_pdf": extract_pdf_text_job,
        "ai_summarize": ai_summarization_job,
    }

    if job_name not in jobs:
        return {
            "status": "error",
            "message": f"Unknown job: {job_name}",
            "available_jobs": list(jobs.keys()),
        }

    # Run the job synchronously (for manual triggers)
    try:
        result = jobs[job_name]()
        return {
            "status": "completed",
            "job": job_name,
            "message": f"Job '{job_name}' executed successfully",
            "result": result if result else None,
        }
    except Exception as e:
        return {
            "status": "error",
            "job": job_name,
            "message": str(e),
        }


@app.post("/admin/migrate-opportunity-schema")
async def migrate_opportunity_schema():
    """
    Add new columns to opportunities table for SAM.gov detail enhancements.

    This is a one-time migration endpoint to add columns without dropping data.
    Safe to run multiple times (uses IF NOT EXISTS).
    """
    from app.database import engine
    from sqlalchemy import text

    migrations_applied = []
    errors = []

    # List of ALTER TABLE statements to add new columns
    new_columns = [
        ("related_notice_id", "VARCHAR(100)"),
        ("original_published_date", "TIMESTAMP"),
        ("original_inactive_date", "DATE"),
        ("inactive_policy", "VARCHAR(255)"),
        ("sub_tier", "VARCHAR(255)"),
        ("contracting_office_address", "TEXT"),  # JSON stored as TEXT for SQLite
        ("contract_type", "VARCHAR(100)"),
        ("authority", "VARCHAR(500)"),
        ("initiative", "VARCHAR(255)"),
        ("task_delivery_order_number", "VARCHAR(100)"),
        ("modification_number", "VARCHAR(50)"),
    ]

    # Create opportunity_attachments table
    create_attachments_table = """
    CREATE TABLE IF NOT EXISTS opportunity_attachments (
        id VARCHAR(36) PRIMARY KEY,
        opportunity_id VARCHAR(36) NOT NULL,
        name VARCHAR(500),
        description TEXT,
        url TEXT,
        resource_type VARCHAR(50),
        file_type VARCHAR(50),
        file_size INTEGER,
        text_content TEXT,
        posted_date TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (opportunity_id) REFERENCES opportunities(id) ON DELETE CASCADE
    )
    """

    # Create opportunity_history table
    create_history_table = """
    CREATE TABLE IF NOT EXISTS opportunity_history (
        id VARCHAR(36) PRIMARY KEY,
        opportunity_id VARCHAR(36) NOT NULL,
        action VARCHAR(100) NOT NULL,
        changed_at TIMESTAMP NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (opportunity_id) REFERENCES opportunities(id) ON DELETE CASCADE
    )
    """

    with engine.connect() as conn:
        # Add new columns to opportunities table
        for col_name, col_type in new_columns:
            try:
                # SQLite uses a different syntax - need to check if column exists first
                result = conn.execute(text(f"PRAGMA table_info(opportunities)"))
                existing_columns = [row[1] for row in result.fetchall()]

                if col_name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE opportunities ADD COLUMN {col_name} {col_type}"))
                    migrations_applied.append(f"Added column: opportunities.{col_name}")
                else:
                    migrations_applied.append(f"Column exists: opportunities.{col_name}")
            except Exception as e:
                errors.append(f"Error adding {col_name}: {str(e)[:100]}")

        # Create attachments table
        try:
            conn.execute(text(create_attachments_table))
            migrations_applied.append("Created/verified table: opportunity_attachments")
        except Exception as e:
            errors.append(f"Error creating opportunity_attachments: {str(e)[:100]}")

        # Create history table
        try:
            conn.execute(text(create_history_table))
            migrations_applied.append("Created/verified table: opportunity_history")
        except Exception as e:
            errors.append(f"Error creating opportunity_history: {str(e)[:100]}")

        # Commit all changes
        conn.commit()

    return {
        "status": "completed",
        "migrations_applied": migrations_applied,
        "errors": errors,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
