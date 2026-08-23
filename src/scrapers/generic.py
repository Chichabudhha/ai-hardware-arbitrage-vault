"""Config-driven MANUAL connector: a new marketplace is a row, not a class.

The measurement pass over EU sites (D-017) showed the real cost of adding a
source is not the parsing — every classifieds site puts the title in a heading,
the price near it and the description below — but the boilerplate of a new
connector class per site. This module turns that into a JSON entry.

Two things it deliberately cannot do:

1. **Fetch.** These profiles are `MANUAL` and unverified by construction, so the
   compliance gate blocks `fetch()` exactly as it does for the hand-written
   connectors (CLAUDE.md principle 7). A JSON file must never be able to grant
   automated access to a site — that decision belongs in `odluke/`.
2. **Interpret.** It extracts what the page states and stops there; condition,
   risk and identity are decided elsewhere.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.core.models import AutomationStatus, Listing, PriceType, Provenance, RawObservation
from src.scrapers.base import BaseConnector, ConnectorAccess, SearchFilters
from src.scrapers.compliance import UNVERIFIED
from src.scrapers.html_parse import (
    ParsedFields,
    SelectorMap,
    fields_from_json_ld,
    first_text,
    merge,
    parse_price,
    soup_of,
)

DEFAULT_SITES = Path("marketplace/sites.json")

# Selectors that work on most classifieds pages, tried after the site's own.
# They are a fallback, not a guess about any particular site: if none of them
# match, the field stays None and the listing reports it as missing.
COMMON_SELECTORS = SelectorMap(
    title=("h1",),
    price=('[class*="price"]', '[class*="Price"]', '[itemprop="price"]'),
    description=('[class*="description"]', '[class*="Description"]', "article p"),
    seller=('[class*="seller"]', '[class*="user"]'),
    location=('[class*="location"]', '[class*="locality"]', '[class*="address"]'),
    listing_link=("a[href]",),
)


class SiteProfile(BaseModel):
    """One marketplace described as data."""

    model_config = ConfigDict(frozen=True)

    marketplace: str
    country: str
    base_url: str
    listing_id_pattern: str
    title: tuple[str, ...] = ()
    price: tuple[str, ...] = ()
    description: tuple[str, ...] = ()
    seller: tuple[str, ...] = ()
    location: tuple[str, ...] = ()
    listing_link: tuple[str, ...] = ()
    notes: str = ""
    # Kept for the record; a profile is always read as MANUAL regardless.
    source_decision: str = Field(default="", description="odluke/ entry allowing manual reading")

    def selectors(self) -> SelectorMap:
        """Site selectors first, shared fallbacks after."""
        return SelectorMap(
            title=self.title + COMMON_SELECTORS.title,
            price=self.price + COMMON_SELECTORS.price,
            description=self.description + COMMON_SELECTORS.description,
            seller=self.seller + COMMON_SELECTORS.seller,
            location=self.location + COMMON_SELECTORS.location,
            listing_link=self.listing_link + COMMON_SELECTORS.listing_link,
            notes=self.notes or "config-driven profile; verify against a saved page",
        )


class SiteProfileError(ValueError):
    """A site profile could not be read as written."""


def load_profiles(path: str | Path | None = None) -> list[SiteProfile]:
    """Read site profiles from JSON. A malformed entry rejects the whole file."""
    source = Path(DEFAULT_SITES if path is None else path)
    if not source.exists():
        return []
    try:
        entries = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SiteProfileError(f"{source} is not valid JSON: {exc}") from exc
    if not isinstance(entries, list):
        raise SiteProfileError(f"{source} must contain a list of site profiles")

    profiles: list[SiteProfile] = []
    for index, entry in enumerate(entries, start=1):
        try:
            profile = SiteProfile.model_validate(entry)
            re.compile(profile.listing_id_pattern)
        except (ValidationError, re.error) as exc:
            raise SiteProfileError(f"{source} entry {index} is not usable: {exc}") from exc
        profiles.append(profile)
    return profiles


class GenericManualConnector(BaseConnector):
    """A marketplace read from a saved page, described entirely by config."""

    def __init__(self, profile: SiteProfile, client=None) -> None:
        self.profile = profile
        self.access = ConnectorAccess(
            marketplace=profile.marketplace,
            country=profile.country,
            base_url=profile.base_url,
            # Not configurable on purpose: config cannot promote a site to
            # automated access. That takes a decision and a verified check.
            automation_status=AutomationStatus.MANUAL,
            verification=UNVERIFIED,
        )
        self._selectors = profile.selectors()
        self._listing_id = re.compile(profile.listing_id_pattern)
        super().__init__(client)

    # --- contract -------------------------------------------------------

    def search(self, filters: SearchFilters) -> list[RawObservation]:
        raise NotImplementedError(
            f"{self.access.marketplace} is a MANUAL source: save the page and use "
            "the import path (D-012/D-014/D-017), no automated search exists"
        )

    def get_listing(self, listing_id: str) -> RawObservation:
        raise NotImplementedError(
            f"{self.access.marketplace} is a MANUAL source: no automated fetch"
        )

    def listing_id_from_url(self, url: str) -> str | None:
        match = self._listing_id.search(url)
        return match.group(1) if match else None

    def normalize_raw(self, observation: RawObservation) -> Listing:
        """Structure extraction only, JSON-LD first where the site provides it."""
        soup = soup_of(observation.payload)
        selector_fields = ParsedFields(
            title=first_text(soup, self._selectors.title),
            description=first_text(soup, self._selectors.description),
            seller_name=first_text(soup, self._selectors.seller),
            location=first_text(soup, self._selectors.location),
        )
        amount, currency = parse_price(first_text(soup, self._selectors.price))
        selector_fields.price_amount = amount
        selector_fields.currency = currency

        fields = merge(fields_from_json_ld(soup), selector_fields)
        return Listing(
            marketplace=observation.marketplace,
            source_listing_id=observation.source_listing_id,
            url=observation.url,
            title=fields.title or "UNKNOWN",
            description=fields.description,
            price_amount=fields.price_amount,
            currency=fields.currency,
            price_type=PriceType.ASKING,
            seller_name=fields.seller_name,
            location=fields.location,
            observed_at=observation.fetched_at,
            raw_payload_hash=observation.payload_hash,
            provenance=Provenance(
                source=observation.url,
                observed_at=observation.fetched_at,
                method=f"manual-profile:{self.profile.marketplace}",
                input_refs=[observation.payload_hash],
            ),
        )
