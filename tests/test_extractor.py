"""Tests for the value extractor (health_connect_daily raw_data)."""

from datetime import date

from app.kernel.extractor import extract_signal, extract_signals_from_row, extract_signal_series
from app.kernel.signal_map import get_signal_config


def _row(raw: dict) -> dict:
    """Wrap payload in raw_data structure."""
    return {"device_id": "x", "date": date(2026, 2, 16), "raw_data": raw}


class TestExtractSignal:
    def test_steps_total(self):
        row = _row({"steps_total": 2530})
        cfg = get_signal_config("steps_total")
        assert cfg is not None
        assert extract_signal(row, cfg) == 2530.0

    def test_body_metrics_weight(self):
        row = _row({"body_metrics": {"weight_kg": 130.16, "body_fat_percentage": 40.9}})
        cfg = get_signal_config("weight_kg")
        assert cfg is not None
        assert extract_signal(row, cfg) == 130.16

    def test_heart_rate_summary(self):
        row = _row({"heart_rate_summary": {"avg_hr": 76, "max_hr": 109, "min_hr": 58, "resting_hr": 76}})
        cfg = get_signal_config("avg_hr")
        assert cfg is not None
        assert extract_signal(row, cfg) == 76.0

    def test_sleep_sessions_array(self):
        row = _row({
            "sleep_sessions": [
                {"start_time": "2026-02-16T02:40:00Z", "end_time": "2026-02-16T11:10:00Z", "duration_minutes": 510}
            ]
        })
        cfg = get_signal_config("sleep_duration_minutes")
        assert cfg is not None
        assert extract_signal(row, cfg) == 510.0

    def test_missing_raw_data(self):
        row = {}
        cfg = get_signal_config("steps_total")
        assert cfg is not None
        assert extract_signal(row, cfg) is None

    def test_missing_path_in_raw_data(self):
        row = _row({"body_metrics": {}})
        cfg = get_signal_config("weight_kg")
        assert cfg is not None
        assert extract_signal(row, cfg) is None

    def test_empty_sleep_sessions(self):
        row = _row({"sleep_sessions": []})
        cfg = get_signal_config("sleep_duration_minutes")
        assert cfg is not None
        assert extract_signal(row, cfg) is None

    def test_calories_total(self):
        row = _row({"nutrition_summary": {"calories_total": 1736, "protein_grams": 41.38}})
        cfg = get_signal_config("calories_total")
        assert cfg is not None
        assert extract_signal(row, cfg) == 1736.0


class TestExtractSignalsFromRow:
    def test_extracts_all_present(self):
        row = _row({
            "steps_total": 2530,
            "body_metrics": {"weight_kg": 130.16, "body_fat_percentage": 40.9},
            "heart_rate_summary": {"avg_hr": 76, "max_hr": 109, "min_hr": 58, "resting_hr": 76},
            "sleep_sessions": [{"duration_minutes": 510}],
        })
        vals = extract_signals_from_row(row)
        assert vals["steps_total"] == 2530.0
        assert vals["weight_kg"] == 130.16
        assert vals["avg_hr"] == 76.0
        assert vals["sleep_duration_minutes"] == 510.0

    def test_skips_missing(self):
        row = _row({"steps_total": 100})
        vals = extract_signals_from_row(row)
        assert "steps_total" in vals
        assert vals["steps_total"] == 100.0
        assert "weight_kg" not in vals


class TestExtractSignalSeries:
    def test_basic(self):
        rows = [
            _row({"steps_total": 100}),
            _row({"steps_total": 200, "heart_rate_summary": {"avg_hr": 72}}),
        ]
        series = extract_signal_series(rows)
        assert series["steps_total"] == [100.0, 200.0]
        assert series["avg_hr"] == [72.0]

    def test_empty(self):
        series = extract_signal_series([])
        for name, vals in series.items():
            assert vals == []
