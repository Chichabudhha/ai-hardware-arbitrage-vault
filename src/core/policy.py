"""W0 business policy — owner decisions, not engineering assumptions.

Every value here traces to an approved entry in odluke/_pregled-odluka.md.
Nothing in this module may be changed without a new decision (CLAUDE.md
principle 9). Thresholds live here rather than inside the calculator so the
policy can be read, audited and versioned on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

# v3 adds the D-019 flat corridor shipping. v2 added the D-015 import cost defaults. The version travels with every
# recorded prediction, so a later change to these numbers stays visible in
# calibration instead of quietly reshaping past results.
POLICY_VERSION = "policy-v3"


@dataclass(frozen=True)
class Policy:
    """Financial thresholds that decide a verdict."""

    capital_eur: Decimal
    max_purchase_eur: Decimal
    min_profit_eur: Decimal
    buy_min_roi: Decimal
    negotiate_min_roi: Decimal
    watch_min_roi: Decimal
    # D-010: the EU intermediary charges a flat fee per card.
    intermediary_fee_eur: Decimal
    # D-015/D-016: standing cost defaults for an EU import, per card. The
    # intermediary charges the same shipping for every EU country, so distance
    # does not enter the calculation; non-EU sources are out of scope (D-016). They apply only
    # when the caller does not supply a figure for a specific deal, and only to
    # imports — a domestic purchase has no shipping until someone states one.
    import_shipping_eur: Decimal = Decimal("25")
    # D-019: the same 25 EUR is assumed for every other corridor too (RS->EU,
    # EU->EU) until the real costs are researched. A working assumption the
    # owner set explicitly, not a measured figure.
    corridor_shipping_eur: Decimal = Decimal("25")
    # Zero because the intermediary's fee already covers customs and VAT — an
    # approved fact, not an UNKNOWN silently treated as 0 (principle 2).
    import_buffer_eur: Decimal = Decimal("0")
    version: str = POLICY_VERSION

    def __post_init__(self) -> None:
        if not (self.buy_min_roi > self.negotiate_min_roi > self.watch_min_roi):
            raise ValueError("ROI thresholds must decrease: buy > negotiate > watch")
        if self.watch_min_roi < 0:
            raise ValueError("watch_min_roi must not be negative")
        if self.max_purchase_eur <= 0 or self.capital_eur <= 0:
            raise ValueError("capital and max purchase must be positive")
        if self.max_purchase_eur > self.capital_eur:
            raise ValueError("max_purchase_eur cannot exceed capital_eur")
        if self.min_profit_eur < 0:
            raise ValueError("min_profit_eur must not be negative")
        if self.intermediary_fee_eur < 0:
            raise ValueError("intermediary_fee_eur must not be negative")
        if self.import_shipping_eur < 0 or self.import_buffer_eur < 0:
            raise ValueError("import cost defaults must not be negative")
        if self.corridor_shipping_eur < 0:
            raise ValueError("corridor_shipping_eur must not be negative")


# D-008: starting capital 1000 EUR, at most 500 EUR committed to one card.
# D-010: the intermediary charges a flat 15 EUR per card.
# D-015: shipping DE->RS is 25 EUR per card and the customs buffer is 0,
#        because the intermediary's 15 EUR fee already includes customs and VAT.
#        Both are revisable by a new decision and overridable per deal.
# D-009: BUY requires ROI >= 18% and >= 50 EUR profit. NEGOTIATE and WATCH
#        floors are derived from the same ratios the previous advisory set used
#        (12/25 and 5/25 of the BUY floor), rounded to whole percent.
OWNER_POLICY = Policy(
    capital_eur=Decimal("1000"),
    max_purchase_eur=Decimal("500"),
    min_profit_eur=Decimal("50"),
    buy_min_roi=Decimal("0.18"),
    negotiate_min_roi=Decimal("0.09"),
    watch_min_roi=Decimal("0.04"),
    intermediary_fee_eur=Decimal("15"),
)
