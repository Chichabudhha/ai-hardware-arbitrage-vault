"""HTML → fields helpers shared by connectors.

Priority order is deliberate: JSON-LD (schema.org Product/Offer) is a documented,
stable contract, so it is tried first. CSS selectors are site-specific and are
marked UNVERIFIED until someone confirms them against a saved fixture — an
unmatched selector yields None, never a guessed value (CLAUDE.md principle 1).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

_PRICE_CHARS = re.compile(r"[^\d,.\-]")
_CURRENCY_SYMBOLS = {"€": "EUR", "din": "RSD", "рсд": "RSD", "rsd": "RSD", "eur": "EUR"}


@dataclass(frozen=True)
class SelectorMap:
    """Site-specific selectors. `verified_on` stays None until confirmed."""

    title: tuple[str, ...] = ()
    price: tuple[str, ...] = ()
    description: tuple[str, ...] = ()
    seller: tuple[str, ...] = ()
    location: tuple[str, ...] = ()
    listing_link: tuple[str, ...] = ()
    verified_on: str | None = None
    notes: str = "UNVERIFIED — confirm against a saved fixture before trusting output."


@dataclass
class ParsedFields:
    title: str | None = None
    description: str | None = None
    price_amount: Decimal | None = None
    currency: str | None = None
    seller_name: str | None = None
    location: str | None = None
    unresolved: list[str] = field(default_factory=list)


def soup_of(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def first_text(soup: BeautifulSoup, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            text = node.get_text(" ", strip=True)
            if text:
                return text
    return None


def parse_price(raw: str | None) -> tuple[Decimal | None, str | None]:
    """Parse '1.250,00 €' / '149.900 RSD' → (Decimal, currency). None if ambiguous."""
    if not raw:
        return None, None

    lowered = raw.lower()
    currency = None
    for token, code in _CURRENCY_SYMBOLS.items():
        if token in lowered:
            currency = code
            break

    cleaned = _PRICE_CHARS.sub("", raw).strip()
    if not cleaned:
        return None, currency

    # European formats: '1.250,00' → '1250.00'; '1,250.00' → '1250.00'
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        decimals = cleaned.rsplit(",", 1)[1]
        cleaned = cleaned.replace(",", "." if len(decimals) == 2 else "")
    elif "." in cleaned:
        # A single dot followed by exactly 3 digits is a thousands separator in
        # sr/de formatting ('89.900'), not a decimal point ('620.00').
        if cleaned.count(".") > 1 or len(cleaned.rsplit(".", 1)[1]) == 3:
            cleaned = cleaned.replace(".", "")

    try:
        return Decimal(cleaned), currency
    except InvalidOperation:
        return None, currency


def json_ld_offers(soup: BeautifulSoup) -> list[dict]:
    """Return every schema.org node that carries an offer-like price."""
    found: list[dict] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in _flatten(data):
            if isinstance(node, dict) and ("offers" in node or "price" in node):
                found.append(node)
    return found


def _flatten(data) -> list:
    if isinstance(data, list):
        return [item for entry in data for item in _flatten(entry)]
    if isinstance(data, dict):
        nested = []
        for value in data.values():
            if isinstance(value, (list, dict)):
                nested.extend(_flatten(value))
        return [data, *nested]
    return []


def fields_from_json_ld(soup: BeautifulSoup) -> ParsedFields:
    """Extract fields from JSON-LD when the site publishes it."""
    parsed = ParsedFields()
    for node in json_ld_offers(soup):
        offer = node.get("offers")
        if isinstance(offer, list):
            offer = offer[0] if offer else None
        offer = offer if isinstance(offer, dict) else node

        if parsed.title is None and isinstance(node.get("name"), str):
            parsed.title = node["name"]
        if parsed.description is None and isinstance(node.get("description"), str):
            parsed.description = node["description"]
        if parsed.price_amount is None and offer.get("price") is not None:
            try:
                parsed.price_amount = Decimal(str(offer["price"]))
            except InvalidOperation:
                pass
        if parsed.currency is None and isinstance(offer.get("priceCurrency"), str):
            parsed.currency = offer["priceCurrency"].upper()

        seller = node.get("seller") or offer.get("seller")
        if parsed.seller_name is None and isinstance(seller, dict):
            name = seller.get("name")
            if isinstance(name, str):
                parsed.seller_name = name
    return parsed


def merge(primary: ParsedFields, fallback: ParsedFields) -> ParsedFields:
    """Fill only the gaps in `primary`, and record what stayed unknown."""
    merged = ParsedFields(
        title=primary.title or fallback.title,
        description=primary.description or fallback.description,
        price_amount=primary.price_amount
        if primary.price_amount is not None
        else fallback.price_amount,
        currency=primary.currency or fallback.currency,
        seller_name=primary.seller_name or fallback.seller_name,
        location=primary.location or fallback.location,
    )
    merged.unresolved = [
        name
        for name in ("title", "price_amount", "currency")
        if getattr(merged, name) in (None, "")
    ]
    return merged
