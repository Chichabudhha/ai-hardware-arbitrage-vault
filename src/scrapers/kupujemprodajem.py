"""KupujemProdajem connector (Serbia) — primary RS market, D-006.

automation_status is RESEARCH: the permitted acquisition method is not yet
verified, so `fetch()` refuses to run. Parsing and normalization are implemented
and testable now, so flipping the status after verification is a one-line change.
Until then use src.scrapers.manual_import.
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
    title=("h1", '[class*="AdViewInfo"] h1'),
    price=('[class*="price"]', '[class*="Price"]'),
    description=('[class*="description"]', '[class*="Description"]'),
    seller=('[class*="userName"]', '[class*="UserInfo"] a'),
    location=('[class*="location"]', '[class*="Location"]'),
    listing_link=('a[href*="/oglas/"]',),
)

_LISTING_ID = re.compile(r"/oglas/(?:[^/]+/)?(\d+)")


class KupujemProdajemConnector(BaseConnector):
    access = ConnectorAccess(
        marketplace="kupujemprodajem",
        country="RS",
        base_url="https://www.kupujemprodajem.com",
        automation_status=AutomationStatus.RESEARCH,
        verification=UNVERIFIED,
        min_interval_seconds=8.0,
    )

    def search(self, filters: SearchFilters) -> list[RawObservation]:
        url = self.search_url(filters)
        html = self.fetch(url)  # blocked by the compliance gate until verified
        return self.parse_search_page(html, url)

    def search_url(self, filters: SearchFilters) -> str:
        params = [f"keywords={filters.query.replace(' ', '+')}", f"page={filters.page}"]
        if filters.min_price is not None:
            params.append(f"priceFrom={filters.min_price}")
        if filters.max_price is not None:
            params.append(f"priceTo={filters.max_price}")
        return f"{self.access.base_url}/pretraga?{'&'.join(params)}"

    def parse_search_page(self, html: str, page_url: str) -> list[RawObservation]:
        """Split a result page into one raw observation per listing link (deduped)."""
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
        url = f"{self.access.base_url}/oglas/{listing_id}"
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
                method=f"kupujemprodajem:{observation.access_method.value}",
                input_refs=[observation.payload_hash],
            ),
        )

    @staticmethod
    def listing_id_from_url(url: str) -> str | None:
        match = _LISTING_ID.search(url)
        return match.group(1) if match else None

    def absolute_url(self, href: str) -> str:
        return href if href.startswith("http") else f"{self.access.base_url}{href}"
