from decimal import Decimal

import pytest

from src.core.money import InsufficientData, Money, require


def test_money_rejects_float():
    with pytest.raises(TypeError):
        Money.of(12.5, "EUR")


def test_money_arithmetic_is_exact():
    total = Money.of("0.10", "EUR") + Money.of("0.20", "EUR")
    assert total.amount == Decimal("0.30")


def test_currency_mismatch_raises():
    with pytest.raises(ValueError):
        Money.of("10", "EUR") + Money.of("10", "RSD")


def test_unknown_is_not_zero():
    with pytest.raises(InsufficientData):
        require(None, "shipping_eur")


def test_zero_or_negative_fx_rate_is_rejected():
    from datetime import datetime, timezone

    from src.core.money import FxRate

    for bad_rate in (Decimal("0"), Decimal("-117.20")):
        with pytest.raises(ValueError):
            FxRate("EUR", "RSD", bad_rate, datetime.now(timezone.utc), "corrupt")


def test_rsd_rounds_to_whole_units():
    from src.core.money import round_units

    assert round_units(Decimal("149899.60")) == Decimal("149900")
