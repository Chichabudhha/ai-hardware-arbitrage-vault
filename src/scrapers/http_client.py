"""Polite HTTP client: fixed identifying user-agent, rate limit, backoff, timeout.

No proxy rotation and no user-agent randomization by design — CLAUDE.md principle 7
forbids evading rate limits or access controls. The client slows down on 429/5xx
instead of routing around them.
"""

from __future__ import annotations

import os
import random
import time

import httpx

DEFAULT_USER_AGENT = os.getenv(
    "ARBITRAGE_USER_AGENT", "ai-hardware-arbitrage/0.1 (contact: set ARBITRAGE_USER_AGENT)"
)


class RateLimitedClient:
    """Single-threaded client enforcing a minimum interval between requests."""

    def __init__(
        self,
        min_interval_seconds: float = 5.0,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        user_agent: str = DEFAULT_USER_AGENT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.min_interval_seconds = min_interval_seconds
        self.max_retries = max_retries
        self.user_agent = user_agent
        self._last_request_at = 0.0
        self._client = httpx.Client(
            timeout=timeout_seconds,
            headers={"User-Agent": user_agent, "Accept-Language": "sr,de,en"},
            follow_redirects=True,
            transport=transport,
        )

    def get_text(self, url: str) -> str:
        self._throttle()
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = self._client.get(url)
            except httpx.RequestError as exc:
                last_error = exc
                self._backoff(attempt)
                continue

            if response.status_code == 429 or response.status_code >= 500:
                self._backoff(attempt, retry_after=response.headers.get("Retry-After"))
                last_error = httpx.HTTPStatusError(
                    f"{response.status_code} from {url}",
                    request=response.request,
                    response=response,
                )
                continue

            response.raise_for_status()
            return response.text

        raise RuntimeError(f"GET failed after {self.max_retries} attempts: {url}") from last_error

    def close(self) -> None:
        self._client.close()

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)
        self._last_request_at = time.monotonic()

    def _backoff(self, attempt: int, retry_after: str | None = None) -> None:
        if retry_after and retry_after.isdigit():
            time.sleep(int(retry_after))
            return
        time.sleep((2**attempt) + random.uniform(0, 1))
