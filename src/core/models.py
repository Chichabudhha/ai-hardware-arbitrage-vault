"""Canonical models (subset of data/DATA-MODEL.md needed for HA-002 phase 1).

Raw observations are immutable: a new price produces a new observation, it never
overwrites an existing one (CLAUDE.md principle 6).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AutomationStatus(str, Enum):
    RESEARCH = "RESEARCH"
    MANUAL = "MANUAL"
    API_FEED = "API_FEED"
    AUTOMATED = "AUTOMATED"


class PriceType(str, Enum):
    ASKING = "asking"
    SOLD = "sold"
    COMPLETED = "completed"
    DEALER_REFERENCE = "dealer_reference"
    MANUAL_REFERENCE = "manual_reference"


class Condition(str, Enum):
    NEW = "new"
    USED = "used"
    FOR_PARTS = "for_parts"
    UNKNOWN = "UNKNOWN"


class RiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class Verdict(str, Enum):
    BUY = "BUY"
    NEGOTIATE = "NEGOTIATE"
    WATCH = "WATCH"
    SKIP = "SKIP"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class Provenance(BaseModel):
    """Where a value came from and when. Required on every derived value."""

    model_config = ConfigDict(frozen=True)

    source: str
    observed_at: datetime
    method: str
    calculation_version: str | None = None
    input_refs: list[str] = Field(default_factory=list)


class RawObservation(BaseModel):
    """Immutable capture of what a source returned. Never rewritten."""

    model_config = ConfigDict(frozen=True)

    marketplace: str
    source_listing_id: str
    url: str
    fetched_at: datetime
    payload: str
    payload_hash: str
    access_method: AutomationStatus


class Listing(BaseModel):
    """Normalized listing. Structure extraction only — no interpretation."""

    model_config = ConfigDict(frozen=True)

    marketplace: str
    source_listing_id: str
    url: str
    title: str
    description: str | None = None
    price_amount: Decimal | None = None
    currency: str | None = None
    price_type: PriceType = PriceType.ASKING
    seller_name: str | None = None
    location: str | None = None
    observed_at: datetime
    raw_payload_hash: str | None = None
    provenance: Provenance | None = None

    def has_financial_minimum(self) -> bool:
        """Attributes required before any financial conclusion (CLAUDE.md §5)."""
        return all(
            [
                self.marketplace,
                self.source_listing_id,
                self.observed_at,
                self.currency,
                self.price_amount is not None,
            ]
        )


class GpuSpec(BaseModel):
    """Product facts extracted from unstructured listing text by the LLM."""

    model_config = ConfigDict(frozen=True)

    gpu_chip: str | None = None
    vram_gb: int | None = None
    brand: str | None = None
    quantity: int = 1
    match_confidence: float = 0.0


class RiskFlag(str, Enum):
    MINING_USE = "mining_use"
    NO_WARRANTY = "no_warranty"
    NO_PACKAGING = "no_packaging"
    PHYSICAL_DAMAGE = "physical_damage"
    UNTESTED = "untested"
    SUSPICIOUS_SELLER = "suspicious_seller"
    BULK_LIQUIDATION = "bulk_liquidation"
    PRICE_TOO_GOOD = "price_too_good"
    REMOTE_PAYMENT_ONLY = "remote_payment_only"


class MatchStatus(str, Enum):
    """Conflict states from product-intelligence/PRODUCT-INTELLIGENCE.md."""

    MATCHED = "MATCHED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    CONFLICT = "CONFLICT"
    UNMATCHED = "UNMATCHED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class Product(BaseModel):
    """One canonical catalog entry. Never inferred from a listing."""

    model_config = ConfigDict(frozen=True)

    product_id: str
    category: str = "GPU"
    manufacturer: str = "NVIDIA"
    family: str
    model: str
    variant: str | None = None
    vram_gb: int
    architecture: str
    canonical_name: str

    @property
    def ai_relevance_score(self) -> Decimal:
        """Derived from VRAM, not hand-assigned.

        For local LLM inference, usable model size is dominated by VRAM, so the
        score is a documented function of it rather than an invented constant.
        Revisit only via a decision in odluke/.
        """
        if self.vram_gb >= 48:
            return Decimal("1.0")
        if self.vram_gb >= 24:
            return Decimal("0.9")
        if self.vram_gb >= 16:
            return Decimal("0.6")
        return Decimal("0.3")


class ProductMatch(BaseModel):
    """Deterministic listing -> product link. Never silently forced."""

    model_config = ConfigDict(frozen=True)

    product_id: str | None
    status: MatchStatus
    confidence: Decimal
    method: str
    matched_at: datetime
    candidate_ids: list[str] = Field(default_factory=list)
    stated_vram_gb: int | None = None
    notes: str | None = None

    @property
    def is_usable(self) -> bool:
        """Only a clean match may feed a financial conclusion."""
        return self.status is MatchStatus.MATCHED


class Evaluation(BaseModel):
    """LLM interpretation of one listing. Contains no money math (D-005)."""

    model_config = ConfigDict(frozen=True)

    spec: GpuSpec
    condition: Condition = Condition.UNKNOWN
    has_warranty: bool | None = None
    warranty_notes: str | None = None
    seller_notes: str | None = None
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    risk_notes: str | None = None
    provenance: Provenance | None = None


class CostBreakdown(BaseModel):
    """Deterministic landed-cost components, all in EUR."""

    model_config = ConfigDict(frozen=True)

    purchase_eur: Decimal
    shipping_eur: Decimal
    import_buffer_eur: Decimal
    risk_reserve_eur: Decimal
    # D-010: sourcing from the EU runs through an intermediary who charges a
    # fee. Domestic buys have no intermediary, so 0 here is a fact, not UNKNOWN.
    intermediary_fee_eur: Decimal = Decimal("0")

    @property
    def landed_cost_eur(self) -> Decimal:
        return (
            self.purchase_eur
            + self.shipping_eur
            + self.import_buffer_eur
            + self.intermediary_fee_eur
            + self.risk_reserve_eur
        )


class PriceBasis(str, Enum):
    """What kind of observations an estimate was built from.

    Asking prices are not sold prices (CLAUDE.md principle 3), so the basis
    travels with every estimate and caps its confidence.
    """

    SOLD = "SOLD"
    MIXED = "MIXED"
    ASKING = "ASKING"


class PriceObservation(BaseModel):
    """One observed Serbian market price for a canonical product.

    Immutable like every raw observation (principle 6): a new price for the same
    listing is a new observation, never an edit of this one.
    """

    model_config = ConfigDict(frozen=True)

    product_id: str
    price_amount: Decimal
    currency: str
    price_type: PriceType
    condition: Condition
    observed_at: datetime
    marketplace: str
    source_listing_id: str
    url: str | None = None
    is_bundle: bool = False
    provenance: Provenance | None = None


class ExcludedObservation(BaseModel):
    """An observation dropped from an estimate, with the rule that dropped it.

    PRICING-ENGINE.md requires exclusions to be by rule and logged, so a
    discarded price is auditable rather than invisible.
    """

    model_config = ConfigDict(frozen=True)

    source_listing_id: str
    price_amount: Decimal
    reason: str


class ResaleEstimate(BaseModel):
    """Serbian resale estimate for one product/condition, in RSD."""

    model_config = ConfigDict(frozen=True)

    product_id: str
    condition: Condition
    currency: str = "RSD"
    resale_conservative: Decimal | None = None
    resale_expected: Decimal | None = None
    resale_optimistic: Decimal | None = None
    p25: Decimal | None = None
    median: Decimal | None = None
    p75: Decimal | None = None
    price_basis: PriceBasis | None = None
    sample_size: int = 0
    confidence: Decimal = Decimal("0")
    excluded: list[ExcludedObservation] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    explanation: list[str] = Field(default_factory=list)
    provenance: Provenance | None = None

    @property
    def is_usable(self) -> bool:
        """False means INSUFFICIENT_DATA — never a number presented as fact."""
        return self.resale_expected is not None and not self.missing_inputs


class Opportunity(BaseModel):
    """Deterministic scoring output. Verdict is advisory only — never auto-buy (D-003)."""

    model_config = ConfigDict(frozen=True)

    listing: Listing
    evaluation: Evaluation | None = None
    costs: CostBreakdown | None = None
    expected_sale_rsd: Decimal | None = None
    expected_sale_eur: Decimal | None = None
    price_basis: PriceBasis | None = None
    pricing_confidence: Decimal | None = None
    pricing_sample_size: int | None = None
    expected_profit_eur: Decimal | None = None
    roi: Decimal | None = None
    risk_level: RiskLevel = RiskLevel.HIGH
    verdict: Verdict = Verdict.INSUFFICIENT_DATA
    missing_inputs: list[str] = Field(default_factory=list)
    provenance: Provenance | None = None


def json_safe(value: Any) -> Any:
    """Serialize Decimal as string so precision survives round-trips."""
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"not JSON serializable: {type(value)}")
