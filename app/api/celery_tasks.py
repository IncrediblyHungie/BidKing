"""
Celery task management API endpoints.

Provides endpoints for:
- Triggering test tasks
- Triggering sync tasks (SAM.gov, USAspending)
- Checking task status
- Managing workers
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from worker.celery_app import celery_app

router = APIRouter()


class TaskResponse(BaseModel):
    """Response for task creation."""
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    """Response for task status check."""
    task_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None
    progress: Optional[int] = None
    current: Optional[int] = None
    total: Optional[int] = None


# =============================================================================
# Test Task Endpoints
# =============================================================================

@router.post("/test/ping", response_model=TaskResponse)
async def trigger_ping():
    """
    Trigger a simple ping task to verify Celery is working.

    Returns immediately with task ID. Use /tasks/{task_id}/status to check result.
    """
    from worker.tasks import ping

    result = ping.delay()
    return TaskResponse(
        task_id=result.id,
        status="queued",
        message="Ping task queued",
    )


@router.post("/test/slow/{duration}", response_model=TaskResponse)
async def trigger_slow_task(duration: int):
    """
    Trigger a slow task that takes `duration` seconds to complete.

    Useful for testing async behavior and progress tracking.
    """
    from worker.tasks import slow_task

    if duration < 1 or duration > 60:
        raise HTTPException(status_code=400, detail="Duration must be between 1 and 60 seconds")

    result = slow_task.delay(duration)
    return TaskResponse(
        task_id=result.id,
        status="queued",
        message=f"Slow task ({duration}s) queued",
    )


@router.post("/test/add/{x}/{y}", response_model=TaskResponse)
async def trigger_add(x: int, y: int):
    """
    Trigger a simple addition task.

    Demonstrates passing arguments to Celery tasks.
    """
    from worker.tasks import add

    result = add.delay(x, y)
    return TaskResponse(
        task_id=result.id,
        status="queued",
        message=f"Add task ({x} + {y}) queued",
    )


# =============================================================================
# SAM.gov Sync Endpoints
# =============================================================================

@router.post("/sync/sam/all", response_model=TaskResponse)
async def trigger_sam_sync_all(
    days_back: int = Query(7, ge=1, le=90, description="Days to look back"),
):
    """
    Trigger sync for all configured NAICS codes from SAM.gov.

    This queues individual tasks for each NAICS code which run in parallel.
    """
    from worker.tasks import sync_all_opportunities

    result = sync_all_opportunities.delay(days_back)
    return TaskResponse(
        task_id=result.id,
        status="queued",
        message=f"SAM.gov sync for all NAICS codes queued (days_back={days_back})",
    )


@router.post("/sync/sam/naics/{naics_code}", response_model=TaskResponse)
async def trigger_sam_sync_naics(
    naics_code: str,
    days_back: int = Query(7, ge=1, le=90, description="Days to look back"),
):
    """
    Trigger sync for a specific NAICS code from SAM.gov.
    """
    from worker.tasks import sync_opportunities_by_naics

    result = sync_opportunities_by_naics.delay(naics_code, days_back)
    return TaskResponse(
        task_id=result.id,
        status="queued",
        message=f"SAM.gov sync for NAICS {naics_code} queued (days_back={days_back})",
    )


# =============================================================================
# USAspending Sync Endpoints
# =============================================================================

@router.post("/sync/usaspending", response_model=TaskResponse)
async def trigger_usaspending_sync(
    days_back: int = Query(30, ge=1, le=365, description="Days to look back"),
):
    """
    Trigger sync of recent contract awards from USAspending.
    """
    from worker.tasks import sync_recent_awards

    result = sync_recent_awards.delay(days_back)
    return TaskResponse(
        task_id=result.id,
        status="queued",
        message=f"USAspending sync queued (days_back={days_back})",
    )


@router.post("/sync/naics-stats", response_model=TaskResponse)
async def trigger_naics_stats_update():
    """
    Trigger update of NAICS code statistics.
    """
    from worker.tasks import update_naics_statistics

    result = update_naics_statistics.delay()
    return TaskResponse(
        task_id=result.id,
        status="queued",
        message="NAICS statistics update queued",
    )


# =============================================================================
# Alert Processing Endpoints
# =============================================================================

@router.post("/alerts/process", response_model=TaskResponse)
async def trigger_alert_processing():
    """
    Trigger processing of realtime alerts for new opportunities.
    """
    from worker.tasks import process_realtime_alerts

    result = process_realtime_alerts.delay()
    return TaskResponse(
        task_id=result.id,
        status="queued",
        message="Realtime alert processing queued",
    )


@router.post("/alerts/daily-digest", response_model=TaskResponse)
async def trigger_daily_digest():
    """
    Trigger sending of daily digest emails.
    """
    from worker.tasks import send_daily_digests

    result = send_daily_digests.delay()
    return TaskResponse(
        task_id=result.id,
        status="queued",
        message="Daily digest sending queued",
    )


# =============================================================================
# Cleanup Endpoints
# =============================================================================

@router.post("/cleanup/archived", response_model=TaskResponse)
async def trigger_cleanup_archived():
    """
    Trigger cleanup of archived opportunities.
    """
    from worker.tasks import cleanup_archived_opportunities

    result = cleanup_archived_opportunities.delay()
    return TaskResponse(
        task_id=result.id,
        status="queued",
        message="Archived opportunity cleanup queued",
    )


@router.post("/cleanup/cache", response_model=TaskResponse)
async def trigger_cleanup_cache():
    """
    Trigger cleanup of expired cache entries.
    """
    from worker.tasks import cleanup_expired_cache

    result = cleanup_expired_cache.delay()
    return TaskResponse(
        task_id=result.id,
        status="queued",
        message="Cache cleanup queued",
    )


# =============================================================================
# Task Management Endpoints
# =============================================================================

@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Check the status of a Celery task.

    Status values:
    - PENDING: Task is waiting to be executed
    - STARTED: Task has started
    - PROGRESS: Task is in progress (custom state)
    - SUCCESS: Task completed successfully
    - FAILURE: Task failed
    - RETRY: Task is being retried
    - REVOKED: Task was cancelled
    """
    result = celery_app.AsyncResult(task_id)

    response = TaskStatusResponse(
        task_id=task_id,
        status=result.status,
    )

    if result.status == "SUCCESS":
        response.result = result.result if isinstance(result.result, dict) else {"value": result.result}
    elif result.status == "FAILURE":
        response.error = str(result.result) if result.result else "Unknown error"
    elif result.status == "PROGRESS":
        info = result.info or {}
        response.progress = info.get("percent", 0)
        response.current = info.get("current", 0)
        response.total = info.get("total", 0)

    return response


@router.delete("/tasks/{task_id}")
async def revoke_task(task_id: str, terminate: bool = False):
    """
    Revoke (cancel) a pending or running task.

    Args:
        task_id: The task ID to revoke
        terminate: If True, forcefully terminate running task (use with caution)
    """
    celery_app.control.revoke(task_id, terminate=terminate)
    return {
        "status": "revoked",
        "task_id": task_id,
        "terminated": terminate,
    }


# =============================================================================
# Worker Management Endpoints
# =============================================================================

@router.get("/workers/status")
async def get_worker_status():
    """
    Get status of all connected Celery workers.

    Returns information about connected workers, their queues, and task stats.
    """
    try:
        # Inspect workers
        inspect = celery_app.control.inspect()

        # Get active workers
        active = inspect.active() or {}
        stats = inspect.stats() or {}
        registered = inspect.registered() or {}

        workers = []
        for name, worker_stats in stats.items():
            workers.append({
                "name": name,
                "active_tasks": len(active.get(name, [])),
                "registered_tasks": len(registered.get(name, [])),
                "pool": worker_stats.get("pool", {}).get("max-concurrency", 0),
                "uptime": str(worker_stats.get("clock", 0)),
            })

        return {
            "status": "connected" if workers else "no_workers",
            "worker_count": len(workers),
            "workers": workers,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@router.get("/redis/health")
async def check_redis_health():
    """
    Check if Redis is accessible.

    This is useful for debugging connection issues.
    """
    import redis
    from app.config import settings

    try:
        redis_url = settings.redis_url
        if redis_url.startswith("rediss://"):
            # TLS connection
            client = redis.from_url(redis_url, ssl_cert_reqs=None)
        else:
            client = redis.from_url(redis_url)

        info = client.info()
        return {
            "status": "healthy",
            "redis_version": info.get("redis_version", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "used_memory": info.get("used_memory_human", "unknown"),
            "url": redis_url.split("@")[-1].split("?")[0] if "@" in redis_url else "localhost",
            "env_url_set": bool(settings.redis_url),
            "config_url_prefix": redis_url[:30] + "..." if len(redis_url) > 30 else redis_url,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


# =============================================================================
# Scheduled Tasks Info
# =============================================================================

@router.get("/schedule")
async def get_scheduled_tasks():
    """
    Get the configured beat schedule (periodic tasks).
    """
    schedule = celery_app.conf.beat_schedule or {}

    tasks = []
    for name, config in schedule.items():
        tasks.append({
            "name": name,
            "task": config.get("task"),
            "schedule": str(config.get("schedule")),
            "queue": config.get("options", {}).get("queue", "default"),
        })

    return {
        "scheduled_tasks": tasks,
        "total": len(tasks),
    }
