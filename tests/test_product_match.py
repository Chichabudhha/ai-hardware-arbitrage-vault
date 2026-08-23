from decimal import Decimal

import pytest

from src.core.models import Condition, Evaluation, GpuSpec, MatchStatus
from src.products import get_product, match_listing, match_text, reconcile_with_llm
from src.products.catalog import CATALOG
from src.products.matcher import normalize, stated_vram_values


def status_of(text: str) -> MatchStatus:
    return match_text(text).status


# --- the case that ruled out embeddings ------------------------------------


def test_3080_is_not_matched_to_3090():
    """nomic-embed-text scored these two 0.930 similar; the rules must not."""
    match = match_text("Nvidia RTX 3080 10GB Gigabyte Gaming OC, kao nova")
    assert match.status is MatchStatus.UNMATCHED
    assert match.product_id is None


def test_3090_matches_regardless_of_phrasing():
    for text in (
        "Nvidia RTX 3090 24GB Gigabyte Gaming OC, kao nova",
        "Grafička karta RTX 3090 24 GB, Gigabyte, očuvana",
        "NVIDIA GeForce RTX 3090 24GB Grafikkarte",
        "rtx3090 24gb",
        "RTX-3090, 24 GB",
    ):
        match = match_text(text)
        assert match.status is MatchStatus.MATCHED, text
        assert match.product_id == "rtx-3090", text


# --- specificity -----------------------------------------------------------


def test_ti_variant_wins_over_base_model():
    match = match_text("RTX 3090 Ti 24GB, kupljena 2022")
    assert match.product_id == "rtx-3090-ti"
    assert match.status is MatchStatus.MATCHED


@pytest.mark.parametrize("text", ["RTX 3090Ti 24GB", "rtx 3090 TI 24gb", "RTX-3090-Ti"])
def test_ti_spellings(text):
    assert match_text(text).product_id == "rtx-3090-ti"


def test_plain_3080_is_not_matched_to_3080_ti():
    assert status_of("RTX 3080 10GB") is MatchStatus.UNMATCHED


# --- false positives -------------------------------------------------------


def test_price_is_not_a_model_number():
    assert status_of("Prodajem grafičku kartu, cena 3090 din") is MatchStatus.UNMATCHED
    assert status_of("Grafička karta, 4090 eur") is MatchStatus.UNMATCHED


def test_unrelated_listing_is_unmatched():
    assert status_of("Playstation 5 sa dva džojstika") is MatchStatus.UNMATCHED


def test_model_number_without_brand_token_is_low_confidence():
    match = match_text("Prodajem 3090, 24GB, stanje odlicno")
    assert match.status is MatchStatus.LOW_CONFIDENCE
    assert match.product_id == "rtx-3090"
    assert match.confidence == Decimal("0.85")


def test_workstation_names_need_no_brand_token():
    match = match_text("A6000 48GB")
    assert match.status is MatchStatus.MATCHED
    assert match.product_id == "rtx-a6000"


# --- conflicts -------------------------------------------------------------


def test_vram_contradiction_is_a_conflict():
    """A '3090 12GB' listing is a seller error or a scam — never a silent match."""
    match = match_text("RTX 3090 12GB, povoljno")
    assert match.status is MatchStatus.CONFLICT
    assert match.stated_vram_gb == 12
    assert "24GB" in (match.notes or "")


def test_two_different_cards_is_a_conflict():
    match = match_text("Prodajem RTX 3090 i RTX 4090, obe rade")
    assert match.status is MatchStatus.CONFLICT
    assert match.candidate_ids == ["rtx-3090", "rtx-4090"]
    assert match.product_id is None


def test_only_matched_is_usable():
    assert match_text("RTX 3090 24GB nvidia").is_usable
    assert not match_text("RTX 3090 12GB").is_usable
    assert not match_text("Prodajem 3090").is_usable


# --- helpers ---------------------------------------------------------------


def test_all_stated_sizes_are_collected():
    assert stated_vram_values(normalize("RTX 3090 24GB, uz njega 32GB RAM")) == [24, 32]
    assert stated_vram_values(normalize("RTX 3090 24GB")) == [24]
    assert stated_vram_values(normalize("bez navedene memorije")) == []


def test_bundle_ram_does_not_fake_a_vram_conflict():
    """'24GB card + 32GB RAM' is a bundle, not a mismatched card."""
    match = match_text("RTX 3090 24GB nvidia, uz njega i7 i 32GB RAM")
    assert match.status is MatchStatus.MATCHED
    assert match.stated_vram_gb == 24


def test_ti_listing_naming_the_plain_card_needs_review():
    """A Ti listing often name-drops the plain card; never silently drop one."""
    match = match_text("RTX 3090 Ti 24GB nvidia, bolja od obicne 3090")
    assert match.status is MatchStatus.REVIEW_REQUIRED
    assert match.product_id == "rtx-3090-ti"
    assert not match.is_usable
    assert "confirm" in (match.notes or "")


def test_normalize_strips_diacritics_and_glue():
    assert normalize("Grafička RTX-3090Ti") == "graficka rtx 3090 ti"


def test_catalog_matches_mvp_spec():
    """MVP seven plus the two Super cards from D-011; do not widen silently."""
    assert sorted(entry.product_id for entry in CATALOG) == [
        "rtx-3080-ti",
        "rtx-3090",
        "rtx-3090-ti",
        "rtx-4070-ti-super",
        "rtx-4080-super",
        "rtx-4090",
        "rtx-a4000",
        "rtx-a5000",
        "rtx-a6000",
    ]


def test_ai_relevance_follows_vram():
    assert get_product("rtx-a6000").ai_relevance_score == Decimal("1.0")
    assert get_product("rtx-3090").ai_relevance_score == Decimal("0.9")
    assert get_product("rtx-a4000").ai_relevance_score == Decimal("0.6")
    assert get_product("rtx-3080-ti").ai_relevance_score == Decimal("0.3")


def test_match_listing_reads_title_and_description(listing):
    assert match_listing(listing).product_id == "rtx-3090"


# --- reconciliation --------------------------------------------------------


def test_catalog_overrides_wrong_llm_vram(listing):
    wrong = Evaluation(
        spec=GpuSpec(gpu_chip="RTX 3090", vram_gb=12, match_confidence=0.9),
        condition=Condition.USED,
    )
    fixed = reconcile_with_llm(match_listing(listing), wrong)

    assert fixed.spec.vram_gb == 24
    assert fixed.spec.gpu_chip == "RTX 3090"
    assert "katalog" in (fixed.risk_notes or "")


def test_reconcile_leaves_evaluation_alone_when_unmatched():
    unmatched = match_text("Playstation 5")
    evaluation = Evaluation(spec=GpuSpec(gpu_chip="nesto", vram_gb=8))
    assert reconcile_with_llm(unmatched, evaluation) == evaluation


def test_reconcile_is_quiet_when_llm_agrees(listing):
    agreeing = Evaluation(
        spec=GpuSpec(gpu_chip="RTX 3090", vram_gb=24, match_confidence=0.9),
        condition=Condition.USED,
    )
    fixed = reconcile_with_llm(match_listing(listing), agreeing)
    assert fixed.risk_notes is None
    assert fixed.spec.match_confidence == 1.0


# --- D-011: Super cards added to the catalog -------------------------------


def test_4080_super_matches():
    match = match_text("NVIDIA GeForce RTX 4080 Super 16GB, garancija")
    assert match.status is MatchStatus.MATCHED
    assert match.product_id == "rtx-4080-super"


def test_plain_4080_is_not_matched_to_4080_super():
    """The non-Super 4080 is not in the catalog and must not be mistaken for it."""
    assert status_of("RTX 4080 16GB Gaming OC") is MatchStatus.UNMATCHED


def test_4070_ti_super_matches():
    match = match_text("Graficka RTX 4070 Ti Super 16GB")
    assert match.status is MatchStatus.MATCHED
    assert match.product_id == "rtx-4070-ti-super"


def test_plain_4070_ti_is_not_matched_to_super():
    assert status_of("RTX 4070 Ti 12GB, malo koriscena") is MatchStatus.UNMATCHED


def test_4080_super_vram_contradiction_is_a_conflict():
    match = match_text("RTX 4080 Super 24GB")
    assert match.status is MatchStatus.CONFLICT


def test_datacenter_cards_stay_out_of_catalog():
    """D-011 rejected V100 and A100 — the Serbian resale market is too thin."""
    assert status_of("Nvidia Tesla V100 32GB") is MatchStatus.UNMATCHED
    assert status_of("Nvidia A100 80GB PCIe") is MatchStatus.UNMATCHED
