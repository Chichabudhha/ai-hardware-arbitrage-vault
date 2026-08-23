from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.core.models import Condition, Evaluation, GpuSpec, RiskFlag, RiskLevel, Verdict
from src.core.money import FxRate
from src.deal_engine.risk import risk_level, risk_points, risk_reserve_rate
from src.pricing.calculator import CostInputs, build_opportunity

EUR_RSD = FxRate(
    base_currency="EUR",
    quote_currency="RSD",
    rate=Decimal("117.20"),
    observed_at=datetime(2026, 8, 18, tzinfo=timezone.utc),
    source="test-fixture",
)

COSTS = CostInputs(
    shipping_eur=Decimal("35"),
    import_buffer_eur=Decimal("60"),
    is_import=True,
    source="test-fixture",
    intermediary_fee_eur=Decimal("25"),
)


def test_missing_sale_price_yields_insufficient_data(listing, evaluation):
    opportunity = build_opportunity(listing, evaluation, COSTS, None, EUR_RSD)
    assert opportunity.verdict is Verdict.INSUFFICIENT_DATA
    assert "expected_sale_rsd" in opportunity.missing_inputs
    assert opportunity.expected_profit_eur is None


def test_missing_shipping_is_not_treated_as_zero(listing, evaluation):
    # D-015 gives imports an approved default, so UNKNOWN only survives on a
    # domestic deal, where no shipping figure has ever been decided.
    inputs = CostInputs(
        shipping_eur=None,
        import_buffer_eur=Decimal("60"),
        is_import=False,
        intermediary_fee_eur=Decimal("25"),
    )
    opportunity = build_opportunity(listing, evaluation, inputs, Decimal("100000"), EUR_RSD)
    assert opportunity.verdict is Verdict.INSUFFICIENT_DATA
    assert "shipping_eur" in opportunity.missing_inputs


def test_import_falls_back_to_the_approved_cost_defaults(listing, evaluation, product_match):
    """D-015: 25 EUR shipping, 0 buffer — approved values, not silent zeros."""
    inputs = CostInputs(shipping_eur=None, import_buffer_eur=None, is_import=True)
    opportunity = build_opportunity(
        listing, evaluation, inputs, Decimal("117200"), EUR_RSD, product_match=product_match
    )

    assert opportunity.verdict is not Verdict.INSUFFICIENT_DATA
    assert opportunity.costs.shipping_eur == Decimal("25.00")
    assert opportunity.costs.import_buffer_eur == Decimal("0.00")
    assert opportunity.costs.intermediary_fee_eur == Decimal("15.00")


def test_a_quoted_cost_still_overrides_the_default(listing, evaluation, product_match):
    inputs = CostInputs(shipping_eur=Decimal("40"), import_buffer_eur=Decimal("12"), is_import=True)
    opportunity = build_opportunity(
        listing, evaluation, inputs, Decimal("117200"), EUR_RSD, product_match=product_match
    )

    assert opportunity.costs.shipping_eur == Decimal("40.00")
    assert opportunity.costs.import_buffer_eur == Decimal("12.00")


def test_profit_and_roi_are_exact(listing, evaluation, product_match):
    opportunity = build_opportunity(
        listing, evaluation, COSTS, Decimal("117200"), EUR_RSD, product_match=product_match
    )

    # no_warranty + no_packaging = 2 points -> Low risk; import reserve is 5%.
    assert opportunity.risk_level is RiskLevel.LOW
    assert opportunity.costs.risk_reserve_eur == Decimal("31.00")
    # 620 purchase + 35 shipping + 60 import buffer + 25 intermediary + 31 reserve
    assert opportunity.costs.intermediary_fee_eur == Decimal("25.00")
    assert opportunity.costs.landed_cost_eur == Decimal("771.00")
    assert opportunity.expected_sale_eur == Decimal("1000.00")
    assert opportunity.expected_profit_eur == Decimal("229.00")
    assert opportunity.roi == Decimal("0.2970")
    # Economics clear every floor, but 620 EUR is above the 500 EUR per-purchase
    # cap (D-008), so the best available verdict is NEGOTIATE, not BUY.
    assert opportunity.verdict is Verdict.NEGOTIATE


def test_non_eur_purchase_without_rate_is_insufficient(listing, evaluation, product_match):
    rsd_listing = listing.model_copy(
        update={"price_amount": Decimal("70000"), "currency": "RSD"}
    )
    opportunity = build_opportunity(
        rsd_listing, evaluation, COSTS, Decimal("117200"), EUR_RSD, product_match=product_match
    )
    assert opportunity.verdict is Verdict.INSUFFICIENT_DATA
    assert opportunity.missing_inputs == ["fx_rsd_eur"]


def test_mining_and_damage_push_risk_high():
    evaluation = Evaluation(
        spec=GpuSpec(gpu_chip="RTX 3090", vram_gb=24, match_confidence=0.9),
        condition=Condition.USED,
        has_warranty=False,
        risk_flags=[RiskFlag.MINING_USE, RiskFlag.PHYSICAL_DAMAGE],
    )
    assert risk_level(evaluation) is RiskLevel.HIGH
    assert risk_reserve_rate(RiskLevel.HIGH, is_import=True) == Decimal("0.15")


def test_verified_local_low_risk_has_no_reserve():
    assert risk_reserve_rate(RiskLevel.LOW, is_import=False) == Decimal("0")
    assert risk_reserve_rate(RiskLevel.LOW, is_import=True) == Decimal("0.05")


def test_unknown_spec_raises_risk(listing):
    vague = Evaluation(spec=GpuSpec(match_confidence=0.2), condition=Condition.UNKNOWN)
    assert risk_level(vague) in (RiskLevel.MEDIUM, RiskLevel.HIGH)


def test_corrupt_fx_store_raises_insufficient_data(tmp_path):
    import json

    from src.core.money import InsufficientData
    from src.pricing.fx import load_rates

    store = tmp_path / "fx.json"
    store.write_text(
        json.dumps(
            [
                {
                    "base_currency": "EUR",
                    "quote_currency": "RSD",
                    "rate": "0",
                    "observed_at": "2026-08-18T00:00:00+00:00",
                    "source": "corrupt",
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(InsufficientData):
        load_rates(store)


def test_expected_sale_rsd_is_whole_dinars(listing, evaluation, product_match):
    opportunity = build_opportunity(
        listing, evaluation, COSTS, Decimal("149899.60"), EUR_RSD, product_match=product_match
    )
    assert opportunity.expected_sale_rsd == Decimal("149900")


def test_high_risk_boundary_at_six_points():
    """PHYSICAL_DAMAGE(4) + NO_PACKAGING(1) + unknown warranty(1) = 6 -> High."""
    evaluation = Evaluation(
        spec=GpuSpec(gpu_chip="RTX 3090", vram_gb=24, match_confidence=0.9),
        condition=Condition.USED,
        has_warranty=None,
        risk_flags=[RiskFlag.PHYSICAL_DAMAGE, RiskFlag.NO_PACKAGING],
    )
    assert risk_points(evaluation) == 6
    assert risk_level(evaluation) is RiskLevel.HIGH


def test_match_confidence_boundary_is_exclusive():
    """Exactly 0.6 must not add the low-confidence penalty."""
    at_threshold = Evaluation(
        spec=GpuSpec(gpu_chip="RTX 3090", vram_gb=24, match_confidence=0.6),
        condition=Condition.USED,
        has_warranty=False,
        risk_flags=[RiskFlag.UNTESTED],
    )
    below = at_threshold.model_copy(
        update={"spec": GpuSpec(gpu_chip="RTX 3090", vram_gb=24, match_confidence=0.59)}
    )
    assert risk_points(at_threshold) == 3
    assert risk_points(below) == 5
    assert risk_level(at_threshold) is RiskLevel.MEDIUM


def test_for_parts_alone_reaches_medium():
    evaluation = Evaluation(
        spec=GpuSpec(gpu_chip="RTX 3090", vram_gb=24, match_confidence=0.9),
        condition=Condition.FOR_PARTS,
        has_warranty=True,
        risk_flags=[],
    )
    assert risk_points(evaluation) == 4
    assert risk_level(evaluation) is RiskLevel.MEDIUM
    assert risk_reserve_rate(RiskLevel.MEDIUM, is_import=False) == Decimal("0.08")


def test_unmatched_product_blocks_financial_conclusion(listing, evaluation):
    """CLAUDE.md section 5: product match is required for a financial conclusion."""
    from src.products import match_text

    opportunity = build_opportunity(
        listing, evaluation, COSTS, Decimal("117200"), EUR_RSD,
        product_match=match_text("Playstation 5"),
    )
    assert opportunity.verdict is Verdict.INSUFFICIENT_DATA
    assert "product_match:UNMATCHED" in opportunity.missing_inputs
    assert opportunity.expected_profit_eur is None


def test_vram_conflict_blocks_financial_conclusion(listing, evaluation):
    from src.products import match_text

    opportunity = build_opportunity(
        listing, evaluation, COSTS, Decimal("117200"), EUR_RSD,
        product_match=match_text("RTX 3090 12GB nvidia"),
    )
    assert opportunity.verdict is Verdict.INSUFFICIENT_DATA
    assert "product_match:CONFLICT" in opportunity.missing_inputs


def test_missing_match_is_reported(listing, evaluation):
    opportunity = build_opportunity(listing, evaluation, COSTS, Decimal("117200"), EUR_RSD)
    assert "product_match" in opportunity.missing_inputs


# --- W0 policy gates (D-008, D-009, D-010) ---------------------------------

from src.core.policy import OWNER_POLICY, Policy  # noqa: E402
from src.pricing.calculator import decide  # noqa: E402

CHEAP = CostInputs(
    shipping_eur=Decimal("10"),
    import_buffer_eur=Decimal("0"),
    is_import=False,
    source="test-fixture",
)


def test_owner_policy_matches_approved_decisions():
    assert OWNER_POLICY.capital_eur == Decimal("1000")
    assert OWNER_POLICY.max_purchase_eur == Decimal("500")
    assert OWNER_POLICY.min_profit_eur == Decimal("50")
    assert OWNER_POLICY.buy_min_roi == Decimal("0.18")


def test_policy_rejects_inverted_thresholds():
    with pytest.raises(ValueError):
        Policy(
            capital_eur=Decimal("1000"),
            max_purchase_eur=Decimal("500"),
            min_profit_eur=Decimal("50"),
            buy_min_roi=Decimal("0.05"),
            negotiate_min_roi=Decimal("0.09"),
            watch_min_roi=Decimal("0.04"),
            intermediary_fee_eur=Decimal("15"),
        )


def test_policy_rejects_purchase_cap_above_capital():
    with pytest.raises(ValueError):
        Policy(
            capital_eur=Decimal("500"),
            max_purchase_eur=Decimal("1000"),
            min_profit_eur=Decimal("50"),
            buy_min_roi=Decimal("0.18"),
            negotiate_min_roi=Decimal("0.09"),
            watch_min_roi=Decimal("0.04"),
            intermediary_fee_eur=Decimal("15"),
        )


def test_high_roi_but_thin_profit_is_not_a_buy():
    """40% ROI on a 100 EUR card is 40 EUR — below the 50 EUR floor (D-009)."""
    verdict = decide(
        roi=Decimal("0.40"),
        level=RiskLevel.LOW,
        profit_eur=Decimal("40"),
        purchase_eur=Decimal("100"),
    )
    assert verdict is Verdict.NEGOTIATE


def test_buy_needs_both_roi_and_profit_floors():
    verdict = decide(
        roi=Decimal("0.18"),
        level=RiskLevel.LOW,
        profit_eur=Decimal("50"),
        purchase_eur=Decimal("250"),
    )
    assert verdict is Verdict.BUY


def test_over_budget_purchase_cannot_be_buy():
    """Above the per-purchase cap the owner cannot pay the asking price (D-008)."""
    verdict = decide(
        roi=Decimal("0.50"),
        level=RiskLevel.LOW,
        profit_eur=Decimal("400"),
        purchase_eur=Decimal("500.01"),
    )
    assert verdict is Verdict.NEGOTIATE


def test_purchase_exactly_at_cap_is_allowed():
    verdict = decide(
        roi=Decimal("0.50"),
        level=RiskLevel.LOW,
        profit_eur=Decimal("400"),
        purchase_eur=Decimal("500"),
    )
    assert verdict is Verdict.BUY


def test_import_falls_back_to_policy_intermediary_fee(listing, evaluation, product_match):
    """D-010: the intermediary charges a flat 15 EUR; a deal need not restate it."""
    inputs = CostInputs(
        shipping_eur=Decimal("35"),
        import_buffer_eur=Decimal("60"),
        is_import=True,
    )
    opportunity = build_opportunity(
        listing, evaluation, inputs, Decimal("117200"), EUR_RSD, product_match=product_match
    )
    assert opportunity.costs.intermediary_fee_eur == Decimal("15.00")


def test_deal_specific_fee_overrides_the_flat_rate(listing, evaluation, product_match):
    """A quoted fee wins over the policy default, so a one-off deal stays honest."""
    opportunity = build_opportunity(
        listing, evaluation, COSTS, Decimal("117200"), EUR_RSD, product_match=product_match
    )
    assert opportunity.costs.intermediary_fee_eur == Decimal("25.00")


def test_owner_policy_carries_the_flat_fee():
    assert OWNER_POLICY.intermediary_fee_eur == Decimal("15")


def test_domestic_buy_needs_no_intermediary_fee(listing, evaluation, product_match):
    opportunity = build_opportunity(
        listing, evaluation, CHEAP, Decimal("117200"), EUR_RSD, product_match=product_match
    )
    assert opportunity.verdict is not Verdict.INSUFFICIENT_DATA
    assert opportunity.costs.intermediary_fee_eur == Decimal("0.00")


def test_calculation_version_records_policy(listing, evaluation, product_match):
    opportunity = build_opportunity(
        listing, evaluation, COSTS, Decimal("117200"), EUR_RSD, product_match=product_match
    )
    assert opportunity.provenance.calculation_version == "calc-v2/policy-v3"


def test_inverted_rate_keeps_the_timestamp_and_names_its_source():
    from src.pricing.fx import inverted

    flipped = inverted(EUR_RSD)

    assert flipped.base_currency == "RSD"
    assert flipped.quote_currency == "EUR"
    assert flipped.observed_at == EUR_RSD.observed_at
    assert "derived from EUR/RSD" in flipped.source
    # Round-trip through the inverse must land back on the original amount.
    from src.core.money import Money

    original = Money.of(Decimal("100"), "EUR")
    assert EUR_RSD.convert(original).amount * flipped.rate == original.amount


def test_rate_to_eur_prefers_an_observed_pair_over_the_inverse():
    from src.pricing.fx import rate_to_eur

    direct = FxRate(
        base_currency="RSD",
        quote_currency="EUR",
        rate=Decimal("0.0085"),
        observed_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
        source="test-direct",
    )
    assert rate_to_eur("RSD", [EUR_RSD, direct]).source == "test-direct"
    assert "derived from" in rate_to_eur("RSD", [EUR_RSD]).source


def test_rsd_listing_is_priced_through_the_inverse_rate(listing, evaluation, product_match):
    from src.pricing.fx import inverted

    rsd_listing = listing.model_copy(
        update={"price_amount": Decimal("70000"), "currency": "RSD"}
    )
    opportunity = build_opportunity(
        rsd_listing,
        evaluation,
        COSTS,
        Decimal("117200"),
        EUR_RSD,
        purchase_fx=inverted(EUR_RSD),
        product_match=product_match,
    )

    assert opportunity.verdict is not Verdict.INSUFFICIENT_DATA
    # 70000 RSD / 117.20 = 597.27 EUR
    assert opportunity.costs.purchase_eur == Decimal("597.27")


def _eur_estimate(amount: str = "780") -> "ResaleEstimate":
    from src.core.models import PriceBasis, ResaleEstimate

    return ResaleEstimate(
        product_id="rtx-3090",
        condition=Condition.USED,
        currency="EUR",
        resale_conservative=Decimal(amount),
        resale_expected=Decimal(amount),
        resale_optimistic=Decimal(amount),
        price_basis=PriceBasis.ASKING,
        sample_size=6,
        confidence=Decimal("0.55"),
    )


def test_eur_estimate_is_used_as_is_without_fx(listing, evaluation, product_match):
    """D-013: a resale estimate already in EUR needs no EUR/RSD rate."""
    opportunity = build_opportunity(
        listing, evaluation, COSTS, _eur_estimate("780"), eur_rsd=None,
        product_match=product_match,
    )

    assert opportunity.verdict is not Verdict.INSUFFICIENT_DATA
    assert opportunity.expected_sale_eur == Decimal("780.00")
    # No dinar figure was observed, so none is reported (UNKNOWN is not 0).
    assert opportunity.expected_sale_rsd is None


def test_rsd_estimate_still_requires_the_rate(listing, evaluation, product_match):
    from src.core.models import PriceBasis, ResaleEstimate

    rsd = ResaleEstimate(
        product_id="rtx-3090",
        condition=Condition.USED,
        currency="RSD",
        resale_expected=Decimal("99000"),
        price_basis=PriceBasis.ASKING,
        sample_size=6,
        confidence=Decimal("0.55"),
    )
    opportunity = build_opportunity(
        listing, evaluation, COSTS, rsd, eur_rsd=None, product_match=product_match
    )

    assert opportunity.verdict is Verdict.INSUFFICIENT_DATA
    assert "fx_eur_rsd" in opportunity.missing_inputs


def test_rsd_listing_still_requires_the_rate_even_with_a_eur_estimate(
    listing, evaluation, product_match
):
    rsd_listing = listing.model_copy(
        update={"price_amount": Decimal("70000"), "currency": "RSD"}
    )
    opportunity = build_opportunity(
        rsd_listing, evaluation, COSTS, _eur_estimate("780"), eur_rsd=None,
        product_match=product_match,
    )

    assert opportunity.verdict is Verdict.INSUFFICIENT_DATA
    assert "fx_eur_rsd" in opportunity.missing_inputs
