"""Claude-backed listing interpretation.

Returns an Evaluation (facts + risk flags) with provenance. Contains no money math.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import anthropic
from pydantic import BaseModel, Field

from src.core.models import Condition, Evaluation, GpuSpec, Listing, Provenance, RiskFlag
from src.deal_engine.prompts import SYSTEM_PROMPT, USER_TEMPLATE

MODEL_ID = os.getenv("ARBITRAGE_MODEL", "claude-opus-5")
EVALUATOR_VERSION = "evaluator-v1"


class ListingFacts(BaseModel):
    """Schema Claude fills. Every uncertain field is nullable on purpose."""

    gpu_chip: str | None = Field(default=None, description="e.g. 'RTX 3090', 'RTX A5000'")
    vram_gb: int | None = None
    brand: str | None = Field(default=None, description="AIB partner, e.g. MSI, Asus")
    quantity: int = 1
    match_confidence: float = 0.0
    condition: str | None = Field(default=None, description="new | used | for_parts")
    has_warranty: bool | None = None
    warranty_notes: str | None = None
    seller_notes: str | None = None
    risk_flags: list[str] = Field(default_factory=list)
    risk_notes: str | None = None


class ListingEvaluator:
    def __init__(self, client: anthropic.Anthropic | None = None, model: str = MODEL_ID) -> None:
        self.client = client or anthropic.Anthropic()
        self.model = model

    def evaluate(self, listing: Listing) -> Evaluation:
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": self._render(listing)}],
            output_format=ListingFacts,
        )
        return self._to_evaluation(response.parsed_output, listing)

    @staticmethod
    def _render(listing: Listing) -> str:
        price = (
            f"{listing.price_amount} {listing.currency}"
            if listing.price_amount is not None and listing.currency
            else "UNKNOWN"
        )
        return USER_TEMPLATE.format(
            marketplace=listing.marketplace,
            title=listing.title,
            location=listing.location or "UNKNOWN",
            seller=listing.seller_name or "UNKNOWN",
            price=price,
            description=listing.description or "(nema opisa)",
        )

    @staticmethod
    def _to_evaluation(facts: ListingFacts, listing: Listing) -> Evaluation:
        known_flags = {flag.value for flag in RiskFlag}
        return Evaluation(
            spec=GpuSpec(
                gpu_chip=facts.gpu_chip,
                vram_gb=facts.vram_gb,
                brand=facts.brand,
                quantity=max(1, facts.quantity),
                match_confidence=max(0.0, min(1.0, facts.match_confidence)),
            ),
            condition=Condition(facts.condition)
            if facts.condition in {c.value for c in Condition}
            else Condition.UNKNOWN,
            has_warranty=facts.has_warranty,
            warranty_notes=facts.warranty_notes,
            seller_notes=facts.seller_notes,
            risk_flags=[RiskFlag(f) for f in facts.risk_flags if f in known_flags],
            risk_notes=facts.risk_notes,
            provenance=Provenance(
                source=listing.url,
                observed_at=datetime.now(timezone.utc),
                method=f"llm:{MODEL_ID}",
                calculation_version=EVALUATOR_VERSION,
                input_refs=[listing.raw_payload_hash] if listing.raw_payload_hash else [],
            ),
        )
