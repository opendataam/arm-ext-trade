"""Small polite HTTP client with retries and rate limiting."""

from __future__ import annotations

import logging
import time

import requests

from . import config

log = logging.getLogger(__name__)


class Client:
    """Wrapper around ``requests.Session``.

    A new ``Client`` keeps its own cookie jar; the web database export
    (``/excelopen.php``) relies on the PHP session cookie set by the query page.
    """

    def __init__(self, delay: float = config.HTTP_DELAY) -> None:
        self.session = requests.Session()
        self.session.headers["User-Agent"] = config.USER_AGENT
        self.delay = delay
        self._last = 0.0

    def reset(self) -> None:
        """Drop cookies (start a fresh PHP session)."""
        self.session.cookies.clear()

    def get(self, url: str, referer: str | None = None, no_delay: bool = False, **kw) -> requests.Response:
        """GET with retries. ``no_delay`` skips the politeness pause (used for the
        export request that must follow its query immediately)."""
        headers = {"Referer": referer} if referer else {}
        last_exc: Exception | None = None
        for attempt in range(1, config.HTTP_RETRIES + 1):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0 and not (no_delay and attempt == 1):
                time.sleep(wait)
            try:
                r = self.session.get(url, headers=headers, timeout=config.HTTP_TIMEOUT, **kw)
                self._last = time.monotonic()
                if r.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
                r.raise_for_status()
                return r
            except requests.RequestException as exc:  # network error or 5xx
                last_exc = exc
                self._last = time.monotonic()
                backoff = 5 * attempt
                log.warning("GET %s failed (%s), retry %d in %ds", url, exc, attempt, backoff)
                time.sleep(backoff)
        raise RuntimeError(f"GET {url} failed after {config.HTTP_RETRIES} attempts") from last_exc
