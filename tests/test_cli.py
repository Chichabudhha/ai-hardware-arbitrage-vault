"""CLI-level regression tests.

Unlike the unit tests in test_paper.py, these exercise the actual command
functions the way `python -m src.cli ...` invokes them, with real files on
disk. Some bugs only show up at this layer: predictions and watched listings
share the outcome store, but `pair_records` only knows about predictions, so
naive wiring between the two blows up once a watch item has an outcome.
"""

from __future__ import annotations

from argparse import Namespace
from datetime import datetime, timezone
from decimal import Decimal

from src.cli import cmd_report, cmd_watch
from src.core.models import RiskLevel, Verdict
from src.paper.records import OutcomeType, PaperOutcome, PaperPrediction
from src.paper.store import append_outcome, append_prediction
from src.paper.watchlist import WatchItem, append_watch_items

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


def _prediction() -> PaperPrediction:
    return PaperPrediction(
        prediction_id="kleinanzeigen:3488481508:20260819T082701Z",
        predicted_at=NOW,
        marketplace="kleinanzeigen",
        source_listing_id="3488481508",
        url="https://www.kleinanzeigen.de/s-anzeige/x/3488481508",
        title="EVGA GeForce RTX 3080Ti",
        product_id="rtx-3080-ti",
        listing_price_amount=Decimal("300"),
        listing_currency="EUR",
        landed_cost_eur=None,
        expected_sale_eur=None,
        expected_profit_eur=None,
        expected_roi_pct=None,
        risk=RiskLevel.MEDIUM,
        verdict=Verdict.WATCH,
        confidence=None,
        missing_inputs=[],
    )


def _watch_item() -> WatchItem:
    return WatchItem(
        watch_id="watch:willhaben:1900028284",
        marketplace="willhaben",
        source_listing_id="1900028284",
        product_id="rtx-3080-ti",
        url="https://www.willhaben.at/iad/1900028284",
        asking_amount=Decimal("400"),
        asking_currency="EUR",
        first_seen_at=NOW,
    )


def _seed(tmp_path):
    predictions_path = tmp_path / "predictions.jsonl"
    outcomes_path = tmp_path / "outcomes.jsonl"
    watchlist_path = tmp_path / "watchlist.jsonl"

    append_prediction(_prediction(), predictions_path)
    append_watch_items([_watch_item()], watchlist_path)

    # One outcome for the prediction, one for the watch item — this is the
    # real-world mix that triggered the bug.
    append_outcome(
        PaperOutcome(
            prediction_id="kleinanzeigen:3488481508:20260819T082701Z",
            outcome=OutcomeType.UNSOLD,
            observed_at=NOW,
        ),
        outcomes_path,
    )
    append_outcome(
        PaperOutcome(
            prediction_id="watch:willhaben:1900028284",
            outcome=OutcomeType.DELISTED,
            observed_at=NOW,
        ),
        outcomes_path,
    )

    return predictions_path, outcomes_path, watchlist_path


def test_watch_does_not_choke_on_a_watch_items_outcome(tmp_path, capsys):
    predictions_path, outcomes_path, watchlist_path = _seed(tmp_path)

    args = Namespace(
        add_market=None,
        predictions=str(predictions_path),
        outcomes=str(outcomes_path),
        watchlist=str(watchlist_path),
        marketplace=None,
    )

    assert cmd_watch(args) == 0
    out = capsys.readouterr().out
    # The DELISTED watch item is terminal and drops off the list; the UNSOLD
    # prediction is still open and should still be shown.
    assert "kleinanzeigen:3488481508:20260819T082701Z" in out
    assert "watch:willhaben:1900028284" not in out


def test_report_does_not_choke_on_a_watch_items_outcome(tmp_path, capsys):
    """The watch item's outcome must not reach pair_records as a stray id.

    With one prediction and zero priced outcomes the report is legitimately
    INSUFFICIENT_DATA (exit 1) — the point of this test is that it gets that
    far without `pair_records` raising over the watch item's outcome.
    """
    predictions_path, outcomes_path, _ = _seed(tmp_path)

    args = Namespace(predictions=str(predictions_path), outcomes=str(outcomes_path))

    assert cmd_report(args) == 1
    out = capsys.readouterr().out
    assert "INSUFFICIENT_DATA" in out
