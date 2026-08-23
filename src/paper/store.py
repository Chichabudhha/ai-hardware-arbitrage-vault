"""Append-only JSONL stores for paper predictions and outcomes.

Same contract as the observation store: a line is never edited or deleted, and a
malformed line is an error rather than a row skipped in silence (CLAUDE.md
principle 6). A correction is a new outcome line for the same prediction_id; the
latest observed_at wins when pairing, but the earlier line stays on disk.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from src.paper.records import OutcomeType, PaperOutcome, PaperPrediction

DEFAULT_PREDICTIONS = Path("data/paper/predictions.jsonl")
DEFAULT_OUTCOMES = Path("data/paper/outcomes.jsonl")


class PaperStoreError(ValueError):
    """A stored paper record could not be read as written."""


def _load(path: str | Path, model: type[PaperPrediction] | type[PaperOutcome]) -> list:
    store = Path(path)
    if not store.exists():
        raise PaperStoreError(f"no paper store at {store}")

    records = []
    for line_no, raw in enumerate(store.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            records.append(model.model_validate_json(raw))
        except ValidationError as exc:
            raise PaperStoreError(f"{store}:{line_no} is not a usable record: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise PaperStoreError(f"{store}:{line_no} is not valid JSON: {exc}") from exc
    return records


def _append(path: str | Path, record: PaperPrediction | PaperOutcome) -> None:
    store = Path(path)
    store.parent.mkdir(parents=True, exist_ok=True)
    with store.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")


def load_predictions(path: str | Path = DEFAULT_PREDICTIONS) -> list[PaperPrediction]:
    return _load(path, PaperPrediction)


def load_outcomes(path: str | Path = DEFAULT_OUTCOMES) -> list[PaperOutcome]:
    return _load(path, PaperOutcome)


def append_prediction(record: PaperPrediction, path: str | Path = DEFAULT_PREDICTIONS) -> None:
    _append(path, record)


def append_outcome(record: PaperOutcome, path: str | Path = DEFAULT_OUTCOMES) -> None:
    _append(path, record)


# A listing that sold or vanished has nothing left to check. UNSOLD and
# PRICE_CUT are progress reports, not conclusions, so they stay on the list.
TERMINAL_OUTCOMES = frozenset({OutcomeType.SOLD, OutcomeType.DELISTED})


def open_watchlist(
    pairs: list[tuple[PaperPrediction, PaperOutcome | None]],
) -> list[tuple[PaperPrediction, PaperOutcome | None]]:
    """Candidates still worth re-checking, oldest first.

    Every scored candidate is watched, not only the ones worth buying: a card
    that was too expensive and then sells anyway tells us the market pays that
    price, and a price cut tells us the seller could not get it. Both are the
    price signal this system otherwise lacks.
    """
    open_pairs = [
        (prediction, outcome)
        for prediction, outcome in pairs
        if outcome is None or outcome.outcome not in TERMINAL_OUTCOMES
    ]
    return sorted(open_pairs, key=lambda pair: pair[0].predicted_at)


def pair_records(
    predictions: list[PaperPrediction],
    outcomes: list[PaperOutcome],
) -> list[tuple[PaperPrediction, PaperOutcome | None]]:
    """Join each prediction with its latest outcome, if one was observed.

    An outcome whose prediction_id matches nothing is an error: it means the
    owner typed an id that does not exist, and silently dropping it would hide
    a real observation.
    """
    by_id: dict[str, PaperOutcome] = {}
    known = {prediction.prediction_id for prediction in predictions}
    for outcome in outcomes:
        if outcome.prediction_id not in known:
            raise PaperStoreError(
                f"outcome refers to unknown prediction_id '{outcome.prediction_id}'"
            )
        current = by_id.get(outcome.prediction_id)
        # Ties keep the later line: an appended correction is written after the
        # record it corrects.
        if current is None or outcome.observed_at >= current.observed_at:
            by_id[outcome.prediction_id] = outcome
    return [(p, by_id.get(p.prediction_id)) for p in predictions]
