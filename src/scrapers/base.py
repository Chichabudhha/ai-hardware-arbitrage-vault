"""Connector contract from MARKETPLACE-STRATEGY.md.

Every connector exposes search / get_listing / normalize_raw / health_check and
supports pagination, backoff, rate limits, timeouts, dedup, source IDs, observed
timestamps and raw payload retention.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.core.models import AutomationStatus, Listing, RawObservation
from src.scrapers.compliance import (
    UNVERIFIED,
    AccessVerification,
    assert_fetch_allowed,
    robots_allows,
)
from src.scrapers.http_client import RateLimitedClient


@dataclass(frozen=True)
class ConnectorAccess:
    """Static access description of one marketplace."""

    marketplace: str
    country: str
    base_url: str
    automation_status: AutomationStatus = AutomationStatus.RESEARCH
    verification: AccessVerification = UNVERIFIED
    min_interval_seconds: float = 5.0


@dataclass
class SearchFilters:
    """Source-agnostic filters; each connector maps them to its own query shape."""

    query: str
    min_price: int | None = None
    max_price: int | None = None
    page: int = 1
    extra: dict[str, str] = field(default_factory=dict)


def payload_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class BaseConnector(ABC):
    """Transport + normalization for one marketplace. No pricing, no LLM."""

    access: ConnectorAccess

    def __init__(self, client: RateLimitedClient | None = None) -> None:
        self.client = client or RateLimitedClient(
            min_interval_seconds=self.access.min_interval_seconds
        )

    # --- contract -------------------------------------------------------

    @abstractmethod
    def search(self, filters: SearchFilters) -> list[RawObservation]:
        """Return raw observations for one result page."""

    @abstractmethod
    def get_listing(self, listing_id: str) -> RawObservation:
        """Return the raw observation for a single listing."""

    @abstractmethod
    def normalize_raw(self, observation: RawObservation) -> Listing:
        """Structure extraction only — never interpretation."""

    def health_check(self) -> dict[str, object]:
        """Report whether this connector may run automated at all."""
        verification = self.access.verification
        return {
            "marketplace": self.access.marketplace,
            "automation_status": self.access.automation_status.value,
            "access_verified": verification.is_verified,
            "terms_url": verification.terms_url,
            "verified_on": verification.verified_on.isoformat()
            if verification.verified_on
            else None,
            "notes": verification.notes,
        }

    # --- shared fetch path ----------------------------------------------

    def fetch(self, url: str) -> str:
        """Fetch a URL only if the compliance gate and robots.txt both allow it."""
        assert_fetch_allowed(
            self.access.marketplace,
            self.access.automation_status,
            self.access.verification,
        )
        if not robots_allows(url, self.client.user_agent):
            raise PermissionError(f"robots.txt disallows {url} for {self.client.user_agent}")
        return self.client.get_text(url)

    def observe(self, url: str, listing_id: str, payload: str) -> RawObservation:
        """Wrap a payload as an immutable observation."""
        return RawObservation(
            marketplace=self.access.marketplace,
            source_listing_id=listing_id,
            url=url,
            fetched_at=now_utc(),
            payload=payload,
            payload_hash=payload_hash(payload),
            access_method=self.access.automation_status,
        )
