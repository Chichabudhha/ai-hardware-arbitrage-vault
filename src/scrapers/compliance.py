"""Compliance gate for marketplace access.

MARKETPLACE-STRATEGY.md: RESEARCH -> MANUAL -> API/FEED -> AUTOMATED, and only
after access verification. CLAUDE.md principle 7 forbids bypassing authentication,
rate limits, robots.txt, access controls or ToS — so this module deliberately
provides no proxy rotation, no user-agent spoofing and no anti-bot evasion.
Fetching is blocked unless a connector's access has been verified and recorded.
"""

from __future__ import annotations

import urllib.robotparser
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlparse

from src.core.models import AutomationStatus


class ComplianceError(Exception):
    """Access is not permitted or not yet verified."""


@dataclass(frozen=True)
class AccessVerification:
    """Recorded outcome of the compliance gate for one marketplace.

    Never fill this in speculatively — `verified_on` and `terms_url` must reflect
    an actual check by the owner, recorded in odluke/.
    """

    terms_url: str | None
    verified_on: date | None
    permitted_use: str | None
    requires_authentication: bool | None
    notes: str = ""

    @property
    def is_verified(self) -> bool:
        return bool(self.terms_url and self.verified_on and self.permitted_use)


UNVERIFIED = AccessVerification(
    terms_url=None,
    verified_on=None,
    permitted_use=None,
    requires_authentication=None,
    notes="Compliance gate not yet passed — see odluke/ D-006 / D-007.",
)


def assert_fetch_allowed(
    marketplace: str,
    status: AutomationStatus,
    verification: AccessVerification,
) -> None:
    """Raise unless automated fetching is genuinely permitted for this connector."""
    if status in (AutomationStatus.RESEARCH, AutomationStatus.MANUAL):
        raise ComplianceError(
            f"{marketplace}: automation_status={status.value}. "
            "Use manual import (src.scrapers.manual_import) until access is verified."
        )
    if not verification.is_verified:
        raise ComplianceError(
            f"{marketplace}: access verification incomplete "
            "(terms_url, verified_on and permitted_use are all required)."
        )


def robots_allows(url: str, user_agent: str, fetcher=None) -> bool:
    """Check robots.txt for `url`. A failed check is treated as 'not allowed'."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    try:
        if fetcher is not None:
            parser.parse(fetcher(robots_url).splitlines())
        else:
            parser.set_url(robots_url)
            parser.read()
    except Exception:
        return False
    return parser.can_fetch(user_agent, url)
