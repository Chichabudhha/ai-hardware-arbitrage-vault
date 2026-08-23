import re
from datetime import datetime, timezone
from decimal import Decimal

from src.core.money import FxRate
from src.core.models import Verdict
from src.obsidian_sync.writer import DealNoteWriter
from src.pricing.calculator import CostInputs, build_opportunity

EUR_RSD = FxRate("EUR", "RSD", Decimal("117.20"), datetime(2026, 8, 18, tzinfo=timezone.utc), "fx")
COSTS = CostInputs(
    Decimal("35"), Decimal("60"), is_import=True, source="fixture",
    intermediary_fee_eur=Decimal("25"),
)
PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}")


def _writer(tmp_path):
    return DealNoteWriter(deals_dir=tmp_path / "deals")


def test_note_has_no_leftover_placeholders(tmp_path, listing, evaluation, product_match):
    opportunity = build_opportunity(
        listing, evaluation, COSTS, Decimal("117200"), EUR_RSD, product_match=product_match
    )
    note = _writer(tmp_path).render(opportunity)
    assert not PLACEHOLDER.search(note)


def test_note_carries_frontmatter_and_numbers(tmp_path, listing, evaluation, product_match):
    opportunity = build_opportunity(
        listing, evaluation, COSTS, Decimal("117200"), EUR_RSD, product_match=product_match
    )
    note = _writer(tmp_path).render(opportunity)

    assert note.startswith("---\n")
    assert 'gpu_chip: "RTX 3090"' in note
    assert "vram_gb: 24" in note
    assert "est_profit_eur: 229.00" in note
    assert 'risk_score: "Low"' in note
    assert "has_warranty: false" in note
    assert "date_scouted: 2026-08-18" in note


def test_unknown_renders_as_unknown_not_zero(tmp_path, listing):
    opportunity = build_opportunity(listing, None, COSTS, None, EUR_RSD)
    note = _writer(tmp_path).render(opportunity)

    assert opportunity.verdict is Verdict.INSUFFICIENT_DATA
    assert "est_profit_eur: UNKNOWN" in note
    assert "vram_gb: UNKNOWN" in note
    assert "est_profit_eur: 0" not in note
    assert "INSUFFICIENT_DATA:" in note


def test_write_is_idempotent_and_does_not_clobber(tmp_path, listing, evaluation, product_match):
    writer = _writer(tmp_path)
    opportunity = build_opportunity(
        listing, evaluation, COSTS, Decimal("117200"), EUR_RSD, product_match=product_match
    )

    path = writer.write(opportunity)
    assert path.name.startswith("kleinanzeigen-123456789-nvidia-rtx-3090")

    path.write_text("rucno izmenjeno", encoding="utf-8")
    writer.write(opportunity)
    assert path.read_text(encoding="utf-8") == "rucno izmenjeno"

    writer.write(opportunity, overwrite=True)
    assert path.read_text(encoding="utf-8") != "rucno izmenjeno"


def test_unknown_gpu_chip_produces_no_unknown_tag(tmp_path, listing):
    opportunity = build_opportunity(listing, None, COSTS, None, EUR_RSD)
    note = _writer(tmp_path).render(opportunity)

    assert "- gpu_deal" in note
    assert "- UNKNOWN" not in note
