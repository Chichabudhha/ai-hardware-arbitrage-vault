"""Deterministic listing -> product matching.

Why deterministic and not embeddings: measured 2026-08-18, `nomic-embed-text`
scored "RTX 3090 24GB Gigabyte Gaming OC" vs "RTX 3080 10GB Gigabyte Gaming OC"
at 0.930 cosine similarity — higher than the same product phrased differently
(0.708). Embeddings capture surface text, not the meaning of the model number,
and confusing a 10GB card with a 24GB one destroys the whole valuation.
See reference/naucene-lekcije.md.

The target chip set is closed and small, so exact rules are both correct and
free. A match is never silently forced: ambiguity becomes CONFLICT or
REVIEW_REQUIRED, and a missing match stays UNMATCHED.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal

from src.core.models import Evaluation, Listing, MatchStatus, ProductMatch
from src.products.catalog import BRAND_TOKENS, CATALOG, CatalogEntry, get_product

MATCHER_VERSION = "product-match-v1"

# Confidence is a fixed scale, not a tuned number: either the rules identified
# exactly one card or they did not.
CONF_EXACT_WITH_VRAM = Decimal("1.00")
CONF_EXACT = Decimal("0.95")
CONF_NO_BRAND_TOKEN = Decimal("0.85")
CONF_NONE = Decimal("0.00")

# A model number directly attached to money is a price, not a product.
_CURRENCY_AFTER = re.compile(r"^\s*(din|dinara|rsd|e|eur|evra|euro|km)\b", re.IGNORECASE)
_PRICE_BEFORE = re.compile(r"(cena|cijena|price|preis|po)\s*:?\s*$", re.IGNORECASE)

_VRAM = re.compile(r"\b(\d{1,3})\s*(?:gb|gigabyte)\b", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")
_PUNCT = re.compile(r"[_/\\|,;:()\[\]{}+*]+")


def normalize(text: str) -> str:
    """Lowercase, strip diacritics, collapse separators.

    'RTX-3090Ti' and 'rtx 3090 ti' must normalize to the same shape so that one
    pattern covers both spellings.
    """
    lowered = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(ch for ch in lowered if not unicodedata.combining(ch))
    spaced = _PUNCT.sub(" ", stripped)
    spaced = re.sub(r"(?<=[a-z])-(?=[a-z0-9])", " ", spaced)
    spaced = re.sub(r"(?<=[0-9])-(?=[a-z])", " ", spaced)
    # Glue-free model names: 'rtx3090' -> 'rtx 3090', '3090ti' -> '3090 ti'.
    spaced = re.sub(r"(?<=[a-z])(?=\d)", " ", spaced)
    spaced = re.sub(r"(?<=\d)(?=ti\b)", " ", spaced)
    return _WHITESPACE.sub(" ", spaced).strip()


# Brand tokens are compared against normalized text, so they are normalized once
# here — an accented entry would otherwise never match anything.
_BRAND_TOKENS_NORMALIZED = tuple(sorted({normalize(token) for token in BRAND_TOKENS}))


def _has_brand_token(text: str) -> bool:
    return any(token in text for token in _BRAND_TOKENS_NORMALIZED)


def _is_price_context(text: str, start: int, end: int) -> bool:
    """True when the number is part of a price rather than a model name."""
    if _CURRENCY_AFTER.match(text[end : end + 12]):
        return True
    return bool(_PRICE_BEFORE.search(text[max(0, start - 12) : start]))


def _find_hits(text: str, entry: CatalogEntry) -> list[tuple[int, int]]:
    hits: list[tuple[int, int]] = []
    for pattern in entry.patterns:
        for found in re.finditer(pattern, text, re.IGNORECASE):
            if not _is_price_context(text, found.start(), found.end()):
                hits.append((found.start(), found.end()))
    return hits


def stated_vram_values(text: str) -> list[int]:
    """Every plausible VRAM figure in the text, in order of appearance.

    A listing routinely mentions sizes that are not the card's VRAM — '32GB RAM'
    or '1TB SSD' in a whole-PC bundle. Singling one out and calling it the VRAM
    turns a correct listing into a false conflict, so the caller compares the
    whole set against the catalog instead of picking one.
    """
    return [
        int(found.group(1))
        for found in _VRAM.finditer(text)
        if 2 <= int(found.group(1)) <= 96
    ]


def stated_vram(text: str) -> int | None:
    """First plausible VRAM figure — for display only, never for matching."""
    values = stated_vram_values(text)
    return values[0] if values else None


def _is_shadowed(
    entry: CatalogEntry,
    hits: list[tuple[int, int]],
    fired: list[tuple[CatalogEntry, list[tuple[int, int]]]],
) -> bool:
    """True when every hit of `entry` sits inside a longer hit of another entry.

    This is what keeps the '3090' inside 'RTX 3090 Ti' from producing a second,
    wrong candidate.
    """
    for start, end in hits:
        covered = any(
            other is not entry
            and other_start <= start
            and other_end >= end
            and (other_end - other_start) > (end - start)
            for other, other_hits in fired
            for other_start, other_end in other_hits
        )
        if not covered:
            return False
    return True


def _resolve(text: str) -> list[CatalogEntry]:
    """Catalog entries firing on `text`, with shadowed ones removed."""
    fired: list[tuple[CatalogEntry, list[tuple[int, int]]]] = []
    for entry in CATALOG:
        hits = _find_hits(text, entry)
        if hits:
            fired.append((entry, hits))
    return [entry for entry, hits in fired if not _is_shadowed(entry, hits, fired)]


def _prefer_variant(entries: list[CatalogEntry]) -> CatalogEntry | None:
    """Collapse '3090' + '3090 Ti' to the Ti when both name one base model.

    A Ti listing routinely name-drops the plain card ("bolja od obicne 3090"),
    so two candidates from a single base model are usually one card described
    twice. Different base models (3090 vs 4090) are left alone — that is a real
    conflict. The collapse is still surfaced as REVIEW_REQUIRED, never silently.
    """
    if len({entry.product.model for entry in entries}) != 1:
        return None
    with_variant = [entry for entry in entries if entry.product.variant]
    return with_variant[0] if len(with_variant) == 1 else None


def match_text(title: str, description: str | None = None) -> ProductMatch:
    """Match free text against the canonical catalog.

    Identity comes from the title, which names the item actually for sale; the
    description is consulted only when the title identifies nothing, because
    descriptions routinely discuss other cards for comparison.
    """
    full_text = normalize(title if not description else f"{title}\n{description}")
    title_text = normalize(title)
    now = datetime.now(timezone.utc)

    vram_values = stated_vram_values(full_text)
    first_vram = vram_values[0] if vram_values else None

    surviving = _resolve(title_text) or _resolve(full_text)

    if not surviving:
        return ProductMatch(
            product_id=None,
            status=MatchStatus.UNMATCHED,
            confidence=CONF_NONE,
            method=MATCHER_VERSION,
            matched_at=now,
            stated_vram_gb=first_vram,
            notes="no catalog entry matched",
        )

    candidates = sorted({entry.product_id for entry in surviving})
    chosen = surviving[0]
    review_note: str | None = None

    if len(candidates) > 1:
        preferred = _prefer_variant(surviving)
        if preferred is None:
            return ProductMatch(
                product_id=None,
                status=MatchStatus.CONFLICT,
                confidence=CONF_NONE,
                method=MATCHER_VERSION,
                matched_at=now,
                candidate_ids=candidates,
                stated_vram_gb=first_vram,
                notes=f"listing names several distinct cards: {', '.join(candidates)}",
            )
        chosen = preferred
        review_note = (
            f"listing names both {' and '.join(candidates)}; taking the variant "
            f"{preferred.product_id} — confirm the seller is not offering both"
        )

    product = chosen.product

    if chosen.requires_brand_token and not _has_brand_token(full_text):
        return ProductMatch(
            product_id=product.product_id,
            status=MatchStatus.LOW_CONFIDENCE,
            confidence=CONF_NO_BRAND_TOKEN,
            method=MATCHER_VERSION,
            matched_at=now,
            candidate_ids=candidates,
            stated_vram_gb=first_vram,
            notes="model number found but no GPU brand token in the text",
        )

    # A stated size only contradicts the catalog when NONE of the sizes in the
    # text is the card's VRAM: '24GB ... 32GB RAM' is a bundle, not a mismatch.
    if vram_values and product.vram_gb not in vram_values:
        return ProductMatch(
            product_id=product.product_id,
            status=MatchStatus.CONFLICT,
            confidence=CONF_NONE,
            method=MATCHER_VERSION,
            matched_at=now,
            candidate_ids=candidates,
            stated_vram_gb=first_vram,
            notes=(
                f"listing states {first_vram}GB but {product.canonical_name} has "
                f"{product.vram_gb}GB — seller error, bundle, or misrepresentation"
            ),
        )

    vram_confirmed = product.vram_gb in vram_values
    return ProductMatch(
        product_id=product.product_id,
        status=MatchStatus.REVIEW_REQUIRED if review_note else MatchStatus.MATCHED,
        confidence=CONF_EXACT_WITH_VRAM if vram_confirmed else CONF_EXACT,
        method=MATCHER_VERSION,
        matched_at=now,
        candidate_ids=candidates,
        stated_vram_gb=product.vram_gb if vram_confirmed else first_vram,
        notes=review_note,
    )


def match_listing(listing: Listing) -> ProductMatch:
    return match_text(listing.title, listing.description)


def canonical_chip(product_id: str) -> str:
    """Short chip label as written in a deal note, e.g. 'RTX 3090 Ti'."""
    product = get_product(product_id)
    return f"RTX {product.model}" + (f" {product.variant}" if product.variant else "")


def reconcile_with_llm(match: ProductMatch, evaluation: Evaluation) -> Evaluation:
    """Let the catalog override the LLM's chip and VRAM guess.

    The LLM reads condition, warranty and risk from prose — that is its job.
    Product identity is a lookup, so the deterministic result wins when the two
    disagree, and the disagreement is recorded rather than hidden.
    """
    if match.status is not MatchStatus.MATCHED or match.product_id is None:
        return evaluation

    product = get_product(match.product_id)
    chip = canonical_chip(match.product_id)
    llm_chip = (evaluation.spec.gpu_chip or "").strip()

    disagrees = bool(
        (llm_chip and normalize(llm_chip) != normalize(chip))
        or (evaluation.spec.vram_gb is not None and evaluation.spec.vram_gb != product.vram_gb)
    )

    notes = evaluation.risk_notes
    if disagrees:
        detail = (
            f"[katalog: {product.canonical_name}; LLM je rekao: "
            f"{llm_chip or 'UNKNOWN'} / {evaluation.spec.vram_gb or 'UNKNOWN'}GB]"
        )
        notes = f"{notes} {detail}".strip() if notes else detail

    return evaluation.model_copy(
        update={
            "spec": evaluation.spec.model_copy(
                update={
                    "gpu_chip": chip,
                    "vram_gb": product.vram_gb,
                    "match_confidence": float(match.confidence),
                }
            ),
            "risk_notes": notes,
        }
    )
