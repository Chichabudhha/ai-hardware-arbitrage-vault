"""Landed cost, profit and ROI — deterministic Decimal math only.

    Net Profit = Target Resale Price (RS)
               - (Purchase + Shipping + Import/Customs Buffer + Risk Reserve)

Every input that is UNKNOWN produces INSUFFICIENT_DATA. Nothing defaults to 0
(CLAUDE.md principle 2, §5). Cost rules that depend on import regulations are
still open in PROGRESS.md — they must be supplied explicitly by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from src.core.models import (
    CostBreakdown,
    Evaluation,
    Listing,
    Opportunity,
    ProductMatch,
    Provenance,
    ResaleEstimate,
    RiskLevel,
    Verdict,
)
from src.core.money import FxRate, Money, round_money, round_units
from src.core.policy import OWNER_POLICY, Policy
from src.deal_engine.risk import risk_level, risk_reserve_rate

CALC_VERSION = "calc-v2"


@dataclass(frozen=True)
class CostInputs:
    """Explicit, sourced cost inputs. None means UNKNOWN, never 0."""

    shipping_eur: Decimal | None
    import_buffer_eur: Decimal | None
    is_import: bool
    source: str = "manual"
    # D-010: imports carry the flat intermediary fee from OWNER_POLICY unless
    # this deal was quoted a different one. Domestic buys have no intermediary.
    intermediary_fee_eur: Decimal | None = None

    def resolved_shipping(self, policy: Policy) -> Decimal | None:
        """Shipping for this deal, falling back to the D-015 import default.

        A domestic deal keeps the old contract: no default, so an unstated
        shipping cost stays UNKNOWN instead of quietly becoming 0.
        """
        if self.shipping_eur is not None:
            return self.shipping_eur
        return policy.import_shipping_eur if self.is_import else None

    def resolved_import_buffer(self, policy: Policy) -> Decimal | None:
        """Customs/VAT buffer, falling back to the D-015 import default of 0."""
        if self.import_buffer_eur is not None:
            return self.import_buffer_eur
        return policy.import_buffer_eur if self.is_import else None

    def resolved_intermediary_fee(self, policy: Policy) -> Decimal:
        """Fee to charge for this deal."""
        if not self.is_import:
            return Decimal("0")
        if self.intermediary_fee_eur is not None:
            return self.intermediary_fee_eur
        return policy.intermediary_fee_eur


def landed_cost(
    purchase_eur: Decimal,
    inputs: CostInputs,
    level: RiskLevel,
    policy: Policy = OWNER_POLICY,
) -> CostBreakdown:
    shipping = inputs.resolved_shipping(policy)
    buffer = inputs.resolved_import_buffer(policy)
    if shipping is None:
        raise ValueError("shipping_eur is UNKNOWN")
    if buffer is None:
        raise ValueError("import_buffer_eur is UNKNOWN")
    fee = inputs.resolved_intermediary_fee(policy)

    reserve = purchase_eur * risk_reserve_rate(level, inputs.is_import)
    return CostBreakdown(
        purchase_eur=round_money(purchase_eur),
        shipping_eur=round_money(shipping),
        import_buffer_eur=round_money(buffer),
        intermediary_fee_eur=round_money(fee),
        risk_reserve_eur=round_money(reserve),
    )


def build_opportunity(
    listing: Listing,
    evaluation: Evaluation | None,
    cost_inputs: CostInputs,
    expected_sale_rsd: Decimal | None | ResaleEstimate,
    eur_rsd: FxRate | None,
    purchase_fx: FxRate | None = None,
    product_match: ProductMatch | None = None,
    policy: Policy = OWNER_POLICY,
) -> Opportunity:
    """Combine listing + evaluation + costs into a scored opportunity.

    `expected_sale_rsd` must come from the Serbian pricing engine — this module
    never estimates a resale price itself. Pass the `ResaleEstimate` rather than
    a bare number where possible: the basis and confidence then travel with the
    verdict instead of being dropped on the way in.
    """
    missing: list[str] = []
    estimate: ResaleEstimate | None = None
    # D-013: a Serbian resale estimate may be quoted in EUR or in RSD. A bare
    # number keeps the old contract and is read as RSD.
    sale_currency = "RSD"

    if isinstance(expected_sale_rsd, ResaleEstimate):
        estimate = expected_sale_rsd
        sale_currency = estimate.currency.upper()
        # An unusable estimate carries its own reason; do not restate it as a
        # generic missing input, and never fall back to a number it withheld.
        expected_sale_rsd = estimate.resale_expected
        if not estimate.is_usable:
            missing.extend(f"resale:{reason}" for reason in estimate.missing_inputs)
            expected_sale_rsd = None

    if not listing.has_financial_minimum():
        missing.append("listing_financial_minimum")
    # CLAUDE.md section 5 lists product match among the attributes required
    # before any financial conclusion, so an unresolved match blocks the deal.
    if product_match is None:
        missing.append("product_match")
    elif not product_match.is_usable:
        missing.append(f"product_match:{product_match.status.value}")
    if evaluation is None:
        missing.append("evaluation")
    if expected_sale_rsd is None and estimate is None:
        missing.append("expected_sale_rsd")
    # The EUR/RSD rate is only needed when something in the deal is in dinars:
    # an estimate already quoted in EUR does not need converting.
    needs_rsd_rate = sale_currency == "RSD" or (
        listing.currency is not None and listing.currency.upper() == "RSD"
    )
    if eur_rsd is None and needs_rsd_rate:
        missing.append("fx_eur_rsd")
    if cost_inputs.resolved_shipping(policy) is None:
        missing.append("shipping_eur")
    if cost_inputs.resolved_import_buffer(policy) is None:
        missing.append("import_buffer_eur")

    provenance = Provenance(
        source=listing.url,
        observed_at=datetime.now(timezone.utc),
        method="deterministic",
        calculation_version=f"{CALC_VERSION}/{policy.version}",
        input_refs=[
            ref
            for ref in [
                listing.raw_payload_hash,
                cost_inputs.source,
                estimate.provenance.calculation_version if estimate and estimate.provenance else None,
            ]
            if ref
        ],
    )

    if missing:
        return Opportunity(
            listing=listing,
            evaluation=evaluation,
            verdict=Verdict.INSUFFICIENT_DATA,
            missing_inputs=missing,
            risk_level=risk_level(evaluation) if evaluation else RiskLevel.HIGH,
            provenance=provenance,
        )

    assert evaluation is not None and expected_sale_rsd is not None

    purchase = Money.of(listing.price_amount, listing.currency)
    if purchase.currency != "EUR":
        if purchase_fx is None:
            return Opportunity(
                listing=listing,
                evaluation=evaluation,
                verdict=Verdict.INSUFFICIENT_DATA,
                missing_inputs=[f"fx_{purchase.currency.lower()}_eur"],
                risk_level=risk_level(evaluation),
                provenance=provenance,
            )
        purchase = purchase_fx.convert(purchase)

    level = risk_level(evaluation)
    costs = landed_cost(purchase.amount, cost_inputs, level, policy)

    if sale_currency == "EUR":
        sale_eur = round_money(expected_sale_rsd)
    else:
        # eur_rsd is EUR/RSD, so RSD -> EUR is a division by its rate.
        assert eur_rsd is not None
        sale_eur = round_money(expected_sale_rsd / eur_rsd.rate)
    profit = round_money(sale_eur - costs.landed_cost_eur)
    roi = (profit / costs.landed_cost_eur) if costs.landed_cost_eur > 0 else Decimal("0")

    return Opportunity(
        listing=listing,
        evaluation=evaluation,
        costs=costs,
        # The RSD field holds an observed dinar figure only when the estimate
        # was in dinars; a EUR estimate leaves it UNKNOWN rather than carrying a
        # converted number that would look observed.
        expected_sale_rsd=round_units(expected_sale_rsd) if sale_currency == "RSD" else None,
        price_basis=estimate.price_basis if estimate else None,
        pricing_confidence=estimate.confidence if estimate else None,
        pricing_sample_size=estimate.sample_size if estimate else None,
        expected_sale_eur=sale_eur,
        expected_profit_eur=profit,
        roi=roi.quantize(Decimal("0.0001")),
        risk_level=level,
        verdict=decide(roi, level, profit, costs.purchase_eur, policy),
        provenance=provenance,
    )


def decide(
    roi: Decimal,
    level: RiskLevel,
    profit_eur: Decimal,
    purchase_eur: Decimal,
    policy: Policy = OWNER_POLICY,
) -> Verdict:
    """Advisory verdict only — the owner decides, the system never buys (D-003).

    A deal above the per-purchase cap (D-008) cannot be bought at the asking
    price no matter how good the economics are, so the best it can reach is
    NEGOTIATE: the target price may still bring it inside budget.
    """
    if roi < policy.watch_min_roi:
        return Verdict.SKIP
    over_budget = purchase_eur > policy.max_purchase_eur
    # D-009: a high ROI on a tiny margin is not a buy — both floors must hold.
    meets_buy = roi >= policy.buy_min_roi and profit_eur >= policy.min_profit_eur

    if level is RiskLevel.HIGH:
        return Verdict.WATCH if meets_buy else Verdict.SKIP
    if meets_buy:
        if over_budget:
            return Verdict.NEGOTIATE
        return Verdict.BUY if level is RiskLevel.LOW else Verdict.NEGOTIATE
    if roi >= policy.negotiate_min_roi:
        return Verdict.NEGOTIATE
    return Verdict.WATCH
