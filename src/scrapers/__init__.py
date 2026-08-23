"""Connector layer: transport/access only, no interpretation (ARCHITECTURE.md)."""

from src.scrapers.base import BaseConnector, ConnectorAccess
from src.scrapers.registry import get_connector, list_connectors

__all__ = ["BaseConnector", "ConnectorAccess", "get_connector", "list_connectors"]
