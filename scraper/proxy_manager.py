"""
Proxy Manager for Webshare Residential Proxies

Handles:
- Loading 215K+ proxies from file
- Rotating proxies on each request
- Marking failed proxies and removing them temporarily
- Health checking and proxy validation
"""

import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List
from collections import deque
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProxyStats:
    """Track proxy performance"""
    successes: int = 0
    failures: int = 0
    last_used: float = 0
    last_failure: float = 0
    consecutive_failures: int = 0


@dataclass
class Proxy:
    """Represents a single proxy configuration"""
    host: str
    port: int
    username: str
    password: str
    stats: ProxyStats = field(default_factory=ProxyStats)

    @property
    def url(self) -> str:
        """HTTP proxy URL format"""
        return f"http://{self.username}:{self.password}@{self.host}:{self.port}"

    @property
    def httpx_proxy(self) -> str:
        """Format for httpx client"""
        return self.url

    @property
    def playwright_proxy(self) -> Dict:
        """Format for Playwright browser"""
        return {
            "server": f"http://{self.host}:{self.port}",
            "username": self.username,
            "password": self.password,
        }

    def __hash__(self):
        return hash((self.host, self.port, self.username))


class ProxyManager:
    """
    Manages a pool of residential proxies with rotation and health tracking.

    Features:
    - Round-robin rotation through proxies
    - Automatic removal of failing proxies
    - Cooldown period for failed proxies
    - Thread-safe operations
    """

    def __init__(
        self,
        proxy_file: str,
        max_consecutive_failures: int = 3,
        failure_cooldown_seconds: int = 300,  # 5 minutes
        shuffle: bool = True,
        never_remove: bool = False,  # For Bright Data single-endpoint proxies
    ):
        self.proxy_file = Path(proxy_file)
        self.max_consecutive_failures = max_consecutive_failures
        self.failure_cooldown = failure_cooldown_seconds
        self.shuffle = shuffle
        self.never_remove = never_remove

        self._lock = threading.Lock()
        self._proxies: List[Proxy] = []
        self._proxy_queue: deque = deque()
        self._failed_proxies: Dict[Proxy, float] = {}  # proxy -> failure time

        self._load_proxies()

    def _load_proxies(self):
        """Load proxies from file"""
        if not self.proxy_file.exists():
            raise FileNotFoundError(f"Proxy file not found: {self.proxy_file}")

        proxies = []
        with open(self.proxy_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                try:
                    # Format: host:port:username:password
                    parts = line.split(':')
                    if len(parts) >= 4:
                        proxy = Proxy(
                            host=parts[0],
                            port=int(parts[1]),
                            username=parts[2],
                            password=parts[3],
                        )
                        proxies.append(proxy)
                except (ValueError, IndexError) as e:
                    logger.warning(f"Invalid proxy line: {line[:50]}... - {e}")

        if self.shuffle:
            random.shuffle(proxies)

        self._proxies = proxies
        self._proxy_queue = deque(proxies)

        logger.info(f"Loaded {len(self._proxies):,} proxies from {self.proxy_file}")

    def get_proxy(self) -> Optional[Proxy]:
        """
        Get the next available proxy using round-robin rotation.

        Returns None if no proxies are available.
        """
        with self._lock:
            # First, restore any proxies that have cooled down
            self._restore_cooled_proxies()

            if not self._proxy_queue:
                logger.warning("No proxies available!")
                return None

            # Get next proxy from queue
            proxy = self._proxy_queue.popleft()

            # Put it back at the end for rotation
            self._proxy_queue.append(proxy)

            proxy.stats.last_used = time.time()
            return proxy

    def mark_success(self, proxy: Proxy):
        """Mark a proxy as successfully used"""
        with self._lock:
            proxy.stats.successes += 1
            proxy.stats.consecutive_failures = 0

    def mark_failure(self, proxy: Proxy, remove_on_max_failures: bool = True):
        """
        Mark a proxy as failed.

        If consecutive failures exceed threshold, remove from active pool.
        """
        with self._lock:
            proxy.stats.failures += 1
            proxy.stats.consecutive_failures += 1
            proxy.stats.last_failure = time.time()

            if remove_on_max_failures and proxy.stats.consecutive_failures >= self.max_consecutive_failures:
                # Don't remove if never_remove is set (for Bright Data single-endpoint proxies)
                if self.never_remove:
                    logger.debug(f"Proxy {proxy.host} has {proxy.stats.consecutive_failures} failures but never_remove is set")
                    proxy.stats.consecutive_failures = 0  # Reset counter
                else:
                    # Remove from active queue
                    try:
                        self._proxy_queue.remove(proxy)
                        self._failed_proxies[proxy] = time.time()
                        logger.info(
                            f"Proxy {proxy.host} removed after {proxy.stats.consecutive_failures} failures. "
                            f"Will retry in {self.failure_cooldown}s"
                        )
                    except ValueError:
                        pass  # Already removed

    def _restore_cooled_proxies(self):
        """Restore proxies that have passed their cooldown period"""
        now = time.time()
        restored = []

        for proxy, failure_time in list(self._failed_proxies.items()):
            if now - failure_time >= self.failure_cooldown:
                proxy.stats.consecutive_failures = 0
                self._proxy_queue.append(proxy)
                restored.append(proxy)

        for proxy in restored:
            del self._failed_proxies[proxy]
            logger.info(f"Proxy {proxy.host} restored to pool after cooldown")

    @property
    def active_count(self) -> int:
        """Number of proxies currently in rotation"""
        with self._lock:
            return len(self._proxy_queue)

    @property
    def total_count(self) -> int:
        """Total number of proxies loaded"""
        return len(self._proxies)

    @property
    def failed_count(self) -> int:
        """Number of proxies currently in cooldown"""
        with self._lock:
            return len(self._failed_proxies)

    def get_stats(self) -> Dict:
        """Get overall proxy pool statistics"""
        with self._lock:
            total_successes = sum(p.stats.successes for p in self._proxies)
            total_failures = sum(p.stats.failures for p in self._proxies)

            return {
                "total_proxies": self.total_count,
                "active_proxies": self.active_count,
                "failed_proxies": self.failed_count,
                "total_requests": total_successes + total_failures,
                "total_successes": total_successes,
                "total_failures": total_failures,
                "success_rate": total_successes / max(1, total_successes + total_failures) * 100,
            }


class ProxyRotator:
    """
    Higher-level proxy rotation with automatic retry logic.

    Usage:
        rotator = ProxyRotator(proxy_manager)

        async with rotator.get_client() as client:
            response = await client.get(url)
    """

    def __init__(self, proxy_manager: ProxyManager, max_retries: int = 3):
        self.proxy_manager = proxy_manager
        self.max_retries = max_retries

    def get_httpx_proxy(self) -> Optional[str]:
        """Get a proxy URL for httpx client"""
        proxy = self.proxy_manager.get_proxy()
        return proxy.url if proxy else None

    def get_playwright_proxy(self) -> Optional[Dict]:
        """Get proxy config for Playwright"""
        proxy = self.proxy_manager.get_proxy()
        return proxy.playwright_proxy if proxy else None


# Convenience function for quick setup
def create_proxy_manager(
    proxy_file: str = "/home/peteylinux/Projects/sam-mass-scraper/brightdata_proxy.txt",
    **kwargs
) -> ProxyManager:
    """Create a ProxyManager with default settings.

    Default: Uses Bright Data single rotating endpoint.
    For Bright Data, never_remove=True is set automatically.
    """
    # Detect Bright Data proxy file (single endpoint)
    if "brightdata" in proxy_file.lower() or "brd." in open(proxy_file).read(100).lower():
        kwargs.setdefault('never_remove', True)
        kwargs.setdefault('shuffle', False)  # No need to shuffle single proxy

    return ProxyManager(proxy_file, **kwargs)


if __name__ == "__main__":
    # Test the proxy manager
    logging.basicConfig(level=logging.INFO)

    manager = create_proxy_manager()
    print(f"\nProxy Manager Stats:")
    print(f"  Total proxies: {manager.total_count:,}")
    print(f"  Active proxies: {manager.active_count:,}")

    # Test getting a few proxies
    print(f"\nSample proxies:")
    for i in range(3):
        proxy = manager.get_proxy()
        if proxy:
            print(f"  {i+1}. {proxy.host}:{proxy.port} (user: {proxy.username[:10]}...)")
