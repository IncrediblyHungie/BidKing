"""
Test tasks for verifying Celery + Redis integration.
"""

import logging
import time
from datetime import datetime

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def ping(self):
    """
    Simple ping task to verify Celery is working.
    Returns immediately with task info.
    """
    return {
        "status": "pong",
        "task_id": self.request.id,
        "timestamp": datetime.utcnow().isoformat(),
        "worker": self.request.hostname,
    }


@shared_task(bind=True)
def slow_task(self, duration: int = 5):
    """
    Simulates a slow task for testing async behavior.

    Args:
        duration: How long to sleep in seconds (default 5)
    """
    logger.info(f"Starting slow task, will take {duration} seconds")

    for i in range(duration):
        time.sleep(1)
        # Update task state with progress
        self.update_state(
            state='PROGRESS',
            meta={'current': i + 1, 'total': duration}
        )
        logger.info(f"Slow task progress: {i + 1}/{duration}")

    return {
        "status": "completed",
        "task_id": self.request.id,
        "duration": duration,
        "completed_at": datetime.utcnow().isoformat(),
    }


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def retry_test(self, should_fail: bool = True):
    """
    Task that demonstrates retry behavior.

    Args:
        should_fail: If True, fails on first attempt then succeeds
    """
    attempt = self.request.retries + 1
    logger.info(f"Retry test task attempt {attempt}")

    if should_fail and attempt == 1:
        logger.warning("Simulating failure on first attempt")
        raise self.retry(exc=Exception("Simulated failure"))

    return {
        "status": "success",
        "task_id": self.request.id,
        "attempts": attempt,
        "completed_at": datetime.utcnow().isoformat(),
    }


@shared_task
def add(x: int, y: int) -> int:
    """Simple add task for basic testing."""
    return x + y
