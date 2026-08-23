"""Price matrix: the same product across markets, side by side.

Until now the engine asked one question — what does this card fetch in Serbia.
The matrix asks a wider one: what does it fetch *everywhere we have observed*,
so a difference between two markets is visible instead of inferred.

What it does not do is decide that a difference is a trade. A spread between two
markets is not profit: transport, fees, customs and the legal posture of selling
across a border are not modelled here, and for anything other than EU→RS they
are not decided at all (D-010/D-015/D-016 cover exactly one corridor). The
matrix reports the price side and stops there.

Two rules carry over from the Serbian estimator, for the same reasons:

1. A sample is never mixed across currencies (D-013). Each market is estimated
   in its own currency, and the matrix says which.
2. A market with too thin a sample reports INSUFFICIENT_DATA rather than a
   number with a caveat.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from src.core.money import FxRate
from src.core.models import Condition, PriceObservation, ResaleEstimate
from src.core.policy import OWNER_POLICY, Policy
from src.pricing.fx import convert_to_eur
from src.pricing.serbian_market import (
    DEFAULT_RULES,
    PricingRules,
    estimate_resale,
    pick_sample_currency,
)


class MarketPrice(BaseModel):
    """One product in one market."""

    model_config = ConfigDict(frozen=True)

    product_id: str
    marketplace: str
    condition: Condition
    currency: str | None = None
    sample_size: int = 0
    p25: Decimal | None = None
    median: Decimal | None = None
    p75: Decimal | None = None
    # Derived, not observed: converted at an observed rate so the table can be
    # read at a glance (D-019). Empty when no rate covers the currency.
    p25_eur: Decimal | None = None
    median_eur: Decimal | None = None
    p75_eur: Decimal | None = None
    fx_note: str | None = None
    confidence: Decimal = Decimal("0")
    status: str = "INSUFFICIENT_DATA"
    missing_inputs: list[str] = Field(default_factory=list)

    @property
    def is_usable(self) -> bool:
        return self.status == "OK"


class MarketSpread(BaseModel):
    """Difference between two markets for one product, always in EUR (D-019)."""

    model_config = ConfigDict(frozen=True)

    product_id: str
    cheap_market: str
    rich_market: str
    cheap_p25_eur: Decimal
    rich_median_eur: Decimal
    gross_spread_eur: Decimal
    shipping_eur: Decimal
    net_spread_eur: Decimal
    spread_pct: Decimal

    @property
    def headline(self) -> str:
        # ASCII only: this goes to a Windows console whose code page cannot
        # encode an arrow, and a crash while printing a table is a silly way to
        # lose a report.
        return (
            f"{self.product_id}: buy {self.cheap_market} {self.cheap_p25_eur} EUR -> "
            f"sell {self.rich_market} {self.rich_median_eur} EUR = "
            f"+{self.gross_spread_eur} gross, {self.net_spread_eur:+} after "
            f"{self.shipping_eur} EUR shipping ({self.spread_pct * 100:.1f}%)"
        )


def _from_estimate(
    estimate: ResaleEstimate, marketplace: str, rates: list[FxRate] | None = None
) -> MarketPrice:
    rates = rates or []
    eur: dict[str, Decimal | None] = {"p25": None, "median": None, "p75": None}
    note = None
    for name in eur:
        value = getattr(estimate, name)
        if value is None or not estimate.currency:
            continue
        eur[name], reason = convert_to_eur(value, estimate.currency, rates)
        note = note or reason
    return MarketPrice(
        p25_eur=eur["p25"],
        median_eur=eur["median"],
        p75_eur=eur["p75"],
        fx_note=note,
        product_id=estimate.product_id,
        marketplace=marketplace,
        condition=estimate.condition,
        currency=estimate.currency,
        sample_size=estimate.sample_size,
        p25=estimate.p25,
        median=estimate.median,
        p75=estimate.p75,
        confidence=estimate.confidence,
        status="OK" if estimate.is_usable else "INSUFFICIENT_DATA",
        missing_inputs=list(estimate.missing_inputs),
    )


def build_matrix(
    observations: list[PriceObservation],
    condition: Condition = Condition.USED,
    now: datetime | None = None,
    rules: PricingRules = DEFAULT_RULES,
    products: list[str] | None = None,
    markets: list[str] | None = None,
    rates: list[FxRate] | None = None,
) -> list[MarketPrice]:
    """Estimate every observed (product, market) pair, cheapest first per product.

    Each cell is the ordinary estimator pointed at a single marketplace, so a
    cell in the matrix and the Serbian resale estimate are the same computation
    — there is no second, looser code path for money.
    """
    pairs = sorted(
        {
            (obs.product_id, obs.marketplace)
            for obs in observations
            if (products is None or obs.product_id in products)
            and (markets is None or obs.marketplace in markets)
        }
    )

    cells: list[MarketPrice] = []
    for product_id, marketplace in pairs:
        market_rules = replace(rules, resale_marketplaces=frozenset({marketplace}))
        # The sample currency has to be chosen inside the market, not across the
        # whole store: a Romanian market quoting RON would otherwise lose to a
        # global EUR majority and report an empty cell instead of its own prices.
        local = [obs for obs in observations if obs.marketplace == marketplace]
        estimate = estimate_resale(
            observations,
            product_id,
            condition=condition,
            now=now,
            rules=market_rules,
            currency=pick_sample_currency(local, product_id),
        )
        cells.append(_from_estimate(estimate, marketplace, rates))
    return cells


def spreads(
    cells: list[MarketPrice], policy: Policy = OWNER_POLICY
) -> list[MarketSpread]:
    """Price differences between markets, in EUR, gross and net of shipping.

    `cheap_p25` against `rich_median` on purpose: buying happens at the low end
    of a market's asking distribution and selling at its middle, so the pairing
    matches how a trade would actually run.

    Net subtracts only the flat corridor shipping (D-019, 25 EUR in every
    direction as a working assumption). It is **not** a landed cost: no
    intermediary fee, customs, platform fee or tax is in here, and outside the
    EU->RS corridor none of those has even been decided (D-018). A positive net
    number means "worth investigating", never "worth buying".

    A market whose currency has no observed rate is left out entirely rather
    than compared at a guessed rate.
    """
    usable = [
        cell
        for cell in cells
        if cell.is_usable and cell.p25_eur is not None and cell.median_eur is not None
    ]
    found: list[MarketSpread] = []

    for cheap in usable:
        for rich in usable:
            if cheap.marketplace == rich.marketplace or cheap.product_id != rich.product_id:
                continue
            assert cheap.p25_eur is not None and rich.median_eur is not None
            gross = rich.median_eur - cheap.p25_eur
            if gross <= 0:
                continue
            found.append(
                MarketSpread(
                    product_id=cheap.product_id,
                    cheap_market=cheap.marketplace,
                    rich_market=rich.marketplace,
                    cheap_p25_eur=cheap.p25_eur,
                    rich_median_eur=rich.median_eur,
                    gross_spread_eur=gross,
                    shipping_eur=policy.corridor_shipping_eur,
                    net_spread_eur=gross - policy.corridor_shipping_eur,
                    spread_pct=(gross / cheap.p25_eur).quantize(Decimal("0.0001")),
                )
            )
    return sorted(found, key=lambda s: s.net_spread_eur, reverse=True)


def render_table(cells: list[MarketPrice]) -> str:
    """Fixed-width table in EUR, cheapest usable market first within each product.

    The local-currency P25 stays in view next to it: the euro figure is derived
    and the original is what was actually observed.
    """
    if not cells:
        return "no observations"

    def sort_key(cell: MarketPrice) -> tuple:
        return (cell.product_id, not cell.is_usable, cell.p25_eur or Decimal("0"))

    header = (
        f"{'product':<16}{'market':<17}{'n':>3}"
        f"{'P25 EUR':>10}{'med EUR':>10}{'P75 EUR':>10}"
        f"{'local P25':>14}{'conf':>6}  status"
    )
    lines = [header, "-" * len(header)]
    for cell in sorted(cells, key=sort_key):
        local = (
            f"{cell.p25} {cell.currency}"
            if cell.p25 is not None and cell.currency
            else "-"
        )
        status = "OK" if cell.is_usable else ", ".join(cell.missing_inputs)
        if cell.fx_note:
            status = f"{status} ({cell.fx_note})"
        lines.append(
            f"{cell.product_id:<16}{cell.marketplace:<17}{cell.sample_size:>3}"
            f"{str(cell.p25_eur or '-'):>10}{str(cell.median_eur or '-'):>10}"
            f"{str(cell.p75_eur or '-'):>10}{local:>14}{str(cell.confidence):>6}  {status}"
        )
    return "\n".join(lines)
