"""FX rates. Never invented — a rate must be observed and sourced (principle 1)."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from src.core.money import FxRate, InsufficientData

DEFAULT_STORE = Path("data/fx-observations.json")


def load_rates(path: str | Path = DEFAULT_STORE) -> list[FxRate]:
    """Load observed rates from disk. Missing file means no rates, not a default rate."""
    file_path = Path(path)
    if not file_path.exists():
        return []
    entries = json.loads(file_path.read_text(encoding="utf-8"))
    rates: list[FxRate] = []
    for entry in entries:
        try:
            rates.append(
                FxRate(
                    base_currency=entry["base_currency"].upper(),
                    quote_currency=entry["quote_currency"].upper(),
                    rate=Decimal(str(entry["rate"])),
                    observed_at=datetime.fromisoformat(entry["observed_at"]),
                    source=entry["source"],
                )
            )
        except (ValueError, KeyError) as exc:
            # A corrupt entry is dropped loudly, never silently coerced.
            raise InsufficientData(f"invalid FX entry in {file_path}: {exc}") from exc
    return rates


def latest_rate(base: str, quote: str, rates: list[FxRate]) -> FxRate:
    """Most recent observed rate for the pair, or INSUFFICIENT_DATA."""
    candidates = [
        rate
        for rate in rates
        if rate.base_currency == base.upper() and rate.quote_currency == quote.upper()
    ]
    if not candidates:
        raise InsufficientData(
            f"no observed FX rate for {base.upper()}/{quote.upper()}; "
            f"add one to {DEFAULT_STORE} with source and timestamp"
        )
    return max(candidates, key=lambda rate: rate.observed_at)


def inverted(rate: FxRate) -> FxRate:
    """Flip an observed pair, e.g. EUR/RSD -> RSD/EUR.

    Not a new observation: the inverse carries the same timestamp and names the
    rate it was derived from, so nothing looks independently sourced. Division
    happens in Decimal, so no float rounding enters the money path.
    """
    return FxRate(
        base_currency=rate.quote_currency,
        quote_currency=rate.base_currency,
        rate=Decimal(1) / rate.rate,
        observed_at=rate.observed_at,
        source=f"derived from {rate.base_currency}/{rate.quote_currency} ({rate.source})",
    )


def rate_to_eur(currency: str, rates: list[FxRate]) -> FxRate:
    """Rate converting `currency` into EUR, direct if observed, inverse otherwise."""
    currency = currency.upper()
    try:
        return latest_rate(currency, "EUR", rates)
    except InsufficientData:
        # EUR/RSD is the pair that gets published; RSD/EUR usually is not.
        return inverted(latest_rate("EUR", currency, rates))


def convert_to_eur(
    amount: Decimal, currency: str, rates: list[FxRate]
) -> tuple[Decimal | None, str | None]:
    """Amount in EUR, or (None, reason) when no observed rate covers the pair.

    Returning a reason instead of raising lets a report show a whole table with
    one market marked "no rate" rather than failing wholesale — but the missing
    cell stays empty, never filled with an approximation (principle 1).
    """
    code = currency.upper()
    if code == "EUR":
        return amount, None
    try:
        rate = rate_to_eur(code, rates)
    except InsufficientData:
        return None, f"no_observed_rate:{code}/EUR"
    return (amount * rate.rate).quantize(Decimal("0.01")), None
