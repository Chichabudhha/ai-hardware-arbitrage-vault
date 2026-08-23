"""Decimal money arithmetic and FX normalization.

Per DATA-MODEL.md: financial fields use Decimal, never binary floats.
Original currency and amount are always retained; EUR values are derived.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

CENTS = Decimal("0.01")
UNITS = Decimal("1")


class InsufficientData(Exception):
    """Raised when a required financial input is UNKNOWN.

    UNKNOWN is never treated as 0 (CLAUDE.md principle 2).
    """


def to_decimal(value: str | int | Decimal) -> Decimal:
    """Convert to Decimal without ever passing through float."""
    if isinstance(value, float):
        raise TypeError("float is not accepted for money; pass str, int or Decimal")
    return Decimal(str(value))


def round_money(amount: Decimal) -> Decimal:
    """Round to a 2-decimal subunit. Correct for EUR; do not use for RSD."""
    return amount.quantize(CENTS, rounding=ROUND_HALF_UP)


def round_units(amount: Decimal) -> Decimal:
    """Round to whole units — RSD is quoted and paid in whole dinars."""
    return amount.quantize(UNITS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Money:
    """An amount in its original currency. Never silently converted."""

    amount: Decimal
    currency: str

    @classmethod
    def of(cls, amount: str | int | Decimal, currency: str) -> "Money":
        return cls(amount=to_decimal(amount), currency=currency.upper())

    def __add__(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, factor: str | int | Decimal) -> "Money":
        return Money(self.amount * to_decimal(factor), self.currency)

    def rounded(self) -> "Money":
        return Money(round_money(self.amount), self.currency)

    def _assert_same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError(
                f"currency mismatch: {self.currency} vs {other.currency}; "
                "convert explicitly via FxRate"
            )

    def __str__(self) -> str:
        return f"{round_money(self.amount)} {self.currency}"


@dataclass(frozen=True)
class FxRate:
    """One observed FX rate. Never invented — always sourced (principle 1)."""

    base_currency: str
    quote_currency: str
    rate: Decimal
    observed_at: datetime
    source: str

    def __post_init__(self) -> None:
        # A non-positive rate is corrupt data, not a usable rate — every
        # downstream conversion divides or multiplies by it.
        if self.rate <= 0:
            raise ValueError(
                f"FX rate for {self.base_currency}/{self.quote_currency} must be > 0, "
                f"got {self.rate} (source: {self.source})"
            )

    def convert(self, money: Money) -> Money:
        if money.currency != self.base_currency:
            raise ValueError(
                f"rate {self.base_currency}/{self.quote_currency} cannot convert {money.currency}"
            )
        return Money(money.amount * self.rate, self.quote_currency)


def require(value: Money | None, field_name: str) -> Money:
    """Fail loudly instead of substituting 0 for an UNKNOWN input."""
    if value is None:
        raise InsufficientData(f"missing required financial input: {field_name}")
    return value
