"""Kleinanzeigen.de connector (EU sourcing) — first EU source candidate, D-007.

Same posture as the RS connector: automation_status is RESEARCH until the owner
verifies the permitted access method and records it in odluke/. Prices are EUR
but that is read from the page, never assumed.
"""

from __future__ import annotations

import re

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

SELECTORS = SelectorMap(
    title=("#viewad-title", "h1"),
    price=("#viewad-price", '[class*="aditem-main--middle--price"]'),
    description=("#viewad-description-text", '[class*="description"]'),
    seller=("#viewad-contact-details a", '[class*="userprofile"]'),
    location=("#viewad-locality", '[class*="aditem-main--top--left"]'),
    listing_link=('a[href*="/s-anzeige/"]',),
)

_LISTING_ID = re.compile(r"/s-anzeige/[^/]*?/(\d+)")


class KleinanzeigenConnector(BaseConnector):
    access = ConnectorAccess(
        marketplace="kleinanzeigen",
        country="DE",
        base_url="https://www.kleinanzeigen.de",
        automation_status=AutomationStatus.RESEARCH,
        verification=UNVERIFIED,
        min_interval_seconds=10.0,
    )

    def search(self, filters: SearchFilters) -> list[RawObservation]:
        url = self.search_url(filters)
        html = self.fetch(url)  # blocked by the compliance gate until verified
        return self.parse_search_page(html, url)

    def search_url(self, filters: SearchFilters) -> str:
        slug = filters.query.strip().lower().replace(" ", "-")
        price = ""
        if filters.min_price is not None or filters.max_price is not None:
            price = f"preis:{filters.min_price or ''}:{filters.max_price or ''}/"
        return f"{self.access.base_url}/s-seite:{filters.page}/{price}{slug}/k0"

    def parse_search_page(self, html: str, page_url: str) -> list[RawObservation]:
        soup = soup_of(html)
        observations: list[RawObservation] = []
        seen: set[str] = set()
        for selector in SELECTORS.listing_link:
            for anchor in soup.select(selector):
                href = anchor.get("href") or ""
                listing_id = self.listing_id_from_url(href)
                if not listing_id or listing_id in seen:
                    continue
                seen.add(listing_id)
                observations.append(
                    self.observe(
                        url=self.absolute_url(href),
                        listing_id=listing_id,
                        payload=str(anchor.find_parent(["li", "article", "div"]) or anchor),
                    )
                )
        if not observations:
            observations.append(self.observe(page_url, "search-page", html))
        return observations

    def get_listing(self, listing_id: str) -> RawObservation:
        url = f"{self.access.base_url}/s-anzeige/{listing_id}"
        return self.observe(url, listing_id, self.fetch(url))

    def normalize_raw(self, observation: RawObservation) -> Listing:
        soup = soup_of(observation.payload)
        selector_fields = ParsedFields(
            title=first_text(soup, SELECTORS.title),
            description=first_text(soup, SELECTORS.description),
            seller_name=first_text(soup, SELECTORS.seller),
            location=first_text(soup, SELECTORS.location),
        )
        amount, currency = parse_price(first_text(soup, SELECTORS.price))
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
                method=f"kleinanzeigen:{observation.access_method.value}",
                input_refs=[observation.payload_hash],
            ),
        )

    @staticmethod
    def listing_id_from_url(url: str) -> str | None:
        match = _LISTING_ID.search(url)
        return match.group(1) if match else None

    def absolute_url(self, href: str) -> str:
        return href if href.startswith("http") else f"{self.access.base_url}{href}"
