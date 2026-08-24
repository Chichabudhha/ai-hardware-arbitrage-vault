from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.core.models import Condition, PriceBasis, PriceObservation, PriceType
from src.pricing.serbian_market import (
    DEFAULT_RULES,
    PricingRules,
    estimate_resale,
    percentile,
)

NOW = datetime(2026, 8, 19, tzinfo=timezone.utc)


def obs(
    price: str,
    days_ago: int = 1,
    price_type: PriceType = PriceType.ASKING,
    condition: Condition = Condition.USED,
    product_id: str = "rtx-3090",
    currency: str = "RSD",
    is_bundle: bool = False,
    listing_id: str | None = None,
) -> PriceObservation:
    return PriceObservation(
        product_id=product_id,
        price_amount=Decimal(price),
        currency=currency,
        price_type=price_type,
        condition=condition,
        observed_at=NOW - timedelta(days=days_ago),
        marketplace="kupujemprodajem",
        source_listing_id=listing_id or f"kp-{price}-{days_ago}",
        is_bundle=is_bundle,
    )


def sample(prices: list[str], **kwargs) -> list[PriceObservation]:
    return [obs(p, listing_id=f"kp-{i}", **kwargs) for i, p in enumerate(prices)]


BASE = ["95000", "99000", "102000", "105000", "110000", "115000"]


# --- percentile -------------------------------------------------------------


def test_percentile_interpolates_linearly():
    values = [Decimal("10"), Decimal("20"), Decimal("30"), Decimal("40")]
    assert percentile(values, Decimal("0.50")) == Decimal("25")
    assert percentile(values, Decimal("0.25")) == Decimal("17.5")


def test_percentile_of_single_value_is_that_value():
    assert percentile([Decimal("42")], Decimal("0.75")) == Decimal("42")


def test_percentile_of_empty_sample_raises():
    with pytest.raises(ValueError):
        percentile([], Decimal("0.5"))


def test_percentile_does_not_depend_on_input_order():
    forward = percentile([Decimal(x) for x in "13579"], Decimal("0.5"))
    backward = percentile([Decimal(x) for x in "97531"], Decimal("0.5"))
    assert forward == backward


# --- the asking-vs-sold rule (CLAUDE.md principle 3) ------------------------


def test_asking_only_sample_uses_p25_not_median():
    """Asking is not sold, and the gap is unmeasured — P25 is the observed anchor."""
    estimate = estimate_resale(sample(BASE), "rtx-3090", now=NOW)
    assert estimate.price_basis is PriceBasis.ASKING
    assert estimate.resale_expected == estimate.p25
    assert estimate.resale_expected < estimate.median


def test_sold_sample_uses_the_median():
    estimate = estimate_resale(
        sample(BASE, price_type=PriceType.SOLD), "rtx-3090", now=NOW
    )
    assert estimate.price_basis is PriceBasis.SOLD
    assert estimate.resale_expected == estimate.median


def test_completed_counts_as_sold():
    estimate = estimate_resale(
        sample(BASE, price_type=PriceType.COMPLETED), "rtx-3090", now=NOW
    )
    assert estimate.price_basis is PriceBasis.SOLD


def test_one_asking_price_makes_the_basis_mixed():
    observations = sample(BASE, price_type=PriceType.SOLD)
    observations.append(obs("108000", price_type=PriceType.ASKING, listing_id="kp-asking"))
    estimate = estimate_resale(observations, "rtx-3090", now=NOW)
    assert estimate.price_basis is PriceBasis.MIXED
    # Mixed is not sold: the conservative anchor applies until the sample is clean.
    assert estimate.resale_expected == estimate.p25


def test_sold_data_earns_more_confidence_than_asking():
    asking = estimate_resale(sample(BASE), "rtx-3090", now=NOW)
    sold = estimate_resale(sample(BASE, price_type=PriceType.SOLD), "rtx-3090", now=NOW)
    assert sold.confidence > asking.confidence


# --- exclusion rules --------------------------------------------------------


def test_bundle_price_is_not_a_gpu_price():
    observations = sample(BASE)
    observations.append(obs("250000", is_bundle=True, listing_id="kp-bundle"))
    estimate = estimate_resale(observations, "rtx-3090", now=NOW)
    assert estimate.sample_size == len(BASE)
    assert any(x.reason == "bundle_price_is_not_a_gpu_price" for x in estimate.excluded)


def test_dealer_reference_is_not_a_peer_price():
    observations = sample(BASE)
    observations.append(
        obs("250000", price_type=PriceType.DEALER_REFERENCE, listing_id="kp-dealer")
    )
    estimate = estimate_resale(observations, "rtx-3090", now=NOW)
    assert estimate.sample_size == len(BASE)
    assert any(
        x.reason == "reference_price_not_peer:dealer_reference" for x in estimate.excluded
    )


def test_manual_reference_is_not_a_peer_price():
    observations = sample(BASE)
    observations.append(
        obs("250000", price_type=PriceType.MANUAL_REFERENCE, listing_id="kp-manual")
    )
    estimate = estimate_resale(observations, "rtx-3090", now=NOW)
    assert estimate.sample_size == len(BASE)
    assert any(
        x.reason == "reference_price_not_peer:manual_reference" for x in estimate.excluded
    )


def test_for_parts_is_excluded():
    observations = sample(BASE)
    observations.append(obs("30000", condition=Condition.FOR_PARTS, listing_id="kp-parts"))
    estimate = estimate_resale(observations, "rtx-3090", now=NOW)
    assert any(x.reason == "for_parts" for x in estimate.excluded)


def test_new_and_used_are_not_mixed():
    observations = sample(BASE)
    observations.append(obs("180000", condition=Condition.NEW, listing_id="kp-new"))
    estimate = estimate_resale(observations, "rtx-3090", condition=Condition.USED, now=NOW)
    assert estimate.sample_size == len(BASE)
    assert any(x.reason == "condition_mismatch:new" for x in estimate.excluded)


def test_other_products_are_excluded():
    observations = sample(BASE)
    observations.append(obs("70000", product_id="rtx-3080-ti", listing_id="kp-other"))
    estimate = estimate_resale(observations, "rtx-3090", now=NOW)
    assert any(x.reason == "different_product" for x in estimate.excluded)


def test_sample_is_never_mixed_across_currencies():
    """D-013: EUR and RSD are both valid, but one percentile cannot span both."""
    observations = sample(BASE)  # six RSD listings
    observations.append(obs("800", currency="EUR", listing_id="kp-eur"))
    estimate = estimate_resale(observations, "rtx-3090", now=NOW)

    assert estimate.currency == "RSD"  # RSD is the majority here
    assert any(x.reason == "currency_not_sample:EUR" for x in estimate.excluded)


def test_eur_majority_makes_eur_the_sample_currency():
    observations = sample(["750", "780", "800", "820", "850"], currency="EUR")
    observations.append(obs("99000", listing_id="kp-rsd"))
    estimate = estimate_resale(observations, "rtx-3090", now=NOW)

    assert estimate.currency == "EUR"
    assert estimate.is_usable
    assert estimate.resale_expected == Decimal("780")  # P25 of the EUR sample
    assert any(x.reason == "currency_not_sample:RSD" for x in estimate.excluded)


def test_currency_can_be_requested_explicitly():
    observations = sample(["750", "780", "800", "820", "850"], currency="EUR")
    estimate = estimate_resale(observations, "rtx-3090", now=NOW, currency="RSD")

    assert estimate.currency == "RSD"
    assert not estimate.is_usable
    assert all(x.reason == "currency_not_sample:EUR" for x in estimate.excluded)


def test_a_third_currency_is_kept_out_of_the_sample_not_converted():
    """D-018: CHF is a real market currency, just not this sample's."""
    observations = sample(BASE)
    observations.append(obs("900", currency="CHF", listing_id="kp-chf"))
    estimate = estimate_resale(observations, "rtx-3090", now=NOW)

    assert any(x.reason == "currency_not_sample:CHF" for x in estimate.excluded)


def test_a_malformed_currency_code_is_rejected_outright():
    observations = sample(BASE)
    observations.append(obs("900", currency="XX", listing_id="kp-bad"))
    estimate = estimate_resale(observations, "rtx-3090", now=NOW)

    assert any(x.reason == "unsupported_currency:XX" for x in estimate.excluded)


def test_currency_tie_breaks_to_eur_the_same_way_every_run():
    observations = sample(["750", "780"], currency="EUR") + sample(
        ["99000", "105000"], currency="RSD"
    )
    first = estimate_resale(observations, "rtx-3090", now=NOW)
    second = estimate_resale(list(reversed(observations)), "rtx-3090", now=NOW)

    assert first.currency == second.currency == "EUR"


def test_stale_observations_are_excluded():
    observations = sample(BASE)
    observations.append(obs("140000", days_ago=200, listing_id="kp-stale"))
    estimate = estimate_resale(observations, "rtx-3090", now=NOW)
    assert any(x.reason.startswith("stale_over_") for x in estimate.excluded)


def test_every_exclusion_records_its_price_and_listing():
    observations = sample(BASE)
    observations.append(obs("250000", is_bundle=True, listing_id="kp-bundle"))
    estimate = estimate_resale(observations, "rtx-3090", now=NOW)
    dropped = next(x for x in estimate.excluded if x.source_listing_id == "kp-bundle")
    assert dropped.price_amount == Decimal("250000")


# --- outliers ---------------------------------------------------------------


def test_bait_listing_does_not_drag_the_estimate_down():
    """A 3090 listed at 1000 din is bait, not a market price."""
    clean = estimate_resale(sample(BASE), "rtx-3090", now=NOW)
    with_bait = estimate_resale(
        sample(BASE) + [obs("1000", listing_id="kp-bait")], "rtx-3090", now=NOW
    )
    assert with_bait.resale_expected == clean.resale_expected
    assert any(x.reason == "outlier_below_iqr_fence" for x in with_bait.excluded)


def test_absurdly_high_listing_is_excluded():
    observations = sample(BASE) + [obs("900000", listing_id="kp-high")]
    estimate = estimate_resale(observations, "rtx-3090", now=NOW)
    assert any(x.reason == "outlier_above_iqr_fence" for x in estimate.excluded)


def test_identical_prices_survive_the_outlier_rule():
    """Zero IQR must not fence out the whole sample."""
    estimate = estimate_resale(sample(["100000"] * 6), "rtx-3090", now=NOW)
    assert estimate.sample_size == 6
    assert estimate.resale_expected == Decimal("100000")


# --- insufficient data ------------------------------------------------------


def test_thin_sample_is_insufficient_data_not_a_guess():
    estimate = estimate_resale(sample(["100000", "105000"]), "rtx-3090", now=NOW)
    assert not estimate.is_usable
    assert estimate.resale_expected is None
    assert estimate.missing_inputs == ["sample_size_below_5"]


def test_empty_input_is_insufficient_data():
    estimate = estimate_resale([], "rtx-3090", now=NOW)
    assert not estimate.is_usable
    assert estimate.missing_inputs == ["no_usable_observations"]


def test_unusable_estimate_carries_no_number_at_all():
    """UNKNOWN is not 0 (principle 2) — an unusable estimate reports nothing."""
    estimate = estimate_resale(sample(["100000"]), "rtx-3090", now=NOW)
    assert estimate.resale_conservative is None
    assert estimate.resale_optimistic is None
    assert estimate.median is None
    assert estimate.confidence == Decimal("0")


def test_sample_thinned_by_exclusions_is_insufficient():
    observations = sample(["100000", "101000", "102000"]) + [
        obs("103000", is_bundle=True, listing_id="kp-b1"),
        obs("104000", condition=Condition.NEW, listing_id="kp-b2"),
        obs("105000", days_ago=400, listing_id="kp-b3"),
    ]
    estimate = estimate_resale(observations, "rtx-3090", now=NOW)
    assert not estimate.is_usable
    assert len(estimate.excluded) == 3


def test_non_positive_price_is_excluded():
    observations = sample(BASE) + [obs("0", listing_id="kp-zero")]
    estimate = estimate_resale(observations, "rtx-3090", now=NOW)
    assert any(x.reason == "non_positive_price" for x in estimate.excluded)


# --- confidence -------------------------------------------------------------


def test_larger_sample_earns_more_confidence():
    small = estimate_resale(sample(BASE), "rtx-3090", now=NOW)
    big = estimate_resale(sample(BASE * 4), "rtx-3090", now=NOW)
    assert big.confidence > small.confidence


def test_wide_spread_costs_confidence():
    tight = estimate_resale(
        sample(["100000", "101000", "102000", "103000", "104000", "105000"]),
        "rtx-3090",
        now=NOW,
    )
    wide = estimate_resale(
        sample(["60000", "80000", "100000", "120000", "140000", "160000"]),
        "rtx-3090",
        now=NOW,
    )
    assert tight.confidence > wide.confidence


def test_stale_but_valid_sample_costs_confidence():
    fresh = estimate_resale(sample(BASE, days_ago=1), "rtx-3090", now=NOW)
    old = estimate_resale(sample(BASE, days_ago=85), "rtx-3090", now=NOW)
    assert fresh.confidence > old.confidence


def test_confidence_stays_within_bounds():
    estimate = estimate_resale(sample(BASE * 10, price_type=PriceType.SOLD), "rtx-3090", now=NOW)
    assert Decimal("0") <= estimate.confidence <= Decimal("1")


# --- output contract --------------------------------------------------------


def test_percentiles_are_ordered():
    estimate = estimate_resale(sample(BASE), "rtx-3090", now=NOW)
    assert estimate.p25 <= estimate.median <= estimate.p75


def test_prices_are_whole_dinars():
    estimate = estimate_resale(sample(["100000", "100001", "100002", "100003", "100004"]),
                               "rtx-3090", now=NOW)
    assert estimate.resale_expected == estimate.resale_expected.to_integral_value()


def test_estimate_can_explain_itself():
    """PRICING-ENGINE.md gate: the system must explain how it got the number."""
    estimate = estimate_resale(sample(BASE), "rtx-3090", now=NOW)
    joined = " ".join(estimate.explanation)
    assert "P25" in joined
    assert f"n={estimate.sample_size}" in joined


def test_provenance_lists_the_observations_used():
    estimate = estimate_resale(sample(BASE), "rtx-3090", now=NOW)
    assert estimate.provenance.calculation_version == "pricing-v1"
    assert estimate.provenance.source == "kupujemprodajem"
    assert len(estimate.provenance.input_refs) == estimate.sample_size


def test_result_is_reproducible():
    first = estimate_resale(sample(BASE), "rtx-3090", now=NOW)
    second = estimate_resale(sample(list(reversed(BASE))), "rtx-3090", now=NOW)
    assert first.resale_expected == second.resale_expected
    assert first.confidence == second.confidence


def test_rules_are_overridable_without_touching_the_call_site():
    strict = PricingRules(min_sample_size=10)
    estimate = estimate_resale(sample(BASE), "rtx-3090", now=NOW, rules=strict)
    assert estimate.missing_inputs == ["sample_size_below_10"]
    assert DEFAULT_RULES.min_sample_size == 5


# --- wiring into the deal engine -------------------------------------------

from src.core.models import PriceType as _PT  # noqa: E402,F401
from src.pricing.calculator import CostInputs, build_opportunity  # noqa: E402
from src.core.money import FxRate  # noqa: E402
from src.core.models import Verdict  # noqa: E402

EUR_RSD = FxRate("EUR", "RSD", Decimal("117.20"), NOW, "fx-fixture")
DOMESTIC = CostInputs(
    shipping_eur=Decimal("10"),
    import_buffer_eur=Decimal("0"),
    is_import=False,
    source="test-fixture",
)


def test_estimate_feeds_the_deal_engine(listing, evaluation, product_match):
    estimate = estimate_resale(sample(BASE), "rtx-3090", now=NOW)
    opportunity = build_opportunity(
        listing, evaluation, DOMESTIC, estimate, EUR_RSD, product_match=product_match
    )
    assert opportunity.expected_sale_rsd == estimate.resale_expected
    assert opportunity.price_basis is PriceBasis.ASKING
    assert opportunity.pricing_confidence == estimate.confidence
    assert opportunity.pricing_sample_size == estimate.sample_size


def test_unusable_estimate_blocks_the_deal(listing, evaluation, product_match):
    """A thin sample must not silently become a price."""
    estimate = estimate_resale(sample(["100000", "105000"]), "rtx-3090", now=NOW)
    opportunity = build_opportunity(
        listing, evaluation, DOMESTIC, estimate, EUR_RSD, product_match=product_match
    )
    assert opportunity.verdict is Verdict.INSUFFICIENT_DATA
    assert "resale:sample_size_below_5" in opportunity.missing_inputs
    assert opportunity.expected_sale_rsd is None


def test_bare_number_still_works_but_carries_no_basis(listing, evaluation, product_match):
    opportunity = build_opportunity(
        listing, evaluation, DOMESTIC, Decimal("117200"), EUR_RSD, product_match=product_match
    )
    assert opportunity.expected_sale_rsd == Decimal("117200")
    assert opportunity.price_basis is None


def test_pricing_version_reaches_the_opportunity_provenance(
    listing, evaluation, product_match
):
    estimate = estimate_resale(sample(BASE), "rtx-3090", now=NOW)
    opportunity = build_opportunity(
        listing, evaluation, DOMESTIC, estimate, EUR_RSD, product_match=product_match
    )
    assert "pricing-v1" in opportunity.provenance.input_refs


# --- guards found by delegated review (Copilot, 2026-08-19) -----------------


@pytest.mark.parametrize("fraction", ["-0.1", "1.2", "2"])
def test_percentile_outside_zero_to_one_is_rejected(fraction):
    """Extrapolation would return a price no observation supports."""
    with pytest.raises(ValueError):
        percentile([Decimal("10"), Decimal("20")], Decimal(fraction))


def test_percentile_accepts_the_exact_bounds():
    values = [Decimal("10"), Decimal("20"), Decimal("30")]
    assert percentile(values, Decimal("0")) == Decimal("10")
    assert percentile(values, Decimal("1")) == Decimal("30")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"full_sample_size": 0},
        {"max_age_days": 0},
        {"min_sample_size": 0},
        {"iqr_fence": Decimal("-1")},
    ],
)
def test_invalid_rules_fail_at_configuration_time(kwargs):
    """A zero divisor must not surface halfway through an estimate."""
    with pytest.raises(ValueError):
        PricingRules(**kwargs)


def test_foreign_marketplace_never_enters_the_serbian_sample():
    """D-006: an EU sale price is sourcing data, not the resale benchmark."""
    observations = sample(BASE)
    german = obs("400", currency="EUR", listing_id="ka-1").model_copy(
        update={"marketplace": "kleinanzeigen"}
    )
    estimate = estimate_resale(observations + [german], "rtx-3090", now=NOW)

    assert any(
        x.reason == "non_resale_marketplace:kleinanzeigen" for x in estimate.excluded
    )
