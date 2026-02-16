"""Tests for pure feature functions."""

from datetime import datetime, timezone

from app.kernel.features import (
    aggregate,
    baseline_window,
    compute_delta,
    compute_delta_pct,
    coverage_ratio,
    detect_partial_days,
    trailing_average,
)


class TestTrailingAverage:
    def test_basic(self):
        assert trailing_average([2.0, 4.0, 6.0]) == 4.0

    def test_windowed(self):
        assert trailing_average([1, 2, 3, 4, 5], window=3) == 4.0

    def test_empty(self):
        assert trailing_average([]) is None

    def test_single(self):
        assert trailing_average([7.0]) == 7.0


class TestAggregate:
    def test_sum(self):
        assert aggregate([1.0, 2.0, 3.0], "sum") == 6.0

    def test_avg(self):
        assert aggregate([2.0, 4.0], "avg") == 3.0

    def test_max(self):
        assert aggregate([1.0, 5.0, 3.0], "max") == 5.0

    def test_min(self):
        assert aggregate([1.0, 5.0, 3.0], "min") == 1.0

    def test_last(self):
        assert aggregate([1.0, 2.0, 9.0], "last") == 9.0

    def test_empty(self):
        assert aggregate([], "sum") is None

    def test_unknown_method_falls_back_to_avg(self):
        assert aggregate([2.0, 4.0], "unknown") == 3.0


class TestBaselineWindow:
    def test_daily(self):
        assert baseline_window("daily") == 7

    def test_weekly(self):
        assert baseline_window("weekly") == 4

    def test_monthly(self):
        assert baseline_window("monthly") == 3

    def test_unknown(self):
        assert baseline_window("hourly") == 7


class TestDelta:
    def test_basic(self):
        assert compute_delta(10.0, 8.0) == 2.0

    def test_none_current(self):
        assert compute_delta(None, 8.0) is None

    def test_none_baseline(self):
        assert compute_delta(10.0, None) is None

    def test_pct(self):
        result = compute_delta_pct(12.0, 10.0)
        assert result is not None
        assert abs(result - 20.0) < 0.01

    def test_pct_zero_baseline(self):
        assert compute_delta_pct(5.0, 0.0) is None


class TestCoverage:
    def test_full(self):
        assert coverage_ratio(7, 7) == 1.0

    def test_partial(self):
        assert abs(coverage_ratio(3, 7) - 3 / 7) < 0.001

    def test_zero_expected(self):
        assert coverage_ratio(5, 0) == 0.0

    def test_over(self):
        assert coverage_ratio(10, 7) == 1.0


class TestPartialDays:
    def test_empty(self):
        assert detect_partial_days([]) == []

    def test_uniform(self):
        ts = [datetime(2026, 2, 15, h, tzinfo=timezone.utc) for h in range(10)]
        assert detect_partial_days(ts) == []

    def test_detects_partial(self):
        ts = (
            [datetime(2026, 2, 15, h, tzinfo=timezone.utc) for h in range(10)]
            + [datetime(2026, 2, 16, h, tzinfo=timezone.utc) for h in range(10)]
            + [datetime(2026, 2, 17, 0, tzinfo=timezone.utc)]  # only 1 record
        )
        partial = detect_partial_days(ts)
        assert "2026-02-17" in partial
