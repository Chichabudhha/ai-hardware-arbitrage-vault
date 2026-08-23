"""Load Serbian price observations from a JSONL store.

Append-only by convention: a new price for the same listing is a new line, never
an edit of an old one (CLAUDE.md principle 6). A malformed line is an error, not
a row to skip quietly — a silently dropped observation shifts every percentile
that depends on it.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from src.core.models import Condition, PriceObservation, PriceType


class ObservationError(ValueError):
    """A stored observation could not be read as written."""


def _parse_line(raw: str, path: Path, line_no: int) -> PriceObservation:
    try:
        record = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ObservationError(f"{path}:{line_no} is not valid JSON: {exc}") from exc

    try:
        observed_at = datetime.fromisoformat(record["observed_at"])
    except (KeyError, ValueError) as exc:
        raise ObservationError(f"{path}:{line_no} has no usable observed_at") from exc
    if observed_at.tzinfo is None:
        # A naive timestamp cannot be compared against the freshness window
        # without inventing a zone; assume UTC and say so in the store format.
        observed_at = observed_at.replace(tzinfo=timezone.utc)

    try:
        price = Decimal(str(record["price_amount"]))
    except (KeyError, InvalidOperation) as exc:
        raise ObservationError(f"{path}:{line_no} has no usable price_amount") from exc

    try:
        return PriceObservation(
            product_id=record["product_id"],
            price_amount=price,
            currency=record["currency"],
            price_type=PriceType(record.get("price_type", PriceType.ASKING.value)),
            condition=Condition(record.get("condition", Condition.UNKNOWN.value)),
            observed_at=observed_at,
            marketplace=record["marketplace"],
            source_listing_id=record["source_listing_id"],
            url=record.get("url"),
            is_bundle=bool(record.get("is_bundle", False)),
        )
    except (KeyError, ValueError) as exc:
        raise ObservationError(f"{path}:{line_no} is not a usable observation: {exc}") from exc


def load_observations(path: str | Path) -> list[PriceObservation]:
    """Read every observation in a JSONL file, in file order."""
    store = Path(path)
    if not store.exists():
        raise ObservationError(f"no observation store at {store}")

    observations: list[PriceObservation] = []
    for line_no, raw in enumerate(store.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        observations.append(_parse_line(raw, store, line_no))
    return observations


CSV_REQUIRED = (
    "product_id",
    "price_amount",
    "currency",
    "observed_at",
    "marketplace",
    "source_listing_id",
)


def observations_from_csv(path: str | Path) -> list[PriceObservation]:
    """Read a hand-filled CSV of Serbian listings into observations.

    The manual collection path needs a bulk entry point: typing 100 listings one
    CLI flag at a time is how observations stop being collected. A row missing a
    required column is an error — the whole file is rejected rather than
    partially imported, so the store never ends up half-written.

    Columns: product_id, price_amount, currency, observed_at, marketplace,
    source_listing_id, and optionally price_type, condition, url, is_bundle.
    """
    source = Path(path)
    if not source.exists():
        raise ObservationError(f"no CSV at {source}")

    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in CSV_REQUIRED if column not in (reader.fieldnames or [])]
        if missing:
            raise ObservationError(f"{source} is missing columns: {', '.join(missing)}")

        observations: list[PriceObservation] = []
        for row_no, row in enumerate(reader, start=2):  # row 1 is the header
            record = {key: (value.strip() if isinstance(value, str) else value)
                      for key, value in row.items() if key is not None}
            record = {key: value for key, value in record.items() if value not in ("", None)}
            record["is_bundle"] = str(record.get("is_bundle", "")).lower() in {"1", "true", "yes", "da"}
            observations.append(_parse_line(json.dumps(record, ensure_ascii=False), source, row_no))
    return observations


def append_observation(path: str | Path, observation: PriceObservation) -> None:
    """Append one observation. Existing lines are never touched (principle 6)."""
    store = Path(path)
    store.parent.mkdir(parents=True, exist_ok=True)
    record = observation.model_dump(mode="json")
    with store.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
