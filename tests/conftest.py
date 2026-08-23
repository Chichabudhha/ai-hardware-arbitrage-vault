from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.core.models import (
    Condition,
    Evaluation,
    GpuSpec,
    Listing,
    PriceType,
    RiskFlag,
)


@pytest.fixture
def listing() -> Listing:
    return Listing(
        marketplace="kleinanzeigen",
        source_listing_id="123456789",
        url="https://www.kleinanzeigen.de/s-anzeige/rtx-3090/123456789",
        title="NVIDIA RTX 3090 24GB MSI Gaming X Trio",
        description="Karta radi savrseno, koriscena za gaming. Bez garancije, bez kutije.",
        price_amount=Decimal("620"),
        currency="EUR",
        price_type=PriceType.ASKING,
        seller_name="Hans",
        location="Berlin",
        observed_at=datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc),
        raw_payload_hash="a" * 64,
    )


@pytest.fixture
def evaluation() -> Evaluation:
    return Evaluation(
        spec=GpuSpec(gpu_chip="RTX 3090", vram_gb=24, brand="MSI", match_confidence=0.95),
        condition=Condition.USED,
        has_warranty=False,
        warranty_notes="Bez garancije.",
        seller_notes="Privatni prodavac, opis konkretan.",
        risk_flags=[RiskFlag.NO_WARRANTY, RiskFlag.NO_PACKAGING],
        risk_notes="Nema kutije ni garancije.",
    )


@pytest.fixture
def product_match(listing):
    """Deterministic catalog match for the listing fixture (RTX 3090 24GB)."""
    from src.products import match_listing

    return match_listing(listing)
