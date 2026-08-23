"""Connector lookup by marketplace name.

Hand-written connectors win over config profiles: a site with its own parser has
been looked at by a person, and a JSON row must never silently replace that.
"""

from __future__ import annotations

from pathlib import Path

from src.scrapers.base import BaseConnector
from src.scrapers.generic import DEFAULT_SITES, GenericManualConnector, load_profiles
from src.scrapers.kleinanzeigen import KleinanzeigenConnector
from src.scrapers.kupujemprodajem import KupujemProdajemConnector

_CONNECTORS: dict[str, type[BaseConnector]] = {
    KupujemProdajemConnector.access.marketplace: KupujemProdajemConnector,
    KleinanzeigenConnector.access.marketplace: KleinanzeigenConnector,
}


def _profiles(path: str | Path | None = None) -> dict[str, GenericManualConnector]:
    """Config-driven profiles, minus any name a real connector already owns.

    The path is resolved per call rather than bound as a default, so tests and
    callers can point at another file without reimporting the module.
    """
    path = DEFAULT_SITES if path is None else path
    return {
        profile.marketplace: GenericManualConnector(profile)
        for profile in load_profiles(path)
        if profile.marketplace not in _CONNECTORS
    }


def get_connector(marketplace: str, sites: str | Path | None = None) -> BaseConnector:
    connector = _CONNECTORS.get(marketplace)
    if connector is not None:
        return connector()

    profile = _profiles(sites).get(marketplace)
    if profile is not None:
        return profile

    known = sorted(set(_CONNECTORS) | set(_profiles(sites)))
    raise KeyError(f"unknown marketplace '{marketplace}'; known: {known}")


def list_connectors(sites: str | Path | None = None) -> list[BaseConnector]:
    return [cls() for cls in _CONNECTORS.values()] + list(_profiles(sites).values())
