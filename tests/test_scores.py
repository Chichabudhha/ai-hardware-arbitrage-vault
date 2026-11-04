"""D-023: Deal Score, Confidence Score, liquidity proxy and resale friction."""

from dataclasses import replace
from decimal import Decimal

from src.core.models import Verdict
from src.core.policy import OWNER_POLICY
from src.deal_engine.scores import confidence_score, deal_score
from src.pricing.calculator import CostInputs, build_opportunity

from tests.test_pricing import _eur_estimate

IMPORT = CostInputs(shipping_eur=None, import_buffer_eur=None, is_import=True, source="test-fixture")


def test_deal_score_is_50_exactly_at_buy_thresholds():
    assert deal_score(Decimal("50"), Decimal("0.18")) == Decimal("50")


def test_deal_score_weaker_measure_decides():
    # ROI 4x the threshold, profit only at threshold -> profit decides.
    assert deal_score(Decimal("50"), Decimal("0.72")) == Decimal("50")
    # Profit 2x, ROI 0.5x -> ROI decides.
    assert deal_score(Decimal("100"), Decimal("0.09")) == Decimal("25")


def test_deal_score_is_clamped():
    assert deal_score(Decimal("1000"), Decimal("5")) == Decimal("100")
    assert deal_score(Decimal("-40"), Decimal("-0.1")) == Decimal("0")


def test_deal_score_unknown_without_inputs():
    assert deal_score(None, Decimal("0.2")) is None
    assert deal_score(Decimal("60"), None) is None


def test_confidence_score_is_the_weakest_link():
    assert confidence_score(Decimal("0.53"), Decimal("0.95")) == Decimal("0.53")
    assert confidence_score(Decimal("0.9"), Decimal("0.6")) == Decimal("0.60")
    assert confidence_score(None, Decimal("0.9")) is None


def test_opportunity_carries_scores_and_names_unpriced_friction(
    listing, evaluation, product_match
):
    opportunity = build_opportunity(
        listing, evaluation, IMPORT, _eur_estimate("1000"), eur_rsd=None,
        product_match=product_match,
    )
    assert opportunity.verdict is not Verdict.INSUFFICIENT_DATA
    assert opportunity.deal_score is not None
    assert opportunity.confidence_score == min(
        Decimal("0.55"), product_match.confidence
    ).quantize(Decimal("0.01"))
    assert opportunity.liquidity_sample_listings == 6
    # UNKNOWN, not 0 (principle 2): no sell-through yet, no friction figure.
    assert opportunity.liquidity_sell_through is None
    assert opportunity.resale_friction_eur is None
    assert opportunity.unpriced_costs == ["resale_friction"]


def test_approved_friction_is_subtracted_from_profit(listing, evaluation, product_match):
    base = build_opportunity(
        listing, evaluation, IMPORT, _eur_estimate("1000"), eur_rsd=None,
        product_match=product_match,
    )
    with_friction = build_opportunity(
        listing, evaluation, IMPORT, _eur_estimate("1000"), eur_rsd=None,
        product_match=product_match,
        policy=replace(OWNER_POLICY, resale_friction_eur=Decimal("20")),
    )
    assert with_friction.expected_profit_eur == base.expected_profit_eur - Decimal("20")
    assert with_friction.costs.landed_cost_eur == base.costs.landed_cost_eur
    assert with_friction.unpriced_costs == []


def test_insufficient_data_has_no_scores(listing, evaluation):
    opportunity = build_opportunity(listing, evaluation, IMPORT, None, None)
    assert opportunity.verdict is Verdict.INSUFFICIENT_DATA
    assert opportunity.deal_score is None
    assert opportunity.confidence_score is None


def test_old_prediction_records_still_load():
    from src.paper.store import load_predictions

    predictions = load_predictions("data/paper/predictions.jsonl")
    assert predictions
    assert all(p.deal_score is None for p in predictions if p.calculation_version
               and p.calculation_version.startswith("calc-v2"))
