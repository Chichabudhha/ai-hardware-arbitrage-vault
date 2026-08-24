"""Serbian resale price estimation — deterministic statistics, no AI.

Implements pricing/PRICING-ENGINE.md: filtered P25 / median / P75 over Serbian
observations, with every exclusion made by an explicit rule and logged.

Two rules carry most of the weight and are worth stating plainly:

1. Asking price is not sold price (CLAUDE.md principle 3). An asking price sits
   above what the card actually fetches by a margin nobody here has measured.
   Inventing a discount factor would violate principle 1, so instead an
   asking-only sample reports P25 — an *observed* value at the low end of the
   asking distribution — as `resale_expected`, and carries lower confidence.
   Once sold observations exist, the median of those becomes the expected value.

2. A thin or stale sample produces INSUFFICIENT_DATA, not a number with a
   caveat attached.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import median as _median

from src.core.models import (
    Condition,
    ExcludedObservation,
    PriceBasis,
    PriceObservation,
    PriceType,
    Provenance,
    ResaleEstimate,
)
from src.core.money import round_units

PRICING_VERSION = "pricing-v1"

SOLD_TYPES = frozenset({PriceType.SOLD, PriceType.COMPLETED})

# D-020: a dealer's list price or a manually-entered reference is not a peer
# market clearing price — it carries a margin (or an unknown basis) a private
# ASKING/SOLD observation doesn't. Mixing it into the percentile sample is the
# same error D-013 forbids for currency, just on seller type instead.
REFERENCE_TYPES = frozenset({PriceType.DEALER_REFERENCE, PriceType.MANUAL_REFERENCE})

# D-013: Serbian GPU listings are quoted in EUR at least as often as in RSD, so
# both are valid observation currencies. What stays forbidden is *mixing* them
# in one sample — a percentile over two currencies is arithmetic on unlike
# units. One currency is chosen per estimate and the rest are excluded by rule.
#
# D-018 widens the set: once markets are compared side by side, a Romanian
# market quoting RON is internally consistent and needs no conversion to be
# estimated on its own. Any well-formed currency code is therefore accepted;
# what is still refused is a *mixed* sample, and comparing two currencies
# without an observed rate.
_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")


def is_supported_currency(code: str | None) -> bool:
    """A currency is usable if it is a well-formed code, not if it is on a list."""
    return bool(code and _CURRENCY_CODE.match(code.upper()))


@dataclass(frozen=True)
class PricingRules:
    """Statistical parameters. Not money policy — these shape the sample.

    Defaults are conventional choices, not owner decisions: the 1.5x IQR fence
    is the standard Tukey rule, and the freshness window matches how fast the
    used GPU market moves. Change them here, not at the call site.
    """

    min_sample_size: int = 5
    max_age_days: int = 90
    iqr_fence: Decimal = Decimal("1.5")
    # Note: full_sample_size and max_age_days are divisors in _confidence.
    # Confidence starts from the basis and is adjusted from there.
    sold_base_confidence: Decimal = Decimal("0.80")
    mixed_base_confidence: Decimal = Decimal("0.65")
    asking_base_confidence: Decimal = Decimal("0.50")
    # A sample this size or larger earns the full size bonus.
    full_sample_size: int = 20
    # D-006: the Serbian resale benchmark is KupujemProdajem. An EU listing is
    # sourcing data, so it must never reach this sample — the guard matters now
    # that observed EU sale prices feed back into the store from paper trading.
    resale_marketplaces: frozenset[str] = frozenset({"kupujemprodajem"})
    size_bonus: Decimal = Decimal("0.15")
    # Spread penalty: how much confidence a fully dispersed sample costs.
    spread_penalty: Decimal = Decimal("0.20")
    # Freshness penalty at the far edge of the window.
    staleness_penalty: Decimal = Decimal("0.10")

    def __post_init__(self) -> None:
        # full_sample_size and max_age_days are divisors in _confidence; zero
        # there would crash mid-estimate rather than at configuration time.
        if self.full_sample_size <= 0:
            raise ValueError("full_sample_size must be positive")
        if self.max_age_days <= 0:
            raise ValueError("max_age_days must be positive")
        if self.min_sample_size < 1:
            raise ValueError("min_sample_size must be at least 1")
        if self.iqr_fence < 0:
            raise ValueError("iqr_fence must not be negative")


DEFAULT_RULES = PricingRules()


def percentile(values: list[Decimal], fraction: Decimal) -> Decimal:
    """Linear-interpolated percentile over a sorted copy of `values`.

    Written out rather than pulled from a library so the interpolation is
    visible: financial output must be reproducible from the source (principle 5).
    """
    if not values:
        raise ValueError("percentile of an empty sample")
    # Outside [0, 1] the interpolation silently extrapolates past the sample and
    # returns a price no observation supports — worse than failing loudly.
    if not (Decimal("0") <= fraction <= Decimal("1")):
        raise ValueError(f"percentile fraction must be within [0, 1], got {fraction}")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]

    position = (Decimal(len(ordered)) - 1) * fraction
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    weight = position - Decimal(lower_index)
    lower = ordered[lower_index]
    return lower + (ordered[upper_index] - lower) * weight


def _basis(observations: list[PriceObservation]) -> PriceBasis:
    sold = sum(1 for obs in observations if obs.price_type in SOLD_TYPES)
    if sold == len(observations):
        return PriceBasis.SOLD
    if sold == 0:
        return PriceBasis.ASKING
    return PriceBasis.MIXED


def _filter(
    observations: list[PriceObservation],
    product_id: str,
    condition: Condition,
    now: datetime,
    rules: PricingRules,
    sample_currency: str,
) -> tuple[list[PriceObservation], list[ExcludedObservation]]:
    """Apply the non-statistical rules from PRICING-ENGINE.md."""
    kept: list[PriceObservation] = []
    dropped: list[ExcludedObservation] = []
    cutoff = now - timedelta(days=rules.max_age_days)

    for obs in observations:
        reason: str | None = None
        if obs.product_id != product_id:
            reason = "different_product"
        elif obs.marketplace not in rules.resale_marketplaces:
            # Serbian resale is the benchmark; a foreign price says what a card
            # costs abroad, not what it fetches here (PRICING-ENGINE.md).
            reason = f"non_resale_marketplace:{obs.marketplace}"
        elif not is_supported_currency(obs.currency):
            # Not a currency code at all — a typo or a corrupt row, not a market.
            reason = f"unsupported_currency:{obs.currency}"
        elif obs.currency != sample_currency:
            # Not a bad observation — just not in this sample's currency.
            reason = f"currency_not_sample:{obs.currency}"
        elif obs.price_type in REFERENCE_TYPES:
            # D-020: dealer/manual reference prices are not peer market prices.
            reason = f"reference_price_not_peer:{obs.price_type.value}"
        elif obs.is_bundle:
            reason = "bundle_price_is_not_a_gpu_price"
        elif obs.condition is Condition.FOR_PARTS:
            reason = "for_parts"
        elif obs.condition is not condition:
            reason = f"condition_mismatch:{obs.condition.value}"
        elif obs.price_amount <= 0:
            reason = "non_positive_price"
        elif obs.observed_at < cutoff:
            reason = f"stale_over_{rules.max_age_days}_days"

        if reason:
            dropped.append(
                ExcludedObservation(
                    source_listing_id=obs.source_listing_id,
                    price_amount=obs.price_amount,
                    reason=reason,
                )
            )
        else:
            kept.append(obs)

    return kept, dropped


def _drop_outliers(
    observations: list[PriceObservation], rules: PricingRules
) -> tuple[list[PriceObservation], list[ExcludedObservation]]:
    """Tukey fence on the interquartile range, each exclusion logged.

    A single mispriced listing (a 3090 advertised at 1000 din to bait calls)
    otherwise drags the low quartile down and turns a bad deal into a BUY.
    """
    prices = [obs.price_amount for obs in observations]
    q1 = percentile(prices, Decimal("0.25"))
    q3 = percentile(prices, Decimal("0.75"))
    iqr = q3 - q1
    if iqr <= 0:
        return observations, []

    low = q1 - rules.iqr_fence * iqr
    high = q3 + rules.iqr_fence * iqr

    kept: list[PriceObservation] = []
    dropped: list[ExcludedObservation] = []
    for obs in observations:
        if obs.price_amount < low:
            reason = "outlier_below_iqr_fence"
        elif obs.price_amount > high:
            reason = "outlier_above_iqr_fence"
        else:
            kept.append(obs)
            continue
        dropped.append(
            ExcludedObservation(
                source_listing_id=obs.source_listing_id,
                price_amount=obs.price_amount,
                reason=reason,
            )
        )
    return kept, dropped


def _confidence(
    basis: PriceBasis,
    sample_size: int,
    p25: Decimal,
    p75: Decimal,
    med: Decimal,
    ages_days: list[int],
    rules: PricingRules,
) -> Decimal:
    """Deterministic confidence in [0, 1]. Every term is named in `explanation`."""
    if basis is PriceBasis.SOLD:
        score = rules.sold_base_confidence
    elif basis is PriceBasis.MIXED:
        score = rules.mixed_base_confidence
    else:
        score = rules.asking_base_confidence

    size_ratio = min(Decimal(sample_size) / Decimal(rules.full_sample_size), Decimal("1"))
    score += rules.size_bonus * size_ratio

    # Relative interquartile spread: a market that agrees is easier to predict.
    if med > 0:
        spread = min((p75 - p25) / med, Decimal("1"))
        score -= rules.spread_penalty * spread

    # Freshness: observations at the edge of the window count for less than
    # today's. Linear in the median age of the surviving sample.
    if ages_days:
        age_ratio = min(
            Decimal(int(_median(ages_days))) / Decimal(rules.max_age_days), Decimal("1")
        )
        score -= rules.staleness_penalty * age_ratio

    return max(Decimal("0"), min(Decimal("1"), score)).quantize(Decimal("0.01"))


def pick_sample_currency(
    observations: list[PriceObservation], product_id: str
) -> str:
    """Currency this product has most observations in. EUR wins a tie.

    Deterministic and explainable: the sample follows the market rather than a
    preference in code. The tie-break is EUR because that is what the Serbian
    GPU market quotes (D-013), and a tie has to break the same way every run.
    """
    counts: dict[str, int] = {}
    for obs in observations:
        if obs.product_id != product_id or not is_supported_currency(obs.currency):
            continue
        counts[obs.currency] = counts.get(obs.currency, 0) + 1
    if not counts:
        return "EUR"
    best = max(counts.values())
    return "EUR" if counts.get("EUR", 0) == best else max(counts, key=lambda c: counts[c])


def estimate_resale(
    observations: list[PriceObservation],
    product_id: str,
    condition: Condition = Condition.USED,
    now: datetime | None = None,
    rules: PricingRules = DEFAULT_RULES,
    currency: str | None = None,
) -> ResaleEstimate:
    """Estimate the Serbian resale price for one product in one condition.

    Returns an unusable estimate carrying `missing_inputs` when the sample
    cannot support a number — never a figure dressed up as a fact (CLAUDE.md §5).
    """
    now = now or datetime.now(timezone.utc)
    sample_currency = (currency or pick_sample_currency(observations, product_id)).upper()
    if not is_supported_currency(sample_currency):
        raise ValueError(f"sample currency must be a 3-letter code, got {sample_currency}")

    kept, excluded = _filter(observations, product_id, condition, now, rules, sample_currency)
    explanation = [
        f"{len(observations)} observations in, {len(excluded)} removed by rule",
        f"sample currency {sample_currency}",
    ]

    def unusable(reason: str) -> ResaleEstimate:
        return ResaleEstimate(
            product_id=product_id,
            condition=condition,
            currency=sample_currency,
            sample_size=len(kept),
            excluded=excluded,
            missing_inputs=[reason],
            explanation=explanation,
            provenance=_provenance(now, kept),
        )

    if not kept:
        return unusable("no_usable_observations")

    kept, outliers = _drop_outliers(kept, rules)
    excluded.extend(outliers)
    if outliers:
        explanation.append(f"{len(outliers)} removed as IQR outliers")

    if len(kept) < rules.min_sample_size:
        explanation.append(
            f"sample of {len(kept)} is below the minimum of {rules.min_sample_size}"
        )
        return unusable(f"sample_size_below_{rules.min_sample_size}")

    prices = [obs.price_amount for obs in kept]
    p25 = percentile(prices, Decimal("0.25"))
    med = percentile(prices, Decimal("0.50"))
    p75 = percentile(prices, Decimal("0.75"))
    basis = _basis(kept)

    if basis is PriceBasis.SOLD:
        expected = med
        explanation.append("sold observations: expected value is the median")
    else:
        # Principle 3: asking is not sold, and the gap is unmeasured. P25 is the
        # most defensible observed anchor until sold data exists.
        expected = p25
        explanation.append(
            "asking data present: expected value is P25, not the median, because "
            "the asking-to-sold gap is unmeasured"
        )

    ages = [max((now - obs.observed_at).days, 0) for obs in kept]
    confidence = _confidence(basis, len(kept), p25, p75, med, ages, rules)
    explanation.append(f"basis={basis.value}, n={len(kept)}, median age {int(_median(ages))}d")

    return ResaleEstimate(
        product_id=product_id,
        condition=condition,
        currency=sample_currency,
        resale_conservative=round_units(p25),
        resale_expected=round_units(expected),
        resale_optimistic=round_units(p75),
        p25=round_units(p25),
        median=round_units(med),
        p75=round_units(p75),
        price_basis=basis,
        sample_size=len(kept),
        confidence=confidence,
        excluded=excluded,
        explanation=explanation,
        provenance=_provenance(now, kept),
    )


def _provenance(now: datetime, used: list[PriceObservation]) -> Provenance:
    marketplaces = sorted({obs.marketplace for obs in used})
    return Provenance(
        source=",".join(marketplaces) if marketplaces else "none",
        observed_at=now,
        method="deterministic",
        calculation_version=PRICING_VERSION,
        input_refs=sorted(obs.source_listing_id for obs in used),
    )
