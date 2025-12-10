"""
GSA CALC API synchronization tasks.

Fetches and caches labor rate data from CALC API.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
import statistics

from celery import shared_task
import httpx
from sqlalchemy.dialects.postgresql import insert

from app.database import SessionLocal
from app.models import LaborRateCache, CommonJobTitle
from app.utils.redis_client import Cache

logger = logging.getLogger(__name__)

# CALC API base URL
CALC_API_BASE = "https://calc.gsa.gov/api"

# Cache for labor rate queries
labor_rate_cache = Cache(key_prefix="labor_rates", default_ttl=86400)  # 24 hours


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_labor_rates(
    self,
    job_title: str,
    experience_min: Optional[int] = None,
    experience_max: Optional[int] = None,
    education_level: Optional[str] = None,
    force_refresh: bool = False,
):
    """
    Fetch labor rates from CALC API.

    Args:
        job_title: Job title to search for
        experience_min: Minimum years of experience
        experience_max: Maximum years of experience
        education_level: Education level filter
        force_refresh: Force refresh even if cached

    Returns:
        Labor rate statistics
    """
    logger.info(f"Fetching labor rates for: {job_title}")

    # Check cache first
    cache_key = f"{job_title}:{experience_min}:{experience_max}:{education_level}"
    if not force_refresh:
        cached = labor_rate_cache.get(cache_key)
        if cached:
            logger.info(f"Returning cached labor rates for {job_title}")
            return cached

    # Build query parameters
    params = {"q": job_title}

    if experience_min is not None:
        params["min_experience"] = experience_min
    if experience_max is not None:
        params["max_experience"] = experience_max
    if education_level:
        params["education"] = education_level

    try:
        with httpx.Client(timeout=30.0) as client:
            # Search for rates
            response = client.get(f"{CALC_API_BASE}/rates/", params=params)
            response.raise_for_status()
            data = response.json()

        results = data.get("results", [])

        if not results:
            return {
                "search_query": job_title,
                "match_count": 0,
                "message": "No matching labor rates found",
            }

        # Extract hourly rates
        rates = []
        categories = {}

        for item in results:
            # CALC returns min/max rates
            min_rate = item.get("min_years_experience")
            max_rate = item.get("max_years_experience")
            hourly = item.get("hourly_rate_year1")

            if hourly:
                rates.append(float(hourly))

                # Track by labor category
                category = item.get("labor_category", "Other")
                if category not in categories:
                    categories[category] = []
                categories[category].append(float(hourly))

        if not rates:
            return {
                "search_query": job_title,
                "match_count": len(results),
                "message": "No rate data available for matches",
            }

        # Calculate statistics
        sorted_rates = sorted(rates)
        result = {
            "search_query": job_title,
            "experience_range": f"{experience_min or 0}-{experience_max or 'any'} years" if experience_min or experience_max else None,
            "education_level": education_level,
            "match_count": len(results),
            "min_rate": min(rates),
            "max_rate": max(rates),
            "avg_rate": round(statistics.mean(rates), 2),
            "median_rate": round(statistics.median(rates), 2),
            "percentile_25": round(sorted_rates[len(sorted_rates) // 4], 2) if len(sorted_rates) >= 4 else sorted_rates[0],
            "percentile_75": round(sorted_rates[3 * len(sorted_rates) // 4], 2) if len(sorted_rates) >= 4 else sorted_rates[-1],
            "sample_categories": [
                {
                    "name": cat,
                    "count": len(cat_rates),
                    "avg_rate": round(statistics.mean(cat_rates), 2),
                }
                for cat, cat_rates in sorted(categories.items(), key=lambda x: len(x[1]), reverse=True)[:5]
            ],
            "cached_at": datetime.utcnow().isoformat(),
            "data_freshness": "live",
        }

        # Cache result
        labor_rate_cache.set(cache_key, result, ttl=86400)

        # Also store in database for persistence
        _save_to_database(result, experience_min, experience_max, education_level)

        return result

    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching labor rates: {e}")
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(f"Error fetching labor rates: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True)
def refresh_common_job_titles(self):
    """
    Refresh labor rate cache for common job titles.

    Pre-fetches rates for frequently searched job titles.
    """
    logger.info("Refreshing common job title rates")

    with SessionLocal() as db:
        titles = db.query(CommonJobTitle).filter(
            CommonJobTitle.is_active == True
        ).all()

        if not titles:
            # Use default titles if none configured
            default_titles = [
                "Software Developer",
                "Senior Software Engineer",
                "Data Analyst",
                "Business Analyst",
                "Project Manager",
                "Systems Administrator",
                "Cloud Architect",
                "DevOps Engineer",
                "Database Administrator",
                "Security Analyst",
                "Data Scientist",
                "Machine Learning Engineer",
                "ETL Developer",
                "BI Developer",
                "Solutions Architect",
            ]

            for title in default_titles:
                fetch_labor_rates.delay(
                    job_title=title,
                    force_refresh=True,
                )
        else:
            for title in titles:
                for search_term in title.calc_search_terms:
                    fetch_labor_rates.delay(
                        job_title=search_term,
                        experience_min=title.typical_experience_min,
                        experience_max=title.typical_experience_max,
                        education_level=title.typical_education,
                        force_refresh=True,
                    )

    return {"refreshed": len(titles) if titles else 15}


@shared_task(bind=True)
def compare_labor_rates(
    self,
    job_titles: list[str],
    experience_years: Optional[int] = None,
):
    """
    Compare labor rates across multiple job titles.

    Args:
        job_titles: List of job titles to compare
        experience_years: Years of experience for filtering

    Returns:
        Comparison data for all titles
    """
    results = []

    for title in job_titles[:10]:  # Limit to 10 titles
        try:
            rates = fetch_labor_rates(
                job_title=title,
                experience_min=experience_years - 2 if experience_years else None,
                experience_max=experience_years + 2 if experience_years else None,
            )
            if rates.get("match_count", 0) > 0:
                results.append({
                    "title": title,
                    "match_count": rates.get("match_count"),
                    "median_rate": rates.get("median_rate"),
                    "avg_rate": rates.get("avg_rate"),
                    "min_rate": rates.get("min_rate"),
                    "max_rate": rates.get("max_rate"),
                })
        except Exception as e:
            logger.error(f"Error fetching rates for {title}: {e}")
            continue

    # Sort by median rate
    results.sort(key=lambda x: x.get("median_rate", 0), reverse=True)

    return {
        "comparison": results,
        "experience_filter": f"{experience_years} years" if experience_years else "all levels",
        "generated_at": datetime.utcnow().isoformat(),
    }


def _save_to_database(
    result: dict,
    experience_min: Optional[int],
    experience_max: Optional[int],
    education_level: Optional[str],
):
    """Save labor rate result to database for persistence."""
    with SessionLocal() as db:
        record = {
            "search_query": result["search_query"],
            "experience_min": experience_min,
            "experience_max": experience_max,
            "education_level": education_level,
            "match_count": result.get("match_count", 0),
            "min_rate": Decimal(str(result.get("min_rate", 0))) if result.get("min_rate") else None,
            "max_rate": Decimal(str(result.get("max_rate", 0))) if result.get("max_rate") else None,
            "avg_rate": Decimal(str(result.get("avg_rate", 0))) if result.get("avg_rate") else None,
            "median_rate": Decimal(str(result.get("median_rate", 0))) if result.get("median_rate") else None,
            "percentile_25": Decimal(str(result.get("percentile_25", 0))) if result.get("percentile_25") else None,
            "percentile_75": Decimal(str(result.get("percentile_75", 0))) if result.get("percentile_75") else None,
            "sample_categories": result.get("sample_categories"),
            "cached_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=7),
        }

        stmt = insert(LaborRateCache).values(**record)
        stmt = stmt.on_conflict_do_update(
            constraint="labor_rate_cache_search_query_experience_min_experience_max__key",
            set_=record,
        )

        try:
            db.execute(stmt)
            db.commit()
        except Exception as e:
            logger.error(f"Error saving labor rate to database: {e}")
            db.rollback()
