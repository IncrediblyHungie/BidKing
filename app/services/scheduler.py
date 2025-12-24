"""
Scheduler Service for BidKing

Automated background jobs for syncing data from SAM.gov and USAspending.gov
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = BackgroundScheduler()


def sync_usaspending_job():
    """
    Background job to sync USAspending contract awards.

    Runs daily at 6 AM UTC to fetch recent contract awards
    and create recompete opportunities for expiring contracts.
    """
    import httpx
    from app.database import SessionLocal
    from app.models import ContractAward, RecompeteOpportunity, Recipient
    from sqlalchemy.dialects.postgresql import insert

    logger.info("Starting scheduled USAspending sync...")

    USASPENDING_API_BASE = "https://api.usaspending.gov/api/v2"

    # NAICS codes for IT/Data/Cloud services
    NAICS_CODES = [
        "541511",  # Custom Computer Programming Services
        "541512",  # Computer Systems Design Services
        "541519",  # Other Computer Related Services
        "518210",  # Data Processing/Hosting - AWS, ETL
        "541690",  # Scientific/Technical Consulting - Data science
    ]

    days_back = 30  # Sync last 30 days of awards
    total_awards_synced = 0
    total_recompetes_created = 0

    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    for naics_code in NAICS_CODES:
        try:
            url = f"{USASPENDING_API_BASE}/search/spending_by_award/"

            payload = {
                "filters": {
                    "time_period": [
                        {"start_date": start_date, "end_date": end_date}
                    ],
                    "award_type_codes": ["A", "B", "C", "D"],
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

                                start_dt = _parse_date(award.get("Start Date"))
                                end_dt = _parse_date(award.get("End Date"))

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
                                total_awards_synced += 1

                                # Create recompete if expiring within 365 days
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
                                    total_recompetes_created += 1

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
                                logger.warning(f"Error processing award: {e}")
                                continue

                        db.commit()

                    if len(results) < payload["limit"] or payload["page"] >= 5:
                        break

                    payload["page"] += 1

        except Exception as e:
            logger.error(f"Error syncing NAICS {naics_code}: {e}")

    logger.info(f"USAspending sync completed: {total_awards_synced} awards, {total_recompetes_created} recompetes")


def sync_sam_gov_job(naics_index: int = None):
    """
    Background job to sync SAM.gov opportunities WITH attachments.

    RATE LIMIT AWARE: SAM.gov has strict daily quotas (~10-100 requests/day for non-federal keys).
    This job is designed to:
    1. Only make 1 API request per run (one NAICS code, one page)
    2. Be called multiple times throughout the day via scheduler
    3. Track which NAICS was last synced to rotate through them

    Args:
        naics_index: Optional index to specify which NAICS code to sync (0-4).
                    If None, syncs the next NAICS in rotation based on hour of day.
    """
    import httpx
    import uuid
    from app.database import SessionLocal
    from app.models import Opportunity, OpportunityAttachment
    from app.config import settings
    from sqlalchemy.dialects.postgresql import insert

    if not settings.sam_gov_api_key:
        logger.warning("SAM.gov API key not configured, skipping sync")
        return

    # NAICS codes for IT/Data/Cloud services - we rotate through these
    NAICS_CODES = [
        "541511",  # Custom Computer Programming Services
        "541512",  # Computer Systems Design Services
        "541519",  # Other Computer Related Services
        "518210",  # Data Processing/Hosting - AWS, ETL
        "541690",  # Scientific/Technical Consulting - Data science
    ]

    # Determine which NAICS to sync based on time or explicit index
    if naics_index is not None:
        idx = naics_index % len(NAICS_CODES)
    else:
        # Rotate based on hour: 7AM->0, 11AM->1, 15PM->2, 19PM->3, 23PM->4
        hour = datetime.utcnow().hour
        idx = (hour // 4) % len(NAICS_CODES)

    naics_code = NAICS_CODES[idx]

    # Only sync last 3 days to minimize API calls - we run multiple times daily
    days_back = 3
    total_synced = 0
    total_attachments = 0

    posted_from = (datetime.utcnow() - timedelta(days=days_back)).strftime("%m/%d/%Y")
    posted_to = datetime.utcnow().strftime("%m/%d/%Y")

    logger.info(f"SAM.gov sync starting: NAICS {naics_code} (index {idx}), dates {posted_from} to {posted_to}")

    try:
        url = "https://api.sam.gov/opportunities/v2/search"
        # Use smaller page size to get more data per API call while staying conservative
        page_size = 100

        params = {
            "api_key": settings.sam_gov_api_key,
            "postedFrom": posted_from,
            "postedTo": posted_to,
            "ncode": naics_code,
            "limit": page_size,
            "offset": 0,  # Only fetch first page per run to conserve quota
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.get(url, params=params)

            # Check for rate limiting
            if response.status_code == 429:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                next_access = error_data.get("nextAccessTime", "unknown")
                logger.warning(f"SAM.gov rate limited. Next access: {next_access}")
                return {"status": "rate_limited", "next_access": next_access}

            response.raise_for_status()
            data = response.json()

        opportunities = data.get("opportunitiesData", [])
        total_records = data.get("totalRecords", 0)

        logger.info(f"NAICS {naics_code}: Got {len(opportunities)} of {total_records} total opportunities")

        if not opportunities:
            logger.info(f"No new opportunities for NAICS {naics_code}")
            return {"status": "success", "synced": 0, "naics": naics_code}

        # Process opportunities
        with SessionLocal() as db:
            for opp_data in opportunities:
                try:
                    notice_id = opp_data.get("noticeId")
                    if not notice_id:
                        continue

                    opp_record = {
                        "notice_id": notice_id,
                        "solicitation_number": opp_data.get("solicitationNumber"),
                        "title": opp_data.get("title", "")[:500],
                        "description": opp_data.get("description"),
                        "posted_date": _parse_date(opp_data.get("postedDate")),
                        "response_deadline": _parse_datetime(opp_data.get("responseDeadLine")),
                        "notice_type": opp_data.get("type"),
                        "naics_code": opp_data.get("naicsCode") or naics_code,
                        "agency_name": opp_data.get("fullParentPathName", "").split(".")[0] if opp_data.get("fullParentPathName") else opp_data.get("departmentName"),
                        "office_name": opp_data.get("officeName"),
                        "pop_state": opp_data.get("placeOfPerformance", {}).get("state", {}).get("code") if opp_data.get("placeOfPerformance") else None,
                        "set_aside_type": opp_data.get("typeOfSetAside"),
                        "likelihood_score": 50,
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
                            "raw_data": stmt.excluded.raw_data,
                            "fetched_at": stmt.excluded.fetched_at,
                            "updated_at": datetime.utcnow(),
                        },
                    )
                    db.execute(stmt)
                    total_synced += 1

                    # Get the opportunity ID for attachments
                    opp = db.query(Opportunity).filter(
                        Opportunity.notice_id == notice_id
                    ).first()

                    if opp:
                        # Process attachments/resourceLinks
                        resources = opp_data.get("resourceLinks") or opp_data.get("attachments") or []
                        for res in resources:
                            res_url = res.get("url") or res.get("link")
                            if not res_url:
                                continue

                            # Check if attachment already exists
                            existing = db.query(OpportunityAttachment).filter(
                                OpportunityAttachment.opportunity_id == opp.id,
                                OpportunityAttachment.url == res_url
                            ).first()

                            if not existing:
                                att = OpportunityAttachment(
                                    id=uuid.uuid4(),
                                    opportunity_id=opp.id,
                                    name=res.get("name") or res.get("filename") or res.get("description"),
                                    description=res.get("description"),
                                    url=res_url,
                                    resource_type=res.get("type", "link"),
                                    file_type=res.get("mimeType") or _guess_file_type(res_url),
                                    file_size=res.get("fileSize"),
                                    extraction_status="pending",
                                )
                                db.add(att)
                                total_attachments += 1

                except Exception as e:
                    logger.warning(f"Error processing opportunity: {e}")
                    continue

            db.commit()

        logger.info(f"SAM.gov sync completed: NAICS {naics_code}, {total_synced} opportunities, {total_attachments} attachments")
        return {"status": "success", "synced": total_synced, "attachments": total_attachments, "naics": naics_code}

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.warning(f"SAM.gov rate limited for NAICS {naics_code}")
            return {"status": "rate_limited", "naics": naics_code}
        logger.error(f"HTTP error syncing SAM.gov NAICS {naics_code}: {e}")
        return {"status": "error", "error": str(e), "naics": naics_code}
    except Exception as e:
        logger.error(f"Error syncing SAM.gov NAICS {naics_code}: {e}")
        return {"status": "error", "error": str(e), "naics": naics_code}


def _guess_file_type(url: str) -> str:
    """Guess file type from URL extension."""
    if not url:
        return None
    url_lower = url.lower()
    if ".pdf" in url_lower:
        return "application/pdf"
    elif ".doc" in url_lower:
        return "application/msword"
    elif ".xls" in url_lower:
        return "application/vnd.ms-excel"
    elif ".zip" in url_lower:
        return "application/zip"
    return None


def backfill_attachments_job():
    """
    Backfill attachments using SAM.gov internal API.

    The public SAM.gov API often doesn't include resourceLinks/attachments
    in the search results. This job uses the internal SAM.gov API
    (sam.gov/api/prod/opps/v3/opportunities/{id}/resources) which reliably
    returns all attachments for each opportunity.

    Runs daily at 7:30 AM UTC (after main SAM.gov sync).
    """
    import httpx
    import uuid
    import time
    from app.database import SessionLocal
    from app.models import Opportunity, OpportunityAttachment

    logger.info("Starting attachment backfill job (internal SAM.gov API)...")

    total_attachments = 0
    opportunities_processed = 0
    errors = 0

    with SessionLocal() as db:
        # Find opportunities without attachments (synced in last 7 days)
        # This catches newly synced opportunities that need attachment data
        recent_cutoff = datetime.utcnow() - timedelta(days=7)

        opportunities = db.query(Opportunity).filter(
            Opportunity.fetched_at >= recent_cutoff,
            Opportunity.notice_id.isnot(None),
        ).all()

        logger.info(f"Checking {len(opportunities)} recent opportunities for attachments")

        with httpx.Client(timeout=30.0) as client:
            for opp in opportunities:
                try:
                    # Check if already has attachments
                    existing_count = db.query(OpportunityAttachment).filter(
                        OpportunityAttachment.opportunity_id == opp.id
                    ).count()

                    if existing_count > 0:
                        continue  # Already has attachments

                    # Use internal SAM.gov API (no API key required)
                    resources_url = f"https://sam.gov/api/prod/opps/v3/opportunities/{opp.notice_id}/resources"

                    # Rate limit - be nice to SAM.gov
                    time.sleep(0.5)

                    response = client.get(resources_url)

                    if response.status_code == 404:
                        continue  # Opportunity not found in internal API

                    if response.status_code != 200:
                        logger.warning(f"Error fetching resources for {opp.notice_id}: HTTP {response.status_code}")
                        errors += 1
                        continue

                    data = response.json()

                    # Parse nested structure: _embedded -> opportunityAttachmentList -> attachments
                    embedded = data.get("_embedded", {})
                    attachment_list = embedded.get("opportunityAttachmentList", [])

                    for item in attachment_list:
                        attachments = item.get("attachments", [])
                        for att_data in attachments:
                            # Build download URL
                            attachment_id = att_data.get("attachmentId")
                            resource_id = att_data.get("resourceId")
                            if not attachment_id or not resource_id:
                                continue

                            download_url = f"https://sam.gov/api/prod/opps/v3/opportunities/{opp.notice_id}/resources/files/{resource_id}/download"

                            # Check if attachment already exists by URL
                            existing = db.query(OpportunityAttachment).filter(
                                OpportunityAttachment.opportunity_id == opp.id,
                                OpportunityAttachment.url == download_url
                            ).first()

                            if existing:
                                continue

                            att = OpportunityAttachment(
                                id=uuid.uuid4(),
                                opportunity_id=opp.id,
                                name=att_data.get("name"),
                                description=att_data.get("description"),
                                url=download_url,
                                resource_type=att_data.get("type", "file"),
                                file_type=att_data.get("mimeType") or _guess_file_type(att_data.get("name", "")),
                                file_size=att_data.get("size"),
                                extraction_status="pending",
                            )
                            db.add(att)
                            total_attachments += 1

                    opportunities_processed += 1

                    # Commit periodically
                    if opportunities_processed % 50 == 0:
                        db.commit()
                        logger.info(f"Progress: {opportunities_processed} opportunities, {total_attachments} attachments")

                except Exception as e:
                    logger.warning(f"Error processing {opp.notice_id}: {e}")
                    errors += 1
                    continue

        db.commit()

    logger.info(
        f"Attachment backfill completed: {opportunities_processed} opportunities checked, "
        f"{total_attachments} new attachments, {errors} errors"
    )


def archive_expired_opportunities_job():
    """
    Archive opportunities past their response deadline.

    Instead of deleting, we mark them as "archived" to preserve
    historical data for:
    - Award tracking (who won)
    - Competitive analysis
    - Proposal reuse
    - Analytics and trends

    Runs daily at 4:30 AM UTC.
    """
    from app.database import SessionLocal
    from app.models import Opportunity

    logger.info("Starting opportunity archival job...")

    today = datetime.utcnow()

    with SessionLocal() as db:
        # Archive opportunities past deadline (with 7-day grace period)
        # Keep them "active" for a week after deadline in case of extensions
        grace_period = today - timedelta(days=7)

        archived = db.query(Opportunity).filter(
            Opportunity.status == "active",
            Opportunity.response_deadline < grace_period
        ).update({"status": "archived", "updated_at": datetime.utcnow()})

        db.commit()

    logger.info(f"Archived {archived} expired opportunities (preserved for historical reference)")


def cleanup_expired_recompetes_job():
    """
    Archive recompetes that have already expired (contract ended).

    Changed from delete to archive to preserve historical data.
    Runs daily at 5 AM UTC.
    """
    from app.database import SessionLocal
    from app.models import RecompeteOpportunity

    logger.info("Starting expired recompetes archival...")

    today = datetime.utcnow().date()

    with SessionLocal() as db:
        # Archive instead of delete - change status to "expired"
        archived = db.query(RecompeteOpportunity).filter(
            RecompeteOpportunity.period_of_performance_end < today,
            RecompeteOpportunity.status != "expired"
        ).update({"status": "expired", "updated_at": datetime.utcnow()})
        db.commit()

    logger.info(f"Archived {archived} expired recompetes (preserved for historical reference)")


def extract_pdf_text_job():
    """
    Extract text from PDF attachments for keyword search.

    This job:
    - Only processes PDFs with extraction_status='pending'
    - Uses concurrent downloads for speed (5 parallel)
    - Marks each PDF with success/failure status
    - Never re-processes already attempted PDFs

    Runs daily at 8 AM UTC and once on startup.
    """
    import asyncio
    import httpx
    import io
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from app.database import SessionLocal
    from app.models import OpportunityAttachment
    from app.config import settings

    logger.info("Starting PDF text extraction job...")

    try:
        from pypdf import PdfReader
    except ImportError:
        logger.error("pypdf not installed - skipping PDF extraction")
        return

    extracted_count = 0
    failed_count = 0
    skipped_count = 0

    with SessionLocal() as db:
        # Find PDF attachments that haven't been processed yet
        # Only select PDFs (by URL or file_type)
        pending_pdfs = db.query(OpportunityAttachment).filter(
            OpportunityAttachment.extraction_status == "pending",
            OpportunityAttachment.url.isnot(None),
            (
                OpportunityAttachment.url.ilike("%.pdf") |
                OpportunityAttachment.file_type.ilike("%pdf%")
            )
        ).limit(100).all()  # Process 100 at a time

        if not pending_pdfs:
            logger.info("No pending PDFs to extract")
            return

        logger.info(f"Found {len(pending_pdfs)} PDFs to process")

        # Mark non-PDF attachments as skipped
        non_pdfs = db.query(OpportunityAttachment).filter(
            OpportunityAttachment.extraction_status == "pending",
            OpportunityAttachment.url.isnot(None),
            ~OpportunityAttachment.url.ilike("%.pdf"),
            (
                OpportunityAttachment.file_type.is_(None) |
                ~OpportunityAttachment.file_type.ilike("%pdf%")
            )
        ).all()

        for att in non_pdfs:
            att.extraction_status = "skipped"
            att.extracted_at = datetime.utcnow()
            skipped_count += 1

        def process_single_pdf(att_id: str, url: str, name: str) -> dict:
            """Process a single PDF - designed to run in thread pool."""
            result = {
                "id": att_id,
                "status": "failed",
                "text": None,
                "error": None
            }

            try:
                # Add API key if SAM.gov URL
                pdf_url = url
                if "api.sam.gov" in pdf_url:
                    separator = "&" if "?" in pdf_url else "?"
                    pdf_url = f"{pdf_url}{separator}api_key={settings.sam_gov_api_key}"

                # Download PDF with timeout
                with httpx.Client(timeout=60.0) as client:
                    response = client.get(pdf_url, follow_redirects=True)

                    if response.status_code == 429:
                        result["error"] = "Rate limited"
                        return result

                    if response.status_code != 200:
                        result["error"] = f"HTTP {response.status_code}"
                        return result

                    # Check content type
                    content_type = response.headers.get("content-type", "")
                    if "pdf" not in content_type.lower() and not url.lower().endswith(".pdf"):
                        result["status"] = "skipped"
                        result["error"] = f"Not a PDF: {content_type}"
                        return result

                    # Extract text from PDF
                    pdf_file = io.BytesIO(response.content)
                    reader = PdfReader(pdf_file)

                    text_parts = []
                    # Limit to first 50 pages for performance
                    for page in reader.pages[:50]:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)

                    if text_parts:
                        # Limit to 100KB of text
                        result["text"] = "\n\n".join(text_parts)[:100000]
                        result["status"] = "extracted"
                    else:
                        result["status"] = "extracted"
                        result["text"] = ""
                        result["error"] = "No text found in PDF"

            except Exception as e:
                result["error"] = str(e)[:500]

            return result

        # Process PDFs concurrently (5 at a time to avoid rate limits)
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(
                    process_single_pdf,
                    str(att.id),
                    att.url,
                    att.name
                ): att for att in pending_pdfs
            }

            for future in as_completed(futures):
                att = futures[future]
                try:
                    result = future.result()

                    # Update attachment in database
                    if result["status"] == "extracted":
                        att.text_content = result["text"]
                        att.extraction_status = "extracted"
                        extracted_count += 1
                    elif result["status"] == "skipped":
                        att.extraction_status = "skipped"
                        skipped_count += 1
                    else:
                        att.extraction_status = "failed"
                        att.extraction_error = result["error"]
                        failed_count += 1

                    att.extracted_at = datetime.utcnow()

                except Exception as e:
                    att.extraction_status = "failed"
                    att.extraction_error = str(e)[:500]
                    att.extracted_at = datetime.utcnow()
                    failed_count += 1
                    logger.error(f"Error extracting {att.name}: {e}")

        db.commit()

    logger.info(
        f"PDF extraction completed: {extracted_count} extracted, "
        f"{failed_count} failed, {skipped_count} skipped"
    )


def send_pipeline_reminders_job():
    """
    Send reminder emails for pipeline opportunities.

    This job checks for:
    1. Custom reminders: User-set reminder_date that is today
    2. Deadline warnings: Opportunities with response_deadline within X days

    Runs daily at 9 AM UTC.
    """
    from app.database import SessionLocal
    from app.models import SavedOpportunity, Opportunity, User
    from sqlalchemy.orm import joinedload

    logger.info("Starting pipeline reminders job...")

    today = datetime.utcnow().date()
    custom_reminders_sent = 0
    deadline_reminders_sent = 0

    with SessionLocal() as db:
        # 1. Custom reminders - reminder_date is today
        custom_reminders = db.query(SavedOpportunity).options(
            joinedload(SavedOpportunity.opportunity)
        ).join(
            User, SavedOpportunity.user_id == User.id
        ).filter(
            SavedOpportunity.reminder_date == today,
            SavedOpportunity.reminder_sent == False,
            SavedOpportunity.status.notin_(["won", "lost", "archived"]),
            User.email_reminders_enabled == True,
            User.is_active == True,
        ).all()

        for saved_opp in custom_reminders:
            try:
                # Queue reminder email via Celery
                from worker.tasks.email_sending import send_reminder_email
                send_reminder_email.delay(
                    str(saved_opp.user_id),
                    str(saved_opp.id),
                    "custom"
                )
                custom_reminders_sent += 1
            except Exception as e:
                logger.error(f"Failed to queue custom reminder for {saved_opp.id}: {e}")

        # 2. Deadline warnings - opportunities with deadline within user's warning days
        # Group by user's deadline_warning_days setting
        users_with_settings = db.query(User).filter(
            User.email_deadline_warnings == True,
            User.is_active == True,
        ).all()

        for user in users_with_settings:
            warning_days = user.deadline_warning_days or 5
            warning_date = today + timedelta(days=warning_days)

            deadline_reminders = db.query(SavedOpportunity).options(
                joinedload(SavedOpportunity.opportunity)
            ).filter(
                SavedOpportunity.user_id == user.id,
                SavedOpportunity.deadline_reminder_sent == False,
                SavedOpportunity.status.notin_(["won", "lost", "archived", "submitted"]),
            ).all()

            for saved_opp in deadline_reminders:
                opp = saved_opp.opportunity
                if not opp or not opp.response_deadline:
                    continue

                deadline_date = opp.response_deadline.date() if hasattr(opp.response_deadline, 'date') else opp.response_deadline

                # Check if deadline is exactly warning_days away
                if deadline_date == warning_date:
                    try:
                        from worker.tasks.email_sending import send_reminder_email
                        send_reminder_email.delay(
                            str(saved_opp.user_id),
                            str(saved_opp.id),
                            "deadline"
                        )
                        deadline_reminders_sent += 1
                    except Exception as e:
                        logger.error(f"Failed to queue deadline reminder for {saved_opp.id}: {e}")

    logger.info(f"Pipeline reminders completed: {custom_reminders_sent} custom, {deadline_reminders_sent} deadline warnings")


def ai_summarization_job():
    """
    AI summarization job for PDF attachments.

    Uses Claude to analyze extracted PDF text and generate structured summaries
    including:
    - What the government wants done
    - Clearance requirements
    - Technologies and labor categories
    - Estimated contract value

    Runs multiple times daily to ensure all new PDFs get summarized quickly.
    Processes up to 50 PDFs per run with rate limiting (3s between calls).
    """
    from app.services.ai_summarization import batch_summarize_attachments

    logger.info("Starting AI summarization job...")

    try:
        # Process up to 50 PDFs per run (with 3s delay = ~2.5 min per run)
        results = batch_summarize_attachments(limit=50, force=False)

        logger.info(
            f"AI summarization completed: {results['summarized']} summarized, "
            f"{results['failed']} failed, {results['skipped']} skipped"
        )

        if results['errors']:
            for err in results['errors'][:5]:
                logger.warning(f"Summarization error for {err['name']}: {err['error']}")

    except Exception as e:
        logger.error(f"AI summarization job failed: {e}")


def scraper_sync_job(naics_code: str = "541511", max_results: int = 1000, biddable_only: bool = True):
    """
    Sync opportunities using the internal SAM.gov API scraper.

    This job bypasses the rate-limited public API by using SAM.gov's internal
    APIs (the same ones the website uses). Benefits:
    - No rate limits (just be respectful with delays)
    - Complete data: NAICS, set-aside, place of performance
    - Full attachment metadata included
    - Duplicate prevention via notice_id upsert
    - No duplicate AI processing (skips existing attachments)
    - Only syncs biddable opportunities (not expired, not awarded)

    Runs twice daily at 3 AM and 3 PM UTC.

    Args:
        naics_code: NAICS code to sync (default: 541511 Custom Programming)
        max_results: Maximum opportunities to fetch
        biddable_only: If True, only sync opportunities that are biddable
                       (Solicitation, Presolicitation, Combined, Sources Sought with future deadline)
    """
    from app.services.sam_scraper import sync_opportunities_with_full_details

    logger.info(f"Starting SAM.gov scraper sync: NAICS {naics_code}, max {max_results}, biddable_only={biddable_only}")

    try:
        stats = sync_opportunities_with_full_details(
            naics_code=naics_code,
            max_results=max_results,
            biddable_only=biddable_only,
        )

        logger.info(
            f"Scraper sync completed for NAICS {naics_code}: "
            f"{stats['opportunities_created']} created, {stats['opportunities_updated']} updated, "
            f"{stats['attachments_created']} new attachments, "
            f"{stats.get('skipped_not_biddable', 0)} skipped (not biddable)"
        )

        return stats

    except Exception as e:
        logger.error(f"Scraper sync job failed: {e}")
        return {"error": str(e)}


def _parse_date(date_str):
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


def _parse_datetime(dt_str):
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


def start_scheduler():
    """
    Start the background scheduler with all jobs configured.

    Schedule:
    - 4:30 AM UTC: Archive expired opportunities (preserve for history)
    - 5:00 AM UTC: Archive expired recompetes (preserve for history)
    - 6:00 AM UTC: Sync USAspending awards and recompetes
    - 7:00 AM UTC: Sync SAM.gov opportunities with attachments
    - 7:30 AM UTC: Backfill attachments via internal SAM.gov API
    - 8:00 AM UTC: Extract PDF text for keyword search
    - 9:00 AM UTC: Send pipeline reminder emails
    - On startup: Run PDF extraction for any pending PDFs
    """
    if scheduler.running:
        logger.info("Scheduler already running")
        return

    # Archive expired opportunities daily at 4:30 AM UTC
    scheduler.add_job(
        archive_expired_opportunities_job,
        CronTrigger(hour=4, minute=30),
        id="archive_expired_opportunities",
        replace_existing=True,
        name="Archive expired opportunities",
    )

    # Archive expired recompetes daily at 5 AM UTC
    scheduler.add_job(
        cleanup_expired_recompetes_job,
        CronTrigger(hour=5, minute=0),
        id="cleanup_expired_recompetes",
        replace_existing=True,
        name="Archive expired recompetes",
    )

    # Sync USAspending daily at 6 AM UTC
    scheduler.add_job(
        sync_usaspending_job,
        CronTrigger(hour=6, minute=0),
        id="sync_usaspending",
        replace_existing=True,
        name="Sync USAspending awards",
    )

    # Sync SAM.gov 5 times daily, rotating through NAICS codes
    # Spread across the day to stay within rate limits (~10 requests/day for non-federal keys)
    # Each run syncs ONE NAICS code to minimize API calls
    sam_gov_schedule = [
        (1, 0, 0),   # 1 AM UTC - NAICS 541511 (Custom Programming)
        (5, 0, 1),   # 5 AM UTC - NAICS 541512 (Systems Design)
        (9, 0, 2),   # 9 AM UTC - NAICS 541519 (Other Computer)
        (13, 0, 3),  # 1 PM UTC - NAICS 518210 (Data Processing)
        (17, 0, 4),  # 5 PM UTC - NAICS 541690 (Technical Consulting)
    ]

    for hour, minute, naics_idx in sam_gov_schedule:
        scheduler.add_job(
            sync_sam_gov_job,
            CronTrigger(hour=hour, minute=minute),
            id=f"sync_sam_gov_{naics_idx}",
            replace_existing=True,
            name=f"Sync SAM.gov opportunities (NAICS {naics_idx})",
            kwargs={"naics_index": naics_idx},
        )

    # Backfill attachments at 7:30 AM UTC (after main sync, uses internal SAM.gov API)
    scheduler.add_job(
        backfill_attachments_job,
        CronTrigger(hour=7, minute=30),
        id="backfill_attachments",
        replace_existing=True,
        name="Backfill attachments (internal API)",
    )

    # Extract PDF text daily at 8 AM UTC (after attachments are synced)
    scheduler.add_job(
        extract_pdf_text_job,
        CronTrigger(hour=8, minute=0),
        id="extract_pdf_text",
        replace_existing=True,
        name="Extract PDF text for search",
    )

    # Also run PDF extraction once on startup (30 seconds after start)
    # This catches any pending PDFs from previous runs
    scheduler.add_job(
        extract_pdf_text_job,
        "date",
        run_date=datetime.utcnow() + timedelta(seconds=30),
        id="extract_pdf_text_startup",
        replace_existing=True,
        name="Extract PDF text (startup)",
    )

    # Send pipeline reminders daily at 9 AM UTC
    scheduler.add_job(
        send_pipeline_reminders_job,
        CronTrigger(hour=9, minute=0),
        id="send_pipeline_reminders",
        replace_existing=True,
        name="Send pipeline reminder emails",
    )

    # AI summarization runs every 4 hours to keep summaries up-to-date
    # This ensures new opportunities get summarized quickly
    scheduler.add_job(
        ai_summarization_job,
        CronTrigger(hour="0,4,8,12,16,20", minute=30),
        id="ai_summarization",
        replace_existing=True,
        name="AI summarize PDF attachments",
    )

    # Also run AI summarization on startup (60 seconds after start, after PDF extraction)
    # This catches any PDFs that were extracted but not yet summarized
    scheduler.add_job(
        ai_summarization_job,
        "date",
        run_date=datetime.utcnow() + timedelta(seconds=60),
        id="ai_summarization_startup",
        replace_existing=True,
        name="AI summarize PDFs (startup)",
    )

    # SAM.gov scraper sync - runs for each NAICS code
    # Uses internal SAM.gov API (no rate limits) with full details
    # Syncs 541511 (Custom Programming) twice daily, others once daily

    # Primary NAICS: 541511 - Custom Computer Programming (most important)
    scheduler.add_job(
        scraper_sync_job,
        CronTrigger(hour="3,15", minute=0),
        id="scraper_sync_541511",
        replace_existing=True,
        name="SAM.gov scraper: 541511 (Custom Programming)",
        kwargs={"naics_code": "541511", "max_results": 500},
    )

    # Secondary NAICS codes - once daily at different hours
    secondary_naics = [
        ("541512", 4),   # Computer Systems Design - 4 AM
        ("541519", 6),   # Other Computer Related - 6 AM
        ("518210", 10),  # Data Processing/Hosting - 10 AM
        ("541690", 14),  # Scientific/Technical Consulting - 2 PM
    ]

    for naics_code, hour in secondary_naics:
        scheduler.add_job(
            scraper_sync_job,
            CronTrigger(hour=hour, minute=0),
            id=f"scraper_sync_{naics_code}",
            replace_existing=True,
            name=f"SAM.gov scraper: {naics_code}",
            kwargs={"naics_code": naics_code, "max_results": 200},
        )

    # Run 541511 sync on startup (90 seconds after start)
    scheduler.add_job(
        scraper_sync_job,
        "date",
        run_date=datetime.utcnow() + timedelta(seconds=90),
        id="scraper_sync_startup",
        replace_existing=True,
        name="SAM.gov scraper: 541511 (startup)",
        kwargs={"naics_code": "541511", "max_results": 100},
    )

    scheduler.start()
    logger.info("Scheduler started with jobs:")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name}: {job.trigger}")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def get_scheduler_status():
    """Get current scheduler status and job info."""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })

    return {
        "running": scheduler.running,
        "jobs": jobs,
    }
