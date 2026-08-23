import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.core.models import Condition, PriceObservation, PriceType
from src.pricing.observations import (
    ObservationError,
    append_observation,
    load_observations,
    observations_from_csv,
)

NOW = datetime(2026, 8, 19, tzinfo=timezone.utc)

RECORD = {
    "product_id": "rtx-3090",
    "price_amount": "102000",
    "currency": "RSD",
    "price_type": "asking",
    "condition": "used",
    "observed_at": "2026-08-18T10:00:00+00:00",
    "marketplace": "kupujemprodajem",
    "source_listing_id": "kp-1",
}


def write(tmp_path, records):
    store = tmp_path / "serbia.jsonl"
    store.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )
    return store


def test_round_trip_preserves_price_exactly(tmp_path):
    store = write(tmp_path, [RECORD])
    (loaded,) = load_observations(store)
    assert loaded.price_amount == Decimal("102000")
    assert loaded.currency == "RSD"
    assert loaded.price_type is PriceType.ASKING


def test_blank_lines_are_ignored(tmp_path):
    store = tmp_path / "serbia.jsonl"
    store.write_text(json.dumps(RECORD) + "\n\n\n", encoding="utf-8")
    assert len(load_observations(store)) == 1


def test_malformed_line_is_an_error_not_a_silent_skip(tmp_path):
    """A dropped observation shifts every percentile that depended on it."""
    store = tmp_path / "serbia.jsonl"
    store.write_text(json.dumps(RECORD) + "\n{not json}\n", encoding="utf-8")
    with pytest.raises(ObservationError) as exc:
        load_observations(store)
    assert "serbia.jsonl:2" in str(exc.value)


def test_missing_price_is_an_error(tmp_path):
    broken = {k: v for k, v in RECORD.items() if k != "price_amount"}
    with pytest.raises(ObservationError):
        load_observations(write(tmp_path, [broken]))


def test_missing_timestamp_is_an_error(tmp_path):
    broken = {k: v for k, v in RECORD.items() if k != "observed_at"}
    with pytest.raises(ObservationError):
        load_observations(write(tmp_path, [broken]))


def test_unknown_price_type_is_an_error(tmp_path):
    broken = dict(RECORD, price_type="guessed")
    with pytest.raises(ObservationError):
        load_observations(write(tmp_path, [broken]))


def test_naive_timestamp_is_read_as_utc(tmp_path):
    naive = dict(RECORD, observed_at="2026-08-18T10:00:00")
    (loaded,) = load_observations(write(tmp_path, [naive]))
    assert loaded.observed_at.tzinfo is not None


def test_missing_store_is_an_error(tmp_path):
    with pytest.raises(ObservationError):
        load_observations(tmp_path / "nope.jsonl")


def test_float_price_keeps_its_digits(tmp_path):
    """JSON floats lose precision; the loader must go through str, not float."""
    (loaded,) = load_observations(write(tmp_path, [dict(RECORD, price_amount=102000.55)]))
    assert loaded.price_amount == Decimal("102000.55")


def test_append_does_not_touch_existing_lines(tmp_path):
    store = write(tmp_path, [RECORD])
    before = store.read_text(encoding="utf-8")
    append_observation(
        store,
        PriceObservation(
            product_id="rtx-3090",
            price_amount=Decimal("99000"),
            currency="RSD",
            price_type=PriceType.ASKING,
            condition=Condition.USED,
            observed_at=NOW,
            marketplace="kupujemprodajem",
            source_listing_id="kp-2",
        ),
    )
    after = store.read_text(encoding="utf-8")
    assert after.startswith(before)
    assert len(load_observations(store)) == 2


def test_appended_observation_reloads_identically(tmp_path):
    store = tmp_path / "new" / "serbia.jsonl"
    original = PriceObservation(
        product_id="rtx-4080-super",
        price_amount=Decimal("135000"),
        currency="RSD",
        price_type=PriceType.SOLD,
        condition=Condition.USED,
        observed_at=NOW,
        marketplace="kupujemprodajem",
        source_listing_id="kp-9",
        is_bundle=False,
    )
    append_observation(store, original)
    (loaded,) = load_observations(store)
    assert loaded == original


# --- CSV bulk import (W6 manual collection) ---------------------------------

CSV_HEADER = (
    "product_id,price_amount,currency,price_type,condition,observed_at,"
    "marketplace,source_listing_id,url,is_bundle\n"
)


def write_csv(tmp_path, rows: str, header: str = CSV_HEADER):
    path = tmp_path / "listings.csv"
    path.write_text(header + rows, encoding="utf-8")
    return path


def test_csv_rows_become_observations(tmp_path):
    path = write_csv(
        tmp_path,
        "rtx-3090,99000,RSD,asking,used,2026-08-18T10:00:00+00:00,"
        "kupujemprodajem,kp-1,https://example.rs/1,\n"
        "rtx-3090,105000,RSD,asking,used,2026-08-18T11:00:00+00:00,"
        "kupujemprodajem,kp-2,https://example.rs/2,da\n",
    )
    first, second = observations_from_csv(path)

    assert first.product_id == "rtx-3090"
    assert first.price_amount == Decimal("99000")
    assert first.is_bundle is False
    assert second.is_bundle is True


def test_csv_missing_required_column_rejects_the_whole_file(tmp_path):
    path = write_csv(
        tmp_path,
        "rtx-3090,99000,RSD\n",
        header="product_id,price_amount,currency\n",
    )
    with pytest.raises(ObservationError, match="missing columns"):
        observations_from_csv(path)


def test_csv_bad_row_names_its_line_number(tmp_path):
    path = write_csv(
        tmp_path,
        "rtx-3090,99000,RSD,asking,used,2026-08-18T10:00:00+00:00,"
        "kupujemprodajem,kp-1,https://example.rs/1,\n"
        "rtx-3090,not-a-price,RSD,asking,used,2026-08-18T11:00:00+00:00,"
        "kupujemprodajem,kp-2,https://example.rs/2,\n",
    )
    with pytest.raises(ObservationError, match="3 has no usable price_amount"):
        observations_from_csv(path)


def test_csv_empty_optional_cells_fall_back_to_defaults(tmp_path):
    path = write_csv(
        tmp_path,
        "rtx-3090,99000,RSD,,,2026-08-18T10:00:00+00:00,kupujemprodajem,kp-1,,\n",
    )
    (observation,) = observations_from_csv(path)

    assert observation.price_type is PriceType.ASKING
    assert observation.condition is Condition.UNKNOWN
    assert observation.url is None
