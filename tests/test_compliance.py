from datetime import date

import pytest

from src.core.models import AutomationStatus
from src.scrapers.compliance import (
    UNVERIFIED,
    AccessVerification,
    ComplianceError,
    assert_fetch_allowed,
    robots_allows,
)
from src.scrapers.registry import get_connector

VERIFIED = AccessVerification(
    terms_url="https://example.com/terms",
    verified_on=date(2026, 8, 18),
    permitted_use="documented feed",
    requires_authentication=False,
)


def test_research_status_blocks_fetch():
    with pytest.raises(ComplianceError):
        assert_fetch_allowed("x", AutomationStatus.RESEARCH, VERIFIED)


def test_automated_without_verification_blocks_fetch():
    with pytest.raises(ComplianceError):
        assert_fetch_allowed("x", AutomationStatus.AUTOMATED, UNVERIFIED)


def test_automated_with_verification_allowed():
    assert_fetch_allowed("x", AutomationStatus.AUTOMATED, VERIFIED) is None


@pytest.mark.parametrize("marketplace", ["kupujemprodajem", "kleinanzeigen"])
def test_connectors_ship_unverified_and_refuse_to_fetch(marketplace):
    connector = get_connector(marketplace)
    assert connector.health_check()["access_verified"] is False
    with pytest.raises(ComplianceError):
        connector.fetch(f"{connector.access.base_url}/anything")


def test_robots_disallow_is_respected():
    robots = "User-agent: *\nDisallow: /private\n"
    assert robots_allows("https://example.com/public", "bot", fetcher=lambda _: robots)
    assert not robots_allows("https://example.com/private/x", "bot", fetcher=lambda _: robots)


def test_unreachable_robots_is_treated_as_disallowed():
    def failing(_):
        raise OSError("network down")

    assert not robots_allows("https://example.com/x", "bot", fetcher=failing)
