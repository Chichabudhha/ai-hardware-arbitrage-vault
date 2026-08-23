"""Cross-market price matrix and gross spreads."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.core.models import Condition, PriceObservation, PriceType
from src.pricing.market_matrix import build_matrix, render_table, spreads
from src.pricing.serbian_market import estimate_resale

NOW = datetime(2026, 8, 19, tzinfo=timezone.utc)


def obs(
    price: str,
    marketplace: str = "kupujemprodajem",
    product_id: str = "rtx-3080-ti",
    currency: str = "EUR",
    listing_id: str | None = None,
    days_ago: int = 1,
) -> PriceObservation:
    return PriceObservation(
        product_id=product_id,
        price_amount=Decimal(price),
        currency=currency,
        price_type=PriceType.ASKING,
        condition=Condition.USED,
        observed_at=NOW - timedelta(days=days_ago),
        marketplace=marketplace,
        source_listing_id=listing_id or f"{marketplace}-{price}",
    )


def market(prices: list[str], marketplace: str, **kwargs) -> list[PriceObservation]:
    return [obs(p, marketplace, listing_id=f"{marketplace}-{i}", **kwargs) for i, p in enumerate(prices)]


SERBIA = ["380", "390", "390", "400", "410", "410"]
GERMANY = ["245", "300", "350", "420", "430", "450"]


def test_each_cell_matches_the_single_market_estimate():
    """The matrix must not be a second, looser code path for money."""
    observations = market(SERBIA, "kupujemprodajem") + market(GERMANY, "kleinanzeigen")
    cells = {c.marketplace: c for c in build_matrix(observations, now=NOW)}

    from dataclasses import replace

    from src.pricing.serbian_market import DEFAULT_RULES

    direct = estimate_resale(
        observations,
        "rtx-3080-ti",
        now=NOW,
        rules=replace(DEFAULT_RULES, resale_marketplaces=frozenset({"kleinanzeigen"})),
    )
    assert cells["kleinanzeigen"].p25 == direct.p25
    assert cells["kleinanzeigen"].median == direct.median
    assert cells["kleinanzeigen"].sample_size == direct.sample_size


def test_matrix_separates_markets_instead_of_pooling_them():
    observations = market(SERBIA, "kupujemprodajem") + market(GERMANY, "kleinanzeigen")
    cells = {c.marketplace: c for c in build_matrix(observations, now=NOW)}

    assert cells["kupujemprodajem"].sample_size == 6
    assert cells["kleinanzeigen"].sample_size == 6
    # Pooled, the median would sit between the two markets and describe neither.
    assert cells["kupujemprodajem"].median != cells["kleinanzeigen"].median


def test_thin_market_is_reported_not_estimated():
    observations = market(SERBIA, "kupujemprodajem") + market(["300", "310"], "subito")
    cells = {c.marketplace: c for c in build_matrix(observations, now=NOW)}

    assert cells["subito"].is_usable is False
    assert cells["subito"].p25 is None
    assert cells["subito"].missing_inputs == ["sample_size_below_5"]


def test_spread_buys_at_p25_and_sells_at_median():
    observations = market(SERBIA, "kupujemprodajem") + market(GERMANY, "kleinanzeigen")
    cells = build_matrix(observations, now=NOW)
    found = {(s.cheap_market, s.rich_market): s for s in spreads(cells)}

    buy_de = found[("kleinanzeigen", "kupujemprodajem")]
    assert buy_de.cheap_p25_eur == Decimal("313")  # P25 of the German sample
    assert buy_de.rich_median_eur == Decimal("395")  # median of the Serbian sample
    assert buy_de.gross_spread_eur == Decimal("82")  # 395 - 313


def test_net_spread_subtracts_the_flat_corridor_shipping():
    """D-019: 25 EUR in every direction, as a working assumption."""
    observations = market(SERBIA, "kupujemprodajem") + market(GERMANY, "kleinanzeigen")
    buy_de = next(
        s for s in spreads(build_matrix(observations, now=NOW))
        if s.cheap_market == "kleinanzeigen"
    )

    assert buy_de.shipping_eur == Decimal("25")
    assert buy_de.net_spread_eur == buy_de.gross_spread_eur - Decimal("25")


def test_local_prices_are_converted_at_an_observed_rate():
    from datetime import datetime as dt

    from src.core.money import FxRate

    rate = FxRate(
        base_currency="EUR",
        quote_currency="RON",
        rate=Decimal("5"),
        observed_at=dt(2026, 8, 19, tzinfo=timezone.utc),
        source="test-fixture",
    )
    observations = market(
        ["2200", "2250", "2300", "2350", "2400", "2450"], "olx-ro", currency="RON"
    )
    (cell,) = build_matrix(observations, now=NOW, rates=[rate])

    assert cell.currency == "RON"
    assert cell.p25 == Decimal("2263")  # observed, in lei
    assert cell.p25_eur == Decimal("452.60")  # derived at 5 RON/EUR
    assert cell.fx_note is None


def test_a_market_without_a_rate_shows_no_euro_figure():
    observations = market(
        ["2200", "2250", "2300", "2350", "2400", "2450"], "olx-ro", currency="RON"
    )
    (cell,) = build_matrix(observations, now=NOW, rates=[])

    assert cell.p25 == Decimal("2263")  # the observation is not lost
    assert cell.p25_eur is None  # but no euro figure is invented
    assert cell.fx_note == "no_observed_rate:RON/EUR"


def test_spread_is_reported_in_whichever_direction_pays():
    """Selling *into* a market is a trade too — direction is data, not doctrine."""
    cheap_at_home = market(["300", "300", "310", "320", "330", "340"], "kupujemprodajem")
    rich_abroad = market(["500", "520", "540", "560", "580", "600"], "subito")
    directions = {
        (s.cheap_market, s.rich_market)
        for s in spreads(build_matrix(cheap_at_home + rich_abroad, now=NOW))
    }

    assert ("kupujemprodajem", "subito") in directions
    assert ("subito", "kupujemprodajem") not in directions


def test_a_market_without_a_rate_is_left_out_of_spreads():
    """Better a missing comparison than one made at a guessed rate."""
    observations = market(SERBIA, "kupujemprodajem") + market(
        ["100", "110", "120", "130", "140", "150"], "olx-ro", currency="RON"
    )
    cells = build_matrix(observations, now=NOW, rates=[])

    assert {c.currency for c in cells} == {"EUR", "RON"}
    assert spreads(cells) == []


def test_spread_is_gross_and_says_so():
    observations = market(SERBIA, "kupujemprodajem") + market(GERMANY, "kleinanzeigen")
    headline = spreads(build_matrix(observations, now=NOW))[0].headline

    assert "gross" in headline
    assert headline.isascii()  # printed to a cp1250 console


def test_table_renders_without_observations():
    assert render_table([]) == "no observations"
