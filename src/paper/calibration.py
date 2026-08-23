"""Calibration report — how wrong the engine was, measured on observed outcomes.

Implements operations/PAPER-TRADING.md. Nothing here estimates anything: every
number is computed from a stored prediction and an observed outcome. A pair with
no observed sale price contributes to the counts and the failure modes, never to
the error statistics — a delisted card has an UNKNOWN sale price, not a zero
(CLAUDE.md principle 2).

Realized ROI is hypothetical by construction: no card was bought, so it is
measured against the landed cost the engine predicted at scoring time. It
answers "would this purchase have paid off at the price the market actually
gave", not "what did we earn".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from statistics import median as _median

from pydantic import BaseModel, ConfigDict, Field

from src.core.models import Verdict
from src.core.policy import OWNER_POLICY, Policy
from src.paper.records import OutcomeType, PaperOutcome, PaperPrediction

CALIBRATION_VERSION = "calibration-v1"

PCT = Decimal("0.0001")


@dataclass(frozen=True)
class CalibrationRules:
    """Reporting parameters. Not money policy — these shape the report, not a verdict.

    The BUY floors used for false positives and negatives come from
    `src.core.policy`, never from here.
    """

    # operations/PAPER-TRADING.md: at least 100 candidates before real buying.
    target_candidates: int = 100
    # Below this many priced outcomes a median error is noise, not a measurement.
    min_priced_outcomes: int = 20
    # Diagnostic label boundaries, not thresholds that decide money.
    large_error_pct: Decimal = Decimal("0.20")
    close_error_pct: Decimal = Decimal("0.10")
    confidence_bands: tuple[tuple[str, Decimal, Decimal], ...] = (
        ("0.00-0.50", Decimal("0"), Decimal("0.50")),
        ("0.50-0.65", Decimal("0.50"), Decimal("0.65")),
        ("0.65-0.80", Decimal("0.65"), Decimal("0.80")),
        ("0.80-1.00", Decimal("0.80"), Decimal("1.00")),
    )


class BandStats(BaseModel):
    """Error statistics for one confidence band."""

    model_config = ConfigDict(frozen=True)

    band: str
    priced_outcomes: int = 0
    median_abs_pct_error: Decimal | None = None
    median_signed_pct_error: Decimal | None = None


class CalibrationReport(BaseModel):
    """Deterministic accuracy report over stored paper trades."""

    model_config = ConfigDict(frozen=True)

    generated_at: datetime
    calibration_version: str = CALIBRATION_VERSION
    policy_version: str = OWNER_POLICY.version

    candidates_total: int = 0
    candidates_scored: int = 0
    verdict_counts: dict[str, int] = Field(default_factory=dict)

    outcomes_total: int = 0
    outcome_counts: dict[str, int] = Field(default_factory=dict)
    priced_outcomes: int = 0

    # Resale estimate error. Positive = the engine expected more than the market
    # actually paid (overestimate).
    median_abs_pct_error: Decimal | None = None
    median_signed_pct_error: Decimal | None = None
    within_close_pct: int = 0
    within_large_pct: int = 0

    median_profit_error_eur: Decimal | None = None
    median_realized_roi: Decimal | None = None

    false_positives: int = 0
    false_negatives: int = 0
    false_positive_ids: list[str] = Field(default_factory=list)
    false_negative_ids: list[str] = Field(default_factory=list)

    by_confidence: list[BandStats] = Field(default_factory=list)
    median_days_to_sell: int | None = None

    failure_modes: dict[str, int] = Field(default_factory=dict)
    status: str = "INSUFFICIENT_DATA"
    missing_inputs: list[str] = Field(default_factory=list)

    @property
    def is_usable(self) -> bool:
        return self.status == "OK"


def _median_decimal(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return Decimal(_median(sorted(values))).quantize(PCT)


def calibrate(
    pairs: list[tuple[PaperPrediction, PaperOutcome | None]],
    rules: CalibrationRules | None = None,
    policy: Policy = OWNER_POLICY,
    now: datetime | None = None,
) -> CalibrationReport:
    """Measure prediction error over paired predictions and outcomes."""
    rules = rules or CalibrationRules()
    generated_at = now or datetime.now(timezone.utc)

    verdict_counts: dict[str, int] = {}
    outcome_counts: dict[str, int] = {}
    failure_modes: dict[str, int] = {}

    abs_errors: list[Decimal] = []
    signed_errors: list[Decimal] = []
    profit_errors: list[Decimal] = []
    realized_rois: list[Decimal] = []
    days_to_sell: list[int] = []
    band_errors: dict[str, list[tuple[Decimal, Decimal]]] = {
        name: [] for name, _, _ in rules.confidence_bands
    }
    unbanded: list[tuple[Decimal, Decimal]] = []

    false_positive_ids: list[str] = []
    false_negative_ids: list[str] = []
    close_hits = 0
    large_hits = 0
    scored = 0

    def bump(counter: dict[str, int], key: str) -> None:
        counter[key] = counter.get(key, 0) + 1

    for prediction, outcome in pairs:
        bump(verdict_counts, prediction.verdict.value)
        if prediction.is_scored:
            scored += 1
        else:
            bump(failure_modes, "insufficient_data_candidate")

        if outcome is None:
            continue
        bump(outcome_counts, outcome.outcome.value)

        if outcome.outcome is OutcomeType.DELISTED:
            bump(failure_modes, "delisted_without_price")
        elif outcome.outcome is OutcomeType.UNSOLD:
            bump(failure_modes, "unsold_after_window")
        elif outcome.outcome is OutcomeType.PRICE_CUT:
            bump(failure_modes, "seller_cut_price")

        if outcome.days_listed is not None and outcome.outcome is OutcomeType.SOLD:
            days_to_sell.append(outcome.days_listed)

        if not outcome.has_price:
            continue
        if prediction.expected_sale_eur is None:
            # A sale was observed for a candidate the engine never priced: it
            # counts as an outcome, but there is no prediction to score.
            bump(failure_modes, "outcome_without_prediction_price")
            continue

        actual = outcome.actual_sale_eur
        assert actual is not None
        signed = ((prediction.expected_sale_eur - actual) / actual).quantize(PCT)
        signed_errors.append(signed)
        abs_errors.append(abs(signed))

        if abs(signed) <= rules.close_error_pct:
            close_hits += 1
        if abs(signed) <= rules.large_error_pct:
            large_hits += 1
        elif signed > 0:
            bump(failure_modes, "resale_overestimate")
        else:
            bump(failure_modes, "resale_underestimate")

        confidence = prediction.pricing_confidence
        placed = False
        if confidence is not None:
            for name, low, high in rules.confidence_bands:
                # Bands are half-open except the last, so 1.00 lands somewhere.
                if low <= confidence < high or (high == Decimal("1.00") and confidence == high):
                    band_errors[name].append((abs(signed), signed))
                    placed = True
                    break
        if not placed:
            unbanded.append((abs(signed), signed))

        if prediction.landed_cost_eur is None or prediction.landed_cost_eur <= 0:
            continue
        realized_profit = actual - prediction.landed_cost_eur
        # Compare against the policy floors at full precision and round only for
        # reporting: a ROI of 0.17999 must not become a pass by way of display
        # rounding.
        realized_roi = realized_profit / prediction.landed_cost_eur
        realized_rois.append(realized_roi.quantize(PCT))
        if prediction.expected_profit_eur is not None:
            profit_errors.append(
                (prediction.expected_profit_eur - realized_profit).quantize(Decimal("0.01"))
            )

        would_buy = (
            realized_roi >= policy.buy_min_roi and realized_profit >= policy.min_profit_eur
        )
        if prediction.verdict is Verdict.BUY and not would_buy:
            false_positive_ids.append(prediction.prediction_id)
            bump(failure_modes, "buy_below_floors")
        elif prediction.verdict in (Verdict.SKIP, Verdict.WATCH) and would_buy:
            false_negative_ids.append(prediction.prediction_id)
            bump(failure_modes, "missed_opportunity")

    if unbanded:
        band_errors.setdefault("no_confidence", []).extend(unbanded)

    bands = [
        BandStats(
            band=name,
            priced_outcomes=len(entries),
            median_abs_pct_error=_median_decimal([abs_e for abs_e, _ in entries]),
            median_signed_pct_error=_median_decimal([signed for _, signed in entries]),
        )
        for name, entries in band_errors.items()
    ]

    missing: list[str] = []
    priced = len(abs_errors)
    if len(pairs) < rules.target_candidates:
        missing.append(f"candidates:{len(pairs)}<{rules.target_candidates}")
    if priced < rules.min_priced_outcomes:
        missing.append(f"priced_outcomes:{priced}<{rules.min_priced_outcomes}")

    return CalibrationReport(
        generated_at=generated_at,
        candidates_total=len(pairs),
        candidates_scored=scored,
        verdict_counts=verdict_counts,
        outcomes_total=sum(outcome_counts.values()),
        outcome_counts=outcome_counts,
        priced_outcomes=priced,
        median_abs_pct_error=_median_decimal(abs_errors),
        median_signed_pct_error=_median_decimal(signed_errors),
        within_close_pct=close_hits,
        within_large_pct=large_hits,
        median_profit_error_eur=(
            Decimal(_median(sorted(profit_errors))).quantize(Decimal("0.01"))
            if profit_errors
            else None
        ),
        median_realized_roi=_median_decimal(realized_rois),
        false_positives=len(false_positive_ids),
        false_negatives=len(false_negative_ids),
        false_positive_ids=false_positive_ids,
        false_negative_ids=false_negative_ids,
        by_confidence=bands,
        median_days_to_sell=(
            # An even sample gives a .5 median; truncating it would always
            # report the market as faster than it was.
            int(Decimal(_median(sorted(days_to_sell))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            if days_to_sell
            else None
        ),
        failure_modes=failure_modes,
        status="INSUFFICIENT_DATA" if missing else "OK",
        missing_inputs=missing,
    )
