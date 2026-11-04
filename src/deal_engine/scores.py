"""D-023 scores. Deterministic, advisory, never a verdict input.

Each function returns None (UNKNOWN) when an input it needs is missing:
a score built on a guessed input would look measured (principle 2).
"""

from __future__ import annotations

from decimal import Decimal

from src.core.policy import OWNER_POLICY, Policy

_ONE = Decimal("1")


def deal_score(
    profit_eur: Decimal | None,
    roi: Decimal | None,
    policy: Policy = OWNER_POLICY,
) -> Decimal | None:
    """0-100 economic attractiveness relative to the D-009 BUY thresholds.

    The weaker of ROI/min_roi and profit/min_profit decides, so a high ROI on
    a cheap card cannot hide a small absolute profit (the reason D-009 needs
    both). At exactly the thresholds the score is `deal_score_at_threshold`.
    """
    if profit_eur is None or roi is None:
        return None
    ratios = [roi / policy.buy_min_roi]
    if policy.min_profit_eur > 0:
        ratios.append(profit_eur / policy.min_profit_eur)
    raw = min(ratios) * policy.deal_score_at_threshold
    clamped = max(Decimal("0"), min(policy.deal_score_max, raw))
    return clamped.quantize(_ONE)


def confidence_score(
    pricing_confidence: Decimal | None,
    match_confidence: Decimal | None,
) -> Decimal | None:
    """Weakest link of the data behind a deal; no weights (D-023)."""
    if pricing_confidence is None or match_confidence is None:
        return None
    return min(pricing_confidence, match_confidence).quantize(Decimal("0.01"))
