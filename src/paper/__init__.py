"""Paper trading: record predictions, observe outcomes, measure the error (W6)."""

from src.paper.calibration import CalibrationReport, CalibrationRules, calibrate
from src.paper.records import (
    OutcomeType,
    PaperOutcome,
    PaperPrediction,
    prediction_from_opportunity,
    prediction_id,
)
from src.paper.store import (
    PaperStoreError,
    open_watchlist,
    append_outcome,
    append_prediction,
    load_outcomes,
    load_predictions,
    pair_records,
)

__all__ = [
    "CalibrationReport",
    "CalibrationRules",
    "OutcomeType",
    "PaperOutcome",
    "PaperPrediction",
    "PaperStoreError",
    "append_outcome",
    "append_prediction",
    "calibrate",
    "load_outcomes",
    "load_predictions",
    "open_watchlist",
    "pair_records",
    "prediction_from_opportunity",
    "prediction_id",
]
