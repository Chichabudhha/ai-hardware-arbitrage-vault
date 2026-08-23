"""Config-driven MANUAL connectors (generic profiles)."""

import json

import pytest

from src.core.models import AutomationStatus
from src.scrapers.generic import GenericManualConnector, SiteProfile, SiteProfileError, load_profiles
from src.scrapers.registry import get_connector, list_connectors
from src.scrapers.manual_import import import_file

PROFILE = {
    "marketplace": "testsite",
    "country": "IT",
    "base_url": "https://example.test",
    "listing_id_pattern": "-(\\d{6,})\\.htm",
    "title": ["h1.ad-title"],
    "price": [".ad-price"],
    "description": [".ad-text"],
}

PAGE = """
<html><body>
<h1 class="ad-title">MSI RTX 3080 Ti Gaming X Trio</h1>
<div class="ad-price">350 &euro;</div>
<div class="ad-text">Scheda video usata, perfettamente funzionante.</div>
</body></html>
"""


def write_sites(tmp_path, entries) -> str:
    path = tmp_path / "sites.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return str(path)


def test_profile_page_is_normalized_without_a_new_class(tmp_path):
    saved = tmp_path / "annuncio.html"
    saved.write_text(PAGE, encoding="utf-8")
    connector = GenericManualConnector(SiteProfile.model_validate(PROFILE))
    observation = connector.observe("https://example.test/x-123456.htm", "123456", PAGE)

    listing = connector.normalize_raw(observation)

    assert listing.title == "MSI RTX 3080 Ti Gaming X Trio"
    assert str(listing.price_amount) == "350"
    assert listing.currency == "EUR"
    assert listing.provenance.method == "manual-profile:testsite"


def test_profile_is_always_manual_and_unverified():
    """Config must not be able to grant a site automated access (principle 7)."""
    sneaky = dict(PROFILE, automation_status="AUTOMATED", verification="verified")
    connector = GenericManualConnector(SiteProfile.model_validate(sneaky))

    assert connector.access.automation_status is AutomationStatus.MANUAL
    assert connector.access.verification.is_verified is False


def test_profile_connector_refuses_to_fetch():
    connector = GenericManualConnector(SiteProfile.model_validate(PROFILE))
    with pytest.raises(NotImplementedError, match="MANUAL source"):
        connector.get_listing("123456")


def test_listing_id_comes_from_the_configured_pattern():
    connector = GenericManualConnector(SiteProfile.model_validate(PROFILE))

    assert connector.listing_id_from_url("https://example.test/msi-987654.htm") == "987654"
    assert connector.listing_id_from_url("https://example.test/no-id") is None


def test_broken_profile_rejects_the_whole_file(tmp_path):
    path = write_sites(tmp_path, [PROFILE, {"marketplace": "half"}])
    with pytest.raises(SiteProfileError, match="entry 2"):
        load_profiles(path)


def test_invalid_regex_is_caught_at_load_time(tmp_path):
    path = write_sites(tmp_path, [dict(PROFILE, listing_id_pattern="(unclosed")])
    with pytest.raises(SiteProfileError):
        load_profiles(path)


def test_missing_sites_file_is_not_an_error(tmp_path):
    assert load_profiles(tmp_path / "absent.json") == []


def test_registry_serves_profiles_and_keeps_written_connectors(tmp_path):
    path = write_sites(tmp_path, [PROFILE, dict(PROFILE, marketplace="kleinanzeigen")])

    assert get_connector("testsite", sites=path).access.country == "IT"
    # A profile must not shadow a hand-written connector.
    assert get_connector("kleinanzeigen", sites=path).access.country == "DE"
    assert type(get_connector("kleinanzeigen", sites=path)).__name__ == "KleinanzeigenConnector"

    names = {c.access.marketplace for c in list_connectors(sites=path)}
    assert {"kupujemprodajem", "kleinanzeigen", "testsite"} <= names


def test_unknown_marketplace_lists_what_is_known(tmp_path):
    path = write_sites(tmp_path, [PROFILE])
    with pytest.raises(KeyError, match="testsite"):
        get_connector("nowhere", sites=path)


def test_manual_import_works_through_a_profile(tmp_path, monkeypatch):
    saved = tmp_path / "annuncio.html"
    saved.write_text(PAGE, encoding="utf-8")
    path = write_sites(tmp_path, [PROFILE])
    monkeypatch.setattr("src.scrapers.generic.DEFAULT_SITES", path)
    monkeypatch.setattr("src.scrapers.registry.DEFAULT_SITES", path)

    listing = import_file(saved, "testsite", "123456", "https://example.test/x-123456.htm")

    assert listing.marketplace == "testsite"
    assert listing.title.startswith("MSI RTX 3080 Ti")
