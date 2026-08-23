"""Paper trading records — a prediction made before any purchase, and what the
market did afterwards.

Two rules shape this module:

1. A prediction is frozen at the moment it is made. It stores the numbers the
   engine produced *then*, including the calculation and policy versions, so a
   later change to the engine cannot quietly rewrite history (CLAUDE.md
   principle 6).
2. An outcome is an observation, not an estimate. If the card disappeared from
   the market without a visible price, the outcome is DELISTED with no amount —
   never a guessed sale price (principle 1, UNKNOWN != 0).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from src.core.models import Opportunity, PriceBasis, ResaleEstimate, RiskLevel, Verdict


class OutcomeType(str, Enum):
    """What the market did with the listing after the prediction."""

    SOLD = "SOLD"          # observed sold, with a price
    DELISTED = "DELISTED"  # gone from the market, sale price UNKNOWN
    UNSOLD = "UNSOLD"      # still listed at the end of the observation window
    PRICE_CUT = "PRICE_CUT"  # still listed, asking price lowered


def prediction_id(marketplace: str, source_listing_id: str, predicted_at: datetime) -> str:
    """Readable, greppable, stable id.

    The timestamp is part of the id on purpose: the same listing may be scored
    again after new observations arrive, and both predictions must survive.
    """
    stamp = predicted_at.strftime("%Y%m%dT%H%M%SZ")
    return f"{marketplace}:{source_listing_id}:{stamp}"


class PaperPrediction(BaseModel):
    """One scored candidate, recorded without buying anything (D-003)."""

    model_config = ConfigDict(frozen=True)

    prediction_id: str
    predicted_at: datetime
    marketplace: str
    source_listing_id: str
    url: str
    title: str
    product_id: str | None = None
    match_status: str | None = None

    listing_price_amount: Decimal | None = None
    listing_currency: str | None = None

    landed_cost_eur: Decimal | None = None
    expected_sale_rsd: Decimal | None = None
    expected_sale_eur: Decimal | None = None
    expected_profit_eur: Decimal | None = None
    roi: Decimal | None = None

    price_basis: PriceBasis | None = None
    pricing_confidence: Decimal | None = None
    pricing_sample_size: int | None = None

    risk_level: RiskLevel = RiskLevel.HIGH
    verdict: Verdict = Verdict.INSUFFICIENT_DATA
    missing_inputs: list[str] = Field(default_factory=list)
    calculation_version: str | None = None

    @property
    def is_scored(self) -> bool:
        """A candidate the engine could actually price."""
        return self.verdict is not Verdict.INSUFFICIENT_DATA


def prediction_from_opportunity(
    opportunity: Opportunity,
    product_id: str | None = None,
    match_status: str | None = None,
    predicted_at: datetime | None = None,
    estimate: ResaleEstimate | None = None,
) -> PaperPrediction:
    """Snapshot an Opportunity as a paper prediction. No money is recomputed here.

    `estimate` only fills in the pricing *metadata* — basis, confidence, sample
    size — which an INSUFFICIENT_DATA opportunity drops. The withheld resale
    number stays withheld: a candidate the engine refused to price must never
    look priced in the paper log.
    """
    listing = opportunity.listing
    stamped = predicted_at or (
        opportunity.provenance.observed_at if opportunity.provenance else listing.observed_at
    )
    return PaperPrediction(
        prediction_id=prediction_id(listing.marketplace, listing.source_listing_id, stamped),
        predicted_at=stamped,
        marketplace=listing.marketplace,
        source_listing_id=listing.source_listing_id,
        url=listing.url,
        title=listing.title,
        product_id=product_id,
        match_status=match_status,
        listing_price_amount=listing.price_amount,
        listing_currency=listing.currency,
        landed_cost_eur=opportunity.costs.landed_cost_eur if opportunity.costs else None,
        expected_sale_rsd=opportunity.expected_sale_rsd,
        expected_sale_eur=opportunity.expected_sale_eur,
        expected_profit_eur=opportunity.expected_profit_eur,
        roi=opportunity.roi,
        price_basis=opportunity.price_basis or (estimate.price_basis if estimate else None),
        pricing_confidence=(
            opportunity.pricing_confidence
            if opportunity.pricing_confidence is not None
            else (estimate.confidence if estimate else None)
        ),
        pricing_sample_size=(
            opportunity.pricing_sample_size
            if opportunity.pricing_sample_size is not None
            else (estimate.sample_size if estimate else None)
        ),
        risk_level=opportunity.risk_level,
        verdict=opportunity.verdict,
        missing_inputs=list(opportunity.missing_inputs),
        calculation_version=(
            opportunity.provenance.calculation_version if opportunity.provenance else None
        ),
    )


class PaperOutcome(BaseModel):
    """What was observed later. Every field here is observed, never derived."""

    model_config = ConfigDict(frozen=True)

    prediction_id: str
    outcome: OutcomeType
    observed_at: datetime
    # Only SOLD may carry an amount, and only if the price was actually visible.
    actual_sale_rsd: Decimal | None = None
    actual_sale_eur: Decimal | None = None
    eur_rsd_rate: Decimal | None = None
    # A price cut is an observed asking price, not a sale. Kept apart from the
    # sale fields so nothing can mistake "seller asks less now" for "it sold".
    new_asking_amount: Decimal | None = None
    new_asking_currency: str | None = None
    days_listed: int | None = None
    source: str = "manual"
    notes: str | None = None

    def model_post_init(self, _context: object) -> None:
        if self.outcome is not OutcomeType.SOLD and (
            self.actual_sale_rsd is not None or self.actual_sale_eur is not None
        ):
            raise ValueError(
                f"{self.outcome.value} outcome cannot carry a sale price; "
                "a price is only recorded when a sale was observed"
            )
        for name, value in (
            ("actual_sale_rsd", self.actual_sale_rsd),
            ("actual_sale_eur", self.actual_sale_eur),
            ("eur_rsd_rate", self.eur_rsd_rate),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be > 0, got {value}")
        if self.days_listed is not None and self.days_listed < 0:
            raise ValueError("days_listed must not be negative")
        if self.new_asking_amount is not None:
            if self.outcome is not OutcomeType.PRICE_CUT:
                raise ValueError(
                    "a new asking price belongs to a PRICE_CUT outcome; "
                    f"got {self.outcome.value}"
                )
            if self.new_asking_amount <= 0:
                raise ValueError("new_asking_amount must be > 0")
            if not self.new_asking_currency:
                raise ValueError("new_asking_amount requires new_asking_currency")

    @property
    def has_price(self) -> bool:
        return self.outcome is OutcomeType.SOLD and self.actual_sale_eur is not None
