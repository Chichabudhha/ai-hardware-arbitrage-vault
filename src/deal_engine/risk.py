"""Deterministic risk scoring. No LLM here — the LLM only supplied the flags."""

from __future__ import annotations

from decimal import Decimal

from src.core.models import Condition, Evaluation, RiskFlag, RiskLevel

RISK_VERSION = "risk-v1"

# Weights are configuration, not findings. Tune only via a decision in odluke/.
FLAG_WEIGHTS: dict[RiskFlag, int] = {
    RiskFlag.MINING_USE: 3,
    RiskFlag.PHYSICAL_DAMAGE: 4,
    RiskFlag.UNTESTED: 3,
    RiskFlag.SUSPICIOUS_SELLER: 4,
    RiskFlag.REMOTE_PAYMENT_ONLY: 3,
    RiskFlag.PRICE_TOO_GOOD: 2,
    RiskFlag.BULK_LIQUIDATION: 2,
    RiskFlag.NO_WARRANTY: 1,
    RiskFlag.NO_PACKAGING: 1,
}

# Risk reserve as a share of purchase price, per HA-002 §3.
RESERVE_HIGH = Decimal("0.15")
RESERVE_MEDIUM = Decimal("0.08")
RESERVE_LOW_IMPORT = Decimal("0.05")
RESERVE_LOW_LOCAL = Decimal("0.00")


def risk_points(evaluation: Evaluation) -> int:
    points = sum(FLAG_WEIGHTS.get(flag, 1) for flag in evaluation.risk_flags)
    if evaluation.condition is Condition.FOR_PARTS:
        points += 4
    if evaluation.condition is Condition.UNKNOWN:
        points += 1
    if evaluation.has_warranty is None:
        points += 1
    if evaluation.spec.match_confidence < 0.6:
        points += 2
    return points


def risk_level(evaluation: Evaluation) -> RiskLevel:
    points = risk_points(evaluation)
    if points >= 6:
        return RiskLevel.HIGH
    if points >= 3:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def risk_reserve_rate(level: RiskLevel, is_import: bool) -> Decimal:
    """Share of purchase price held back as reserve.

    HA-002 §3: mining / no warranty carry +15%; a verified local deal 0-5%.
    """
    if level is RiskLevel.HIGH:
        return RESERVE_HIGH
    if level is RiskLevel.MEDIUM:
        return RESERVE_MEDIUM
    return RESERVE_LOW_IMPORT if is_import else RESERVE_LOW_LOCAL
