"""Render an Opportunity into a deal note using blokovi/DEAL-template.md.

The template is the single source of truth for note structure — this module only
substitutes {{PLACEHOLDERS}}. Unknown values render as UNKNOWN, never as 0, so a
Dataview table cannot mistake a missing input for a real number.
"""

from __future__ import annotations

import os
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from src.core.models import Opportunity, Verdict

TEMPLATE_PATH = Path("blokovi/DEAL-template.md")
DEFAULT_DEALS_DIR = Path(os.getenv("ARBITRAGE_DEALS_DIR", "dnevnik/deals"))

_PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")

UNKNOWN = "UNKNOWN"


def _num(value: Decimal | int | None) -> str:
    return UNKNOWN if value is None else str(value)


def _quoted(value: str | None) -> str:
    """YAML-safe scalar: the template already wraps these fields in quotes."""
    if value is None:
        return UNKNOWN
    return value.replace('"', "'").replace("\n", " ").strip() or UNKNOWN


def _bool(value: bool | None) -> str:
    return UNKNOWN if value is None else ("true" if value else "false")


def slugify(text: str, max_length: int = 60) -> str:
    slug = _SLUG_STRIP.sub("-", text.lower()).strip("-")
    return slug[:max_length].strip("-") or "deal"


class DealNoteWriter:
    def __init__(
        self,
        template_path: str | Path = TEMPLATE_PATH,
        deals_dir: str | Path = DEFAULT_DEALS_DIR,
    ) -> None:
        self.template_path = Path(template_path)
        self.deals_dir = Path(deals_dir)

    def render(self, opportunity: Opportunity) -> str:
        template = self.template_path.read_text(encoding="utf-8")
        values = self.build_values(opportunity)

        def substitute(match: re.Match[str]) -> str:
            return values.get(match.group(1), UNKNOWN)

        return _drop_unknown_tags(_PLACEHOLDER.sub(substitute, template))

    def write(self, opportunity: Opportunity, overwrite: bool = False) -> Path:
        """Write the note. Existing notes are kept unless overwrite is requested."""
        self.deals_dir.mkdir(parents=True, exist_ok=True)
        path = self.deals_dir / f"{self.note_name(opportunity)}.md"
        if path.exists() and not overwrite:
            return path
        path.write_text(self.render(opportunity), encoding="utf-8")
        return path

    @staticmethod
    def note_name(opportunity: Opportunity) -> str:
        listing = opportunity.listing
        return f"{listing.marketplace}-{listing.source_listing_id}-{slugify(listing.title)}"

    @staticmethod
    def build_values(opportunity: Opportunity) -> dict[str, str]:
        listing = opportunity.listing
        evaluation = opportunity.evaluation
        spec = evaluation.spec if evaluation else None
        costs = opportunity.costs

        shipping_total = (
            costs.shipping_eur
            + costs.import_buffer_eur
            + costs.intermediary_fee_eur
            + costs.risk_reserve_eur
            if costs
            else None
        )
        risk_notes = evaluation.risk_notes if evaluation else None
        if evaluation and evaluation.risk_flags:
            flags = ", ".join(flag.value for flag in evaluation.risk_flags)
            risk_notes = f"{risk_notes or ''} [flags: {flags}]".strip()
        if opportunity.verdict is Verdict.INSUFFICIENT_DATA and opportunity.missing_inputs:
            missing = ", ".join(opportunity.missing_inputs)
            risk_notes = f"{risk_notes or ''} [INSUFFICIENT_DATA: {missing}]".strip()

        return {
            "ITEM_NAME": _quoted(listing.title),
            "GPU_CHIP": _quoted(spec.gpu_chip if spec else None),
            "VRAM_GB": _num(spec.vram_gb if spec else None),
            "PLATFORM": _quoted(listing.marketplace),
            "SOURCE_URL": _quoted(listing.url),
            "SELLER_NAME": _quoted(listing.seller_name),
            "BUY_PRICE_EUR": _num(costs.purchase_eur if costs else None),
            "SHIPPING_EUR": _num(shipping_total),
            "SELL_PRICE_RSD": _num(opportunity.expected_sale_rsd),
            "SELL_PRICE_EUR": _num(opportunity.expected_sale_eur),
            "PROFIT_EUR": _num(opportunity.expected_profit_eur),
            "RISK_SCORE": _quoted(opportunity.risk_level.value),
            "CONDITION": _quoted(evaluation.condition.value if evaluation else None),
            "HAS_WARRANTY": _bool(evaluation.has_warranty if evaluation else None),
            "DATE_SCOUTED": listing.observed_at.date().isoformat()
            if listing.observed_at
            else date.today().isoformat(),
            "RAW_DESCRIPTION": (listing.description or UNKNOWN).strip(),
            "WARRANTY_NOTES": (evaluation.warranty_notes if evaluation else None) or UNKNOWN,
            "SELLER_NOTES": (evaluation.seller_notes if evaluation else None) or UNKNOWN,
            "RISK_NOTES": risk_notes or UNKNOWN,
        }


def _drop_unknown_tags(note: str) -> str:
    """Remove `- UNKNOWN` tag entries so Obsidian gets no meaningless tag."""
    kept = [line for line in note.splitlines() if line.strip() != f'- {UNKNOWN}']
    trailing_newline = chr(10) if note.endswith(chr(10)) else ''
    return chr(10).join(kept) + trailing_newline
