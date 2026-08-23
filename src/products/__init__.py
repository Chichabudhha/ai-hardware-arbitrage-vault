"""Canonical product catalog and deterministic listing -> product matching."""

from src.products.catalog import CATALOG, get_product
from src.products.matcher import match_listing, match_text, reconcile_with_llm

__all__ = ["CATALOG", "get_product", "match_listing", "match_text", "reconcile_with_llm"]
