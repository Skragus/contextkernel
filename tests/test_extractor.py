"""Tests for the value extractor."""

from datetime import datetime, timezone

from app.kernel.extractor import extract_batch, extract_value


class TestExtractValue:
    def test_known_type_with_value_key(self):
        row = {"record_type": "step_count", "data": {"value": 8500}}
        assert extract_value(row) == 8500.0

    def test_known_type_string_value(self):
        row = {"record_type": "heart_rate", "data": {"value": "72.5"}}
        assert extract_value(row) == 72.5

    def test_unknown_type_first_numeric(self):
        row = {"record_type": "something_new", "data": {"foo": "bar", "metric": 42}}
        assert extract_value(row) == 42.0

    def test_nested_value(self):
        row = {"record_type": "something_new", "data": {"nested": {"deep": 3.14}}}
        assert extract_value(row) == 3.14

    def test_none_data(self):
        row = {"record_type": "step_count", "data": None}
        assert extract_value(row) is None

    def test_empty_dict(self):
        row = {"record_type": "step_count", "data": {}}
        assert extract_value(row) is None

    def test_no_numeric_anywhere(self):
        row = {"record_type": "unknown", "data": {"a": "text", "b": "more"}}
        assert extract_value(row) is None

    def test_boolean_not_extracted(self):
        row = {"record_type": "unknown", "data": {"flag": True, "val": 5}}
        assert extract_value(row) == 5.0

    def test_missing_record_type(self):
        row = {"data": {"value": 10}}
        assert extract_value(row) == 10.0

    def test_corrupt_data_no_crash(self):
        row = {"record_type": "step_count", "data": object()}
        result = extract_value(row)
        assert result is None

    def test_nested_dot_path(self):
        """Config path like 'heart_rate_summary.avg_bpm' into a daily blob."""
        row = {
            "record_type": "heart_rate_avg",
            "data": {"heart_rate_summary": {"avg_bpm": 72, "resting_bpm": 58}},
        }
        assert extract_value(row) == 72.0

    def test_list_index_path(self):
        """Config path like 'sleep_sessions.0.duration_minutes'."""
        row = {
            "record_type": "sleep_duration",
            "data": {
                "sleep_sessions": [
                    {"duration_minutes": 450, "efficiency": 88},
                ]
            },
        }
        assert extract_value(row) == 450.0

    def test_list_index_out_of_bounds_falls_back(self):
        """Empty list should not crash — falls back to first-numeric."""
        row = {
            "record_type": "sleep_duration",
            "data": {"sleep_sessions": [], "some_number": 99},
        }
        assert extract_value(row) == 99.0

    def test_deep_nested_blob_path(self):
        """Config path like 'sleep_sessions.0.stages.deep_minutes'."""
        row = {
            "record_type": "sleep_deep",
            "data": {
                "sleep_sessions": [
                    {"stages": {"deep_minutes": 125, "rem_minutes": 80}},
                ]
            },
        }
        assert extract_value(row) == 125.0

    def test_top_level_numeric_path(self):
        """Config path like 'steps_total' — top-level key in blob."""
        row = {
            "record_type": "steps_total",
            "data": {"steps_total": 8432, "other": "stuff"},
        }
        assert extract_value(row) == 8432.0

    def test_nutrition_nested_path(self):
        row = {
            "record_type": "calories_consumed",
            "data": {
                "nutrition_summary": {
                    "calories_consumed": 2450,
                    "protein_g": 145,
                }
            },
        }
        assert extract_value(row) == 2450.0


class TestExtractBatch:
    def test_basic(self):
        ts = datetime(2026, 2, 15, 12, 0, tzinfo=timezone.utc)
        rows = [
            {"record_type": "step_count", "start_date": ts, "data": {"value": 100}},
            {"record_type": "step_count", "start_date": ts, "data": {"value": 200}},
        ]
        pairs = extract_batch(rows)
        assert len(pairs) == 2
        assert pairs[0] == (ts, 100.0)
        assert pairs[1] == (ts, 200.0)

    def test_skips_bad_rows(self):
        ts = datetime(2026, 2, 15, 12, 0, tzinfo=timezone.utc)
        rows = [
            {"record_type": "step_count", "start_date": ts, "data": {"value": 100}},
            {"record_type": "step_count", "start_date": ts, "data": None},
            {"record_type": "step_count", "start_date": ts, "data": {"value": 300}},
        ]
        pairs = extract_batch(rows)
        assert len(pairs) == 2

    def test_empty(self):
        assert extract_batch([]) == []
