"""Canonical NVIDIA GPU catalog.

Scope is the MVP list in product-intelligence/PRODUCT-INTELLIGENCE.md, which
says: expand only after MVP validation. D-011 added RTX 4080 Super and
RTX 4070 Ti Super. Tesla V100 and A100 from HA-002 stay out: the same decision
rejected them because the Serbian resale market for datacenter cards is too
thin to price. Widening the catalog further needs a new entry in odluke/
(CLAUDE.md principle 9).

Each entry carries its own match patterns. A pattern must be specific enough
that no listing for a different card can satisfy it.
"""

from __future__ import annotations

from src.core.models import Product

# Tokens that prove the text is talking about a graphics card at all. A bare
# number like "3090" also appears in prices ("cena 3090 din"), so a numeric
# model is only trusted when one of these is present somewhere in the listing.
BRAND_TOKENS = (
    "rtx",
    "geforce",
    "nvidia",
    "gtx",
    "quadro",
    "tesla",
    "graficka",
    "grafička",
    "grafikkarte",
    "graphics card",
    "video karta",
)

class CatalogEntry:
    """A product plus the patterns that identify it in free text."""

    __slots__ = ("product", "patterns", "requires_brand_token")

    def __init__(
        self,
        product: Product,
        patterns: tuple[str, ...],
        requires_brand_token: bool = True,
    ) -> None:
        self.product = product
        self.patterns = patterns
        self.requires_brand_token = requires_brand_token

    @property
    def product_id(self) -> str:
        return self.product.product_id


def _geforce(model: str, variant: str | None, vram: int, arch: str) -> Product:
    name = f"RTX {model}" + (f" {variant}" if variant else "")
    return Product(
        product_id=name.lower().replace(" ", "-"),
        family="GeForce RTX",
        model=model,
        variant=variant,
        vram_gb=vram,
        architecture=arch,
        canonical_name=f"NVIDIA {name} {vram}GB",
    )


def _workstation(model: str, vram: int, arch: str) -> Product:
    name = f"RTX {model}"
    return Product(
        product_id=name.lower().replace(" ", "-"),
        family="RTX professional",
        model=model,
        variant=None,
        vram_gb=vram,
        architecture=arch,
        canonical_name=f"NVIDIA {name} {vram}GB",
    )


# Order matters only for readability; specificity is resolved by the matcher.
CATALOG: tuple[CatalogEntry, ...] = (
    CatalogEntry(
        _geforce("3090", "Ti", 24, "Ampere"),
        # 'Ti' may be written Ti / TI / ti, optionally after 'super'-style spacing.
        (r"\b3090\s*ti\b",),
    ),
    CatalogEntry(
        _geforce("3090", None, 24, "Ampere"),
        (r"\b3090\b",),
    ),
    CatalogEntry(
        _geforce("3080", "Ti", 12, "Ampere"),
        (r"\b3080\s*ti\b",),
    ),
    CatalogEntry(
        _geforce("4090", None, 24, "Ada Lovelace"),
        (r"\b4090\b",),
    ),
    CatalogEntry(
        _geforce("4080", "Super", 16, "Ada Lovelace"),
        (r"\b4080\s*super\b",),
    ),
    CatalogEntry(
        # Written as one model name, so the Super is part of the variant and
        # there is no plain '4070 Ti' entry for it to collapse against.
        _geforce("4070 Ti", "Super", 16, "Ada Lovelace"),
        (r"\b4070\s*ti\s*super\b",),
    ),
    CatalogEntry(
        _workstation("A4000", 16, "Ampere"),
        (r"\ba\s*4000\b",),
        requires_brand_token=False,
    ),
    CatalogEntry(
        _workstation("A5000", 24, "Ampere"),
        (r"\ba\s*5000\b",),
        requires_brand_token=False,
    ),
    CatalogEntry(
        _workstation("A6000", 48, "Ampere"),
        (r"\ba\s*6000\b",),
        requires_brand_token=False,
    ),
)

_BY_ID = {entry.product_id: entry for entry in CATALOG}


def get_product(product_id: str) -> Product:
    try:
        return _BY_ID[product_id].product
    except KeyError:
        raise KeyError(f"unknown product_id '{product_id}'") from None


def known_product_ids() -> list[str]:
    return sorted(_BY_ID)
