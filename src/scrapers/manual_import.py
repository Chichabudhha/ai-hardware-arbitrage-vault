"""MANUAL import path — the only acquisition method usable before verification.

The owner saves a listing page (or copies its HTML) into a local file; this module
turns it into a RawObservation and hands it to the matching connector's
normalize_raw(). No network access, so no ToS surface at all.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.core.models import AutomationStatus, Listing, RawObservation
from src.scrapers.base import payload_hash
from src.scrapers.registry import get_connector


def observation_from_file(
    path: str | Path,
    marketplace: str,
    source_listing_id: str,
    url: str,
    fetched_at: datetime | None = None,
) -> RawObservation:
    """Build an observation from a manually saved HTML file."""
    file_path = Path(path)
    payload = file_path.read_text(encoding="utf-8", errors="replace")
    return RawObservation(
        marketplace=marketplace,
        source_listing_id=source_listing_id,
        url=url,
        fetched_at=fetched_at
        or datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc),
        payload=payload,
        payload_hash=payload_hash(payload),
        access_method=AutomationStatus.MANUAL,
    )


def import_file(
    path: str | Path,
    marketplace: str,
    source_listing_id: str,
    url: str,
) -> Listing:
    """Manual file → normalized Listing using the marketplace's own parser."""
    observation = observation_from_file(path, marketplace, source_listing_id, url)
    connector = get_connector(marketplace)
    return connector.normalize_raw(observation)
