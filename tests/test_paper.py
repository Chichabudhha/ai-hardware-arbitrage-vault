"""W6 paper trading: records, append-only store, calibration report."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.core.models import PriceBasis, RiskLevel, Verdict
from src.paper.calibration import CalibrationRules, calibrate
from src.paper.records import (
    OutcomeType,
    PaperOutcome,
    PaperPrediction,
    prediction_from_opportunity,
    prediction_id,
)
from src.paper.store import (
    PaperStoreError,
    append_outcome,
    append_prediction,
    load_outcomes,
    load_predictions,
    pair_records,
)

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)

# Loose rules so a small fixture set can still produce an OK report; the real
# gate (100 candidates, 20 priced outcomes) is tested separately.
SMALL = CalibrationRules(target_candidates=1, min_priced_outcomes=1)


def prediction(
    listing_id: str = "kp-1",
    verdict: Verdict = Verdict.BUY,
    expected_sale_eur: str | None = "600",
    landed_cost_eur: str | None = "500",
    expected_profit_eur: str | None = "100",
    confidence: str | None = "0.55",
) -> PaperPrediction:
    return PaperPrediction(
        prediction_id=prediction_id("kupujemprodajem", listing_id, NOW),
        predicted_at=NOW,
        marketplace="kupujemprodajem",
        source_listing_id=listing_id,
        url=f"https://www.kupujemprodajem.com/{listing_id}",
        title="RTX 3090 24GB",
        product_id="rtx-3090",
        landed_cost_eur=Decimal(landed_cost_eur) if landed_cost_eur else None,
        expected_sale_eur=Decimal(expected_sale_eur) if expected_sale_eur else None,
        expected_profit_eur=Decimal(expected_profit_eur) if expected_profit_eur else None,
        roi=Decimal("0.20"),
        price_basis=PriceBasis.ASKING,
        pricing_confidence=Decimal(confidence) if confidence else None,
        pricing_sample_size=8,
        risk_level=RiskLevel.LOW,
        verdict=verdict,
    )


def sold(pred: PaperPrediction, price_eur: str, days: int = 10) -> PaperOutcome:
    return PaperOutcome(
        prediction_id=pred.prediction_id,
        outcome=OutcomeType.SOLD,
        observed_at=NOW,
        actual_sale_eur=Decimal(price_eur),
        days_listed=days,
    )


# --- records ----------------------------------------------------------------


def test_prediction_id_is_stable_and_readable():
    made = prediction_id("kupujemprodajem", "kp-1", NOW)
    assert made == "kupujemprodajem:kp-1:20260819T120000Z"
    assert made == prediction_id("kupujemprodajem", "kp-1", NOW)


def test_prediction_snapshots_the_opportunity(listing, evaluation, product_match):
    from src.pricing.calculator import CostInputs, build_opportunity
    from src.core.money import FxRate

    fx = FxRate(
        base_currency="EUR",
        quote_currency="RSD",
        rate=Decimal("117"),
        observed_at=NOW,
        source="test",
    )
    opportunity = build_opportunity(
        listing=listing,
        evaluation=evaluation,
        cost_inputs=CostInputs(
            shipping_eur=Decimal("20"), import_buffer_eur=Decimal("30"), is_import=True
        ),
        expected_sale_rsd=Decimal("110000"),
        eur_rsd=fx,
        product_match=product_match,
    )
    record = prediction_from_opportunity(
        opportunity, product_id=product_match.product_id, match_status="matched"
    )

    assert record.verdict is opportunity.verdict
    assert record.expected_profit_eur == opportunity.expected_profit_eur
    assert record.landed_cost_eur == opportunity.costs.landed_cost_eur
    assert record.source_listing_id == listing.source_listing_id
    assert record.calculation_version  # provenance travels with the prediction


def test_unsold_outcome_cannot_carry_a_price():
    with pytest.raises(ValueError, match="cannot carry a sale price"):
        PaperOutcome(
            prediction_id="x",
            outcome=OutcomeType.DELISTED,
            observed_at=NOW,
            actual_sale_eur=Decimal("500"),
        )


def test_negative_sale_price_is_rejected():
    with pytest.raises(ValueError, match="must be > 0"):
        PaperOutcome(
            prediction_id="x",
            outcome=OutcomeType.SOLD,
            observed_at=NOW,
            actual_sale_eur=Decimal("-1"),
        )


# --- store ------------------------------------------------------------------


def test_store_round_trip(tmp_path):
    path = tmp_path / "predictions.jsonl"
    record = prediction()
    append_prediction(record, path)
    append_prediction(prediction("kp-2"), path)

    loaded = load_predictions(path)
    assert [p.source_listing_id for p in loaded] == ["kp-1", "kp-2"]
    assert loaded[0].expected_profit_eur == record.expected_profit_eur


def test_missing_store_is_an_error(tmp_path):
    with pytest.raises(PaperStoreError, match="no paper store"):
        load_predictions(tmp_path / "nothing.jsonl")


def test_malformed_line_raises_instead_of_being_skipped(tmp_path):
    path = tmp_path / "predictions.jsonl"
    append_prediction(prediction(), path)
    path.write_text(path.read_text(encoding="utf-8") + "{not json}\n", encoding="utf-8")

    with pytest.raises(PaperStoreError):
        load_predictions(path)


def test_outcome_for_unknown_prediction_raises():
    pred = prediction()
    stray = PaperOutcome(
        prediction_id="kupujemprodajem:kp-999:20260819T120000Z",
        outcome=OutcomeType.UNSOLD,
        observed_at=NOW,
    )
    with pytest.raises(PaperStoreError, match="unknown prediction_id"):
        pair_records([pred], [stray])


def test_latest_outcome_wins_but_the_earlier_line_stays(tmp_path):
    path = tmp_path / "outcomes.jsonl"
    pred = prediction()
    first = PaperOutcome(
        prediction_id=pred.prediction_id, outcome=OutcomeType.UNSOLD, observed_at=NOW
    )
    later = sold(pred, "590")
    later = later.model_copy(update={"observed_at": datetime(2026, 9, 1, tzinfo=timezone.utc)})
    append_outcome(first, path)
    append_outcome(later, path)

    stored = load_outcomes(path)
    assert len(stored) == 2  # append-only: nothing was overwritten
    pairs = pair_records([pred], stored)
    assert pairs[0][1].outcome is OutcomeType.SOLD


# --- calibration ------------------------------------------------------------


def test_overestimate_has_a_positive_signed_error():
    pred = prediction(expected_sale_eur="660")
    report = calibrate([(pred, sold(pred, "600"))], rules=SMALL)

    assert report.priced_outcomes == 1
    assert report.median_signed_pct_error == Decimal("0.1000")
    assert report.median_abs_pct_error == Decimal("0.1000")
    assert report.within_close_pct == 1
    assert report.failure_modes.get("resale_overestimate") is None


def test_large_overestimate_is_a_failure_mode():
    pred = prediction(expected_sale_eur="750")
    report = calibrate([(pred, sold(pred, "500"))], rules=SMALL)

    assert report.failure_modes["resale_overestimate"] == 1
    assert report.within_large_pct == 0


def test_buy_that_would_not_have_paid_off_is_a_false_positive():
    # Landed cost 500, actual sale 520: 20 EUR profit, below the 50 EUR floor.
    pred = prediction(verdict=Verdict.BUY)
    report = calibrate([(pred, sold(pred, "520"))], rules=SMALL)

    assert report.false_positives == 1
    assert report.false_negatives == 0
    assert report.false_positive_ids == [pred.prediction_id]
    assert report.median_realized_roi == Decimal("0.0400")


def test_skip_that_would_have_paid_off_is_a_false_negative():
    pred = prediction(verdict=Verdict.SKIP)
    report = calibrate([(pred, sold(pred, "700"))], rules=SMALL)

    assert report.false_negatives == 1
    assert report.failure_modes["missed_opportunity"] == 1


def test_delisted_outcome_never_enters_the_error_statistics():
    pred = prediction()
    outcome = PaperOutcome(
        prediction_id=pred.prediction_id, outcome=OutcomeType.DELISTED, observed_at=NOW
    )
    report = calibrate([(pred, outcome)], rules=SMALL)

    assert report.outcomes_total == 1
    assert report.priced_outcomes == 0
    assert report.median_abs_pct_error is None
    assert report.failure_modes["delisted_without_price"] == 1
    assert report.status == "INSUFFICIENT_DATA"


def test_thin_sample_reports_insufficient_data():
    pred = prediction()
    report = calibrate([(pred, sold(pred, "600"))])

    assert report.status == "INSUFFICIENT_DATA"
    assert report.missing_inputs == ["candidates:1<100", "priced_outcomes:1<20"]


def test_unscored_candidate_counts_as_a_failure_mode():
    pred = prediction(verdict=Verdict.INSUFFICIENT_DATA, expected_sale_eur=None)
    report = calibrate([(pred, None)], rules=SMALL)

    assert report.candidates_total == 1
    assert report.candidates_scored == 0
    assert report.failure_modes["insufficient_data_candidate"] == 1
    assert report.verdict_counts["INSUFFICIENT_DATA"] == 1


def test_errors_are_grouped_by_confidence_band():
    low = prediction("kp-1", confidence="0.50", expected_sale_eur="660")
    high = prediction("kp-2", confidence="0.85", expected_sale_eur="606")
    report = calibrate(
        [(low, sold(low, "600")), (high, sold(high, "600"))],
        rules=SMALL,
    )

    bands = {band.band: band for band in report.by_confidence if band.priced_outcomes}
    assert bands["0.50-0.65"].median_abs_pct_error == Decimal("0.1000")
    assert bands["0.80-1.00"].median_abs_pct_error == Decimal("0.0100")


def test_median_days_to_sell_uses_sold_outcomes_only():
    first = prediction("kp-1")
    second = prediction("kp-2")
    unsold = PaperOutcome(
        prediction_id=second.prediction_id,
        outcome=OutcomeType.UNSOLD,
        observed_at=NOW,
        days_listed=90,
    )
    report = calibrate(
        [(first, sold(first, "600", days=14)), (second, unsold)],
        rules=SMALL,
    )

    assert report.median_days_to_sell == 14


def test_report_is_reproducible():
    pred = prediction()
    pairs = [(pred, sold(pred, "610"))]
    first = calibrate(pairs, rules=SMALL, now=NOW)
    second = calibrate(pairs, rules=SMALL, now=NOW)

    assert first.model_dump_json() == second.model_dump_json()


def test_roi_at_the_floor_is_compared_before_rounding():
    # Landed cost 1000, sale 1179.99 -> ROI 0.17999, below the 0.18 BUY floor.
    # Rounding to four places first would read 0.1800 and hide the false positive.
    pred = prediction(
        verdict=Verdict.BUY,
        landed_cost_eur="1000",
        expected_sale_eur="1200",
        expected_profit_eur="200",
    )
    report = calibrate([(pred, sold(pred, "1179.99"))], rules=SMALL)

    assert report.false_positives == 1


def test_median_days_to_sell_rounds_half_up():
    first = prediction("kp-1")
    second = prediction("kp-2")
    report = calibrate(
        [(first, sold(first, "600", days=1)), (second, sold(second, "600", days=2))],
        rules=SMALL,
    )

    assert report.median_days_to_sell == 2


# --- watchlist --------------------------------------------------------------


def test_watchlist_keeps_everything_without_a_terminal_outcome():
    from src.paper.store import open_watchlist

    sold_one = prediction("kp-1")
    cut_one = prediction("kp-2")
    open_one = prediction("kp-3")
    pairs = [
        (sold_one, sold(sold_one, "600")),
        (
            cut_one,
            PaperOutcome(
                prediction_id=cut_one.prediction_id,
                outcome=OutcomeType.PRICE_CUT,
                observed_at=NOW,
                new_asking_amount=Decimal("560"),
                new_asking_currency="EUR",
            ),
        ),
        (open_one, None),
    ]
    watched = [p.source_listing_id for p, _ in open_watchlist(pairs)]

    # A sale is a conclusion; a price cut is not.
    assert "kp-1" not in watched
    assert watched == ["kp-2", "kp-3"]


def test_watchlist_drops_delisted_but_keeps_unsold():
    from src.paper.store import open_watchlist

    gone = prediction("kp-1")
    still = prediction("kp-2")
    pairs = [
        (
            gone,
            PaperOutcome(
                prediction_id=gone.prediction_id,
                outcome=OutcomeType.DELISTED,
                observed_at=NOW,
            ),
        ),
        (
            still,
            PaperOutcome(
                prediction_id=still.prediction_id,
                outcome=OutcomeType.UNSOLD,
                observed_at=NOW,
            ),
        ),
    ]
    assert [p.source_listing_id for p, _ in open_watchlist(pairs)] == ["kp-2"]


def test_watchlist_is_ordered_oldest_first():
    from datetime import timedelta

    from src.paper.store import open_watchlist

    newer = prediction("kp-new")
    older = prediction("kp-old").model_copy(update={"predicted_at": NOW - timedelta(days=9)})

    order = [p.source_listing_id for p, _ in open_watchlist([(newer, None), (older, None)])]
    assert order == ["kp-old", "kp-new"]


# --- price cut --------------------------------------------------------------


def test_new_asking_price_belongs_only_to_a_price_cut():
    with pytest.raises(ValueError, match="belongs to a PRICE_CUT"):
        PaperOutcome(
            prediction_id="x",
            outcome=OutcomeType.UNSOLD,
            observed_at=NOW,
            new_asking_amount=Decimal("500"),
            new_asking_currency="EUR",
        )


def test_new_asking_price_needs_a_currency():
    with pytest.raises(ValueError, match="requires new_asking_currency"):
        PaperOutcome(
            prediction_id="x",
            outcome=OutcomeType.PRICE_CUT,
            observed_at=NOW,
            new_asking_amount=Decimal("500"),
        )


def test_a_price_cut_is_not_a_sale():
    """A lowered asking price must never be read as what the card fetched."""
    cut = PaperOutcome(
        prediction_id="x",
        outcome=OutcomeType.PRICE_CUT,
        observed_at=NOW,
        new_asking_amount=Decimal("500"),
        new_asking_currency="EUR",
    )
    assert cut.has_price is False
    assert cut.actual_sale_eur is None
