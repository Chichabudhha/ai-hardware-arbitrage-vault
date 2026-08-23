"""Watched listings: subjects followed for their price signal, not for buying."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.core.models import Condition, PriceObservation, PriceType
from src.paper.watchlist import (
    WatchlistError,
    append_watch_items,
    from_observation,
    load_watchlist,
    watch_id,
)

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


def observation(listing_id: str = "1900028284", price: str = "499") -> PriceObservation:
    return PriceObservation(
        product_id="rtx-3080-ti",
        price_amount=Decimal(price),
        currency="EUR",
        price_type=PriceType.ASKING,
        condition=Condition.USED,
        observed_at=NOW,
        marketplace="willhaben",
        source_listing_id=listing_id,
        url=f"https://www.willhaben.at/iad/{listing_id}",
    )


def test_watch_id_has_no_timestamp():
    """A listing is one subject, however many times we look at it."""
    first = watch_id("willhaben", "123")
    assert first == "watch:willhaben:123"
    assert first == watch_id("willhaben", "123")


def test_watch_item_keeps_the_asking_price_it_was_seen_at():
    item = from_observation(observation(price="450"))

    assert item.asking_amount == Decimal("450")
    assert item.asking_currency == "EUR"
    assert item.first_seen_at == NOW
    assert item.product_id == "rtx-3080-ti"


def test_watch_item_carries_no_verdict():
    """Watching is not scoring: nothing here implies a trade decision."""
    fields = set(from_observation(observation()).model_dump())

    assert not fields & {"verdict", "roi", "expected_profit_eur", "landed_cost_eur"}


def test_adding_the_same_listing_twice_does_not_duplicate_it(tmp_path):
    path = tmp_path / "watchlist.jsonl"
    first = append_watch_items([from_observation(observation())], path)
    again = append_watch_items([from_observation(observation(price="480"))], path)

    assert len(first) == 1
    assert again == []  # same listing, one subject
    assert len(load_watchlist(path)) == 1


def test_only_new_listings_are_appended(tmp_path):
    path = tmp_path / "watchlist.jsonl"
    append_watch_items([from_observation(observation("aaa"))], path)
    added = append_watch_items(
        [from_observation(observation("aaa")), from_observation(observation("bbb"))], path
    )

    assert [item.source_listing_id for item in added] == ["bbb"]
    assert len(load_watchlist(path)) == 2


def test_missing_watchlist_is_empty_not_an_error(tmp_path):
    assert load_watchlist(tmp_path / "absent.jsonl") == []


def test_malformed_line_raises_instead_of_being_skipped(tmp_path):
    path = tmp_path / "watchlist.jsonl"
    append_watch_items([from_observation(observation())], path)
    path.write_text(path.read_text(encoding="utf-8") + "{broken}\n", encoding="utf-8")

    with pytest.raises(WatchlistError):
        load_watchlist(path)
