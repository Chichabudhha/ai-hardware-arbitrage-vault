"""Watched listings that are not purchase candidates.

A paper prediction answers "should we buy this". Plenty of listings are worth
following without that question ever being asked: an Austrian card at 499 EUR
tells us nothing about buying, but everything about whether 499 EUR is a price
this market actually pays. If it sells, the median holds; if it sits for weeks
or the seller cuts, the median was wishful.

So a watch item is deliberately thin: what was listed, where, at what asking
price, and when we first saw it. No verdict, no costs, no scoring — those would
imply a trade decision that was never made.

Outcomes are shared with predictions: the same `outcome` command records SOLD /
PRICE_CUT / UNSOLD / DELISTED against either kind of subject.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from src.core.models import PriceObservation

DEFAULT_WATCHLIST = Path("data/paper/watchlist.jsonl")


class WatchlistError(ValueError):
    """A stored watch item could not be read as written."""


def watch_id(marketplace: str, source_listing_id: str) -> str:
    """Stable id, readable and greppable.

    No timestamp, unlike a prediction id: a listing is watched once, and seeing
    it again is an observation about the same subject rather than a new one.
    """
    return f"watch:{marketplace}:{source_listing_id}"


class WatchItem(BaseModel):
    """One listing being followed for its price signal."""

    model_config = ConfigDict(frozen=True)

    watch_id: str
    marketplace: str
    source_listing_id: str
    product_id: str
    url: str | None = None
    asking_amount: Decimal
    asking_currency: str
    first_seen_at: datetime
    reason: str = "price_signal"


def from_observation(observation: PriceObservation, reason: str = "price_signal") -> WatchItem:
    """Follow a listing we already recorded a price for."""
    return WatchItem(
        watch_id=watch_id(observation.marketplace, observation.source_listing_id),
        marketplace=observation.marketplace,
        source_listing_id=observation.source_listing_id,
        product_id=observation.product_id,
        url=observation.url,
        asking_amount=observation.price_amount,
        asking_currency=observation.currency,
        first_seen_at=observation.observed_at,
        reason=reason,
    )


def load_watchlist(path: str | Path | None = None) -> list[WatchItem]:
    """Read the watchlist. A malformed line is an error, never a skipped row."""
    store = Path(DEFAULT_WATCHLIST if path is None else path)
    if not store.exists():
        return []

    items: list[WatchItem] = []
    for line_no, raw in enumerate(store.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            items.append(WatchItem.model_validate_json(raw))
        except ValidationError as exc:
            raise WatchlistError(f"{store}:{line_no} is not a usable watch item: {exc}") from exc
    return items


def append_watch_items(
    items: list[WatchItem], path: str | Path | None = None
) -> list[WatchItem]:
    """Append the items that are not on the list yet; return those actually added.

    Re-adding a listing is a no-op rather than a duplicate line: the watchlist
    answers "what am I still checking", and the same listing seen twice is one
    subject, not two.
    """
    store = Path(DEFAULT_WATCHLIST if path is None else path)
    known = {item.watch_id for item in load_watchlist(store)}
    fresh = [item for item in items if item.watch_id not in known]
    if not fresh:
        return []

    store.parent.mkdir(parents=True, exist_ok=True)
    with store.open("a", encoding="utf-8") as handle:
        for item in fresh:
            handle.write(item.model_dump_json() + "\n")
    return fresh
