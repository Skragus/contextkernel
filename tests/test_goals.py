"""Tests for goals config, computation helpers, and builder integration."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.kernel.features import (
    compute_trend,
    find_tracking_start_date,
    goal_progress_pct,
    goal_status,
    manual_tracking_coverage_vector,
    tracking_consistency,
    tracking_status_from_coverage,
)
from app.kernel.goals_config import GOALS_BY_SIGNAL, get_goal, list_goals
from app.kernel.builders import build_daily_summary
from tests.conftest import make_daily_row


# ---------------------------------------------------------------------------
# Goals config
# ---------------------------------------------------------------------------

class TestGoalsConfig:
    def test_three_goals_configured(self):
        goals = list_goals()
        assert len(goals) == 3

    def test_get_known_goal(self):
        g = get_goal("steps_total")
        assert g is not None
        assert g.priority == 3
        assert g.target_value == 8000.0

    def test_get_unknown_goal(self):
        assert get_goal("nonexistent_signal") is None

    def test_priorities_are_1_through_3(self):
        priorities = {g.priority for g in list_goals()}
        assert priorities == {1, 2, 3}

    def test_tracking_consistency_is_t1(self):
        g = get_goal("tracking_consistency")
        assert g is not None
        assert g.priority == 1
        assert g.target_type == "minimum"

    def test_calories_is_t2(self):
        g = get_goal("calories_total")
        assert g is not None
        assert g.priority == 2
        assert g.target_type == "maximum"


# ---------------------------------------------------------------------------
# Goal progress computation
# ---------------------------------------------------------------------------

class TestGoalProgressPct:
    def test_minimum_exact_hit(self):
        assert goal_progress_pct(8000, 8000.0, "minimum") == 100.0

    def test_minimum_over(self):
        assert goal_progress_pct(10000, 8000.0, "minimum") == 100.0

    def test_minimum_under(self):
        result = goal_progress_pct(4000, 8000.0, "minimum")
        assert result is not None
        assert abs(result - 50.0) < 0.01

    def test_maximum_under(self):
        assert goal_progress_pct(1500, 2000.0, "maximum") == 100.0

    def test_maximum_over(self):
        result = goal_progress_pct(3000, 2000.0, "maximum")
        assert result is not None
        assert abs(result - 66.67) < 0.1

    def test_exact_on_target(self):
        assert goal_progress_pct(2000, 2000.0, "exact") == 100.0

    def test_none_value(self):
        assert goal_progress_pct(None, 8000.0, "minimum") is None

    def test_zero_target(self):
        assert goal_progress_pct(100, 0.0, "minimum") is None


# ---------------------------------------------------------------------------
# Goal status
# ---------------------------------------------------------------------------

class TestGoalStatus:
    def test_green(self):
        assert goal_status(100.0) == "green"

    def test_yellow(self):
        assert goal_status(75.0) == "yellow"

    def test_red_low(self):
        assert goal_status(30.0) == "red"

    def test_red_none(self):
        assert goal_status(None) == "red"

    def test_boundary_50(self):
        assert goal_status(50.0) == "yellow"

    def test_boundary_100(self):
        assert goal_status(100.0) == "green"


# ---------------------------------------------------------------------------
# Trend computation
# ---------------------------------------------------------------------------

class TestComputeTrend:
    def test_up(self):
        assert compute_trend([10, 12, 14], [5, 6, 7]) == "up"

    def test_down(self):
        assert compute_trend([3, 4, 5], [10, 12, 14]) == "down"

    def test_flat(self):
        assert compute_trend([10, 10, 10], [10, 10, 10]) == "flat"

    def test_empty_recent(self):
        assert compute_trend([], [10, 12]) == "flat"

    def test_empty_prior(self):
        assert compute_trend([10, 12], []) == "flat"

    def test_zero_prior(self):
        assert compute_trend([5, 5], [0, 0]) == "up"


# ---------------------------------------------------------------------------
# Tracking consistency
# ---------------------------------------------------------------------------

class TestTrackingConsistency:
    def test_full_tracking(self):
        rows = [
            make_daily_row(
                date(2026, 2, 15),
                nutrition_summary={"calories_total": 1800},
            ),
            make_daily_row(
                date(2026, 2, 16),
                body_metrics={"weight_kg": 130.0},
            ),
        ]
        result = tracking_consistency(rows, expected_days=2)
        assert result == 1.0

    def test_no_tracked_fields(self):
        rows = [
            make_daily_row(date(2026, 2, 15), steps_total=5000),
        ]
        result = tracking_consistency(rows, expected_days=1)
        assert result == 0.0

    def test_partial(self):
        rows = [
            make_daily_row(
                date(2026, 2, 15),
                nutrition_summary={"calories_total": 1500},
            ),
            make_daily_row(date(2026, 2, 16), steps_total=5000),
        ]
        result = tracking_consistency(rows, expected_days=2)
        assert result == 0.5

    def test_zero_expected(self):
        assert tracking_consistency([], expected_days=0) == 0.0


# ---------------------------------------------------------------------------
# Builder integration — goals appear on signals + priority_summary
# ---------------------------------------------------------------------------

class TestBuilderGoalIntegration:
    @pytest.mark.asyncio
    async def test_goal_fields_on_steps_signal(self):
        session = AsyncMock()
        target_rows = [
            make_daily_row(
                date(2026, 2, 15),
                steps_total=10000,
                nutrition_summary={"calories_total": 1800},
            )
        ]
        baseline_rows = [
            make_daily_row(date(2026, 2, 15) - timedelta(days=i), steps_total=7000)
            for i in range(1, 8)
        ]

        async def _fetch(sess, start, end_exclusive, device_id=None):
            if start >= date(2026, 2, 15):
                return target_rows
            return baseline_rows

        with patch("app.kernel.builders.connector.fetch_daily_rows", side_effect=_fetch):
            env = await build_daily_summary(session, date(2026, 2, 15))

        steps = next((s for s in env.signals if s.record_type == "steps_total"), None)
        assert steps is not None
        assert steps.priority == 3
        assert steps.target == 8000.0
        assert steps.target_progress_pct == 100.0
        assert steps.status == "green"
        assert steps.trend is not None

    @pytest.mark.asyncio
    async def test_calories_goal_under_target_is_green(self):
        session = AsyncMock()
        target_rows = [
            make_daily_row(
                date(2026, 2, 15),
                nutrition_summary={"calories_total": 1500},
            )
        ]

        async def _fetch(sess, start, end_exclusive, device_id=None):
            if start >= date(2026, 2, 15):
                return target_rows
            return []

        with patch("app.kernel.builders.connector.fetch_daily_rows", side_effect=_fetch):
            env = await build_daily_summary(session, date(2026, 2, 15))

        cals = next((s for s in env.signals if s.record_type == "calories_total"), None)
        assert cals is not None
        assert cals.status == "green"
        assert cals.target_progress_pct == 100.0

    @pytest.mark.asyncio
    async def test_tracking_consistency_signal_present(self):
        session = AsyncMock()
        target_rows = [
            make_daily_row(
                date(2026, 2, 15),
                nutrition_summary={"calories_total": 1800},
            )
        ]

        async def _fetch(sess, start, end_exclusive, device_id=None):
            if start >= date(2026, 2, 15):
                return target_rows
            return []

        with patch("app.kernel.builders.connector.fetch_daily_rows", side_effect=_fetch):
            env = await build_daily_summary(session, date(2026, 2, 15))

        tc = next((s for s in env.signals if s.record_type == "tracking_consistency"), None)
        assert tc is not None
        assert tc.priority == 1
        assert tc.value is not None

    @pytest.mark.asyncio
    async def test_priority_summary_present(self):
        session = AsyncMock()
        target_rows = [
            make_daily_row(
                date(2026, 2, 15),
                steps_total=10000,
                nutrition_summary={"calories_total": 1800},
            )
        ]

        async def _fetch(sess, start, end_exclusive, device_id=None):
            if start >= date(2026, 2, 15):
                return target_rows
            return []

        with patch("app.kernel.builders.connector.fetch_daily_rows", side_effect=_fetch):
            env = await build_daily_summary(session, date(2026, 2, 15))

        assert env.priority_summary is not None
        assert "P2" in env.priority_summary
        assert "P3" in env.priority_summary
        p3 = env.priority_summary["P3"]
        assert p3.status == "green"

    @pytest.mark.asyncio
    async def test_no_data_no_priority_summary(self):
        session = AsyncMock()
        with patch("app.kernel.builders.connector.fetch_daily_rows", return_value=[]):
            env = await build_daily_summary(session, date(2026, 2, 15))
        assert env.priority_summary is None

    @pytest.mark.asyncio
    async def test_signals_without_goals_have_none_fields(self):
        session = AsyncMock()
        target_rows = [
            make_daily_row(
                date(2026, 2, 15),
                steps_total=5000,
                heart_rate_summary={"avg_hr": 72},
            )
        ]

        async def _fetch(sess, start, end_exclusive, device_id=None):
            if start >= date(2026, 2, 15):
                return target_rows
            return []

        with patch("app.kernel.builders.connector.fetch_daily_rows", side_effect=_fetch):
            env = await build_daily_summary(session, date(2026, 2, 15))

        hr = next((s for s in env.signals if s.record_type == "avg_hr"), None)
        assert hr is not None
        assert hr.priority is None
        assert hr.status is None
        assert hr.trend is None


# ---------------------------------------------------------------------------
# Phase 1: Tracking consistency vector tests
# ---------------------------------------------------------------------------

class TestFindTrackingStartDate:
    def test_finds_earliest_manual_signal(self):
        rows = [
            make_daily_row(date(2026, 2, 10), steps_total=5000),  # Auto only
            make_daily_row(date(2026, 2, 11), body_metrics={"weight_kg": 130.0}),  # Manual
            make_daily_row(date(2026, 2, 12), nutrition_summary={"calories_total": 2000}),  # Manual
        ]
        result = find_tracking_start_date(rows)
        assert result == date(2026, 2, 11)

    def test_returns_none_if_no_manual_signals(self):
        rows = [
            make_daily_row(date(2026, 2, 10), steps_total=5000),
            make_daily_row(date(2026, 2, 11), steps_total=6000),
        ]
        result = find_tracking_start_date(rows)
        assert result is None

    def test_handles_empty_list(self):
        assert find_tracking_start_date([]) is None


class TestManualTrackingCoverageVector:
    def test_full_coverage_7d(self):
        tracking_start = date(2026, 2, 9)
        current_date = date(2026, 2, 16)
        rows = [
            make_daily_row(
                date(2026, 2, 10),
                nutrition_summary={"calories_total": 2000},
                body_metrics={"weight_kg": 130.0},
            )
            for i in range(7)  # 7 days of manual tracking
        ]
        # Adjust dates
        for i, row in enumerate(rows):
            row["date"] = current_date - timedelta(days=6 - i)

        result = manual_tracking_coverage_vector(rows, recent_days=7, tracking_start=tracking_start, current_date=current_date)
        assert result["manual_coverage_7d"] == 1.0
        assert result["streak_manual_days"] == 7

    def test_partial_coverage(self):
        tracking_start = date(2026, 2, 9)
        current_date = date(2026, 2, 16)
        rows = [
            make_daily_row(date(2026, 2, 10), nutrition_summary={"calories_total": 2000}),
            make_daily_row(date(2026, 2, 12), body_metrics={"weight_kg": 130.0}),
            make_daily_row(date(2026, 2, 14), nutrition_summary={"calories_total": 1800}),
        ]

        result = manual_tracking_coverage_vector(rows, recent_days=7, tracking_start=tracking_start, current_date=current_date)
        assert 0.0 < result["manual_coverage_7d"] < 1.0

    def test_days_since_last(self):
        tracking_start = date(2026, 2, 9)
        current_date = date(2026, 2, 16)
        rows = [
            make_daily_row(date(2026, 2, 10), nutrition_summary={"calories_total": 2000}),
        ]

        result = manual_tracking_coverage_vector(rows, recent_days=7, tracking_start=tracking_start, current_date=current_date)
        assert result["days_since_last_manual_entry"] == 6  # 6 days ago

    def test_empty_rows(self):
        tracking_start = date(2026, 2, 9)
        current_date = date(2026, 2, 16)
        result = manual_tracking_coverage_vector([], recent_days=7, tracking_start=tracking_start, current_date=current_date)
        assert result["manual_coverage_7d"] == 0.0
        assert result["streak_manual_days"] == 0
        assert result["days_since_last_manual_entry"] == 999.0


class TestTrackingStatusFromCoverage:
    def test_green_high_coverage(self):
        assert tracking_status_from_coverage(0.90) == "green"
        assert tracking_status_from_coverage(0.85) == "green"

    def test_yellow_moderate_coverage(self):
        assert tracking_status_from_coverage(0.75) == "yellow"
        assert tracking_status_from_coverage(0.70) == "yellow"

    def test_red_low_coverage(self):
        assert tracking_status_from_coverage(0.50) == "red"
        assert tracking_status_from_coverage(0.0) == "red"


class TestBuilderPhase1Integration:
    @pytest.mark.asyncio
    async def test_tracking_consistency_has_coverage_vector(self):
        session = AsyncMock()
        target_rows = [
            make_daily_row(
                date(2026, 2, 15),
                nutrition_summary={"calories_total": 2000},
                body_metrics={"weight_kg": 130.0},
            )
        ]

        async def _fetch(sess, start, end_exclusive, device_id=None):
            if start >= date(2026, 2, 15):
                return target_rows
            return []

        with patch("app.kernel.builders.connector.fetch_daily_rows", side_effect=_fetch):
            env = await build_daily_summary(session, date(2026, 2, 15))

        tc = next((s for s in env.signals if s.record_type == "tracking_consistency"), None)
        assert tc is not None
        assert tc.coverage_vector is not None
        assert "manual_coverage_7d" in tc.coverage_vector
        assert "manual_coverage_30d" in tc.coverage_vector
        assert "days_since_last_manual_entry" in tc.coverage_vector
        assert "streak_manual_days" in tc.coverage_vector

    @pytest.mark.asyncio
    async def test_tracking_status_from_coverage_vector(self):
        session = AsyncMock()
        # Create 7 days of full tracking
        target_rows = [
            make_daily_row(
                date(2026, 2, 9) + timedelta(days=i),
                nutrition_summary={"calories_total": 2000},
            )
            for i in range(7)
        ]

        async def _fetch(sess, start, end_exclusive, device_id=None):
            if start >= date(2026, 2, 9):
                return target_rows
            return []

        with patch("app.kernel.builders.connector.fetch_daily_rows", side_effect=_fetch):
            env = await build_daily_summary(session, date(2026, 2, 15))

        tc = next((s for s in env.signals if s.record_type == "tracking_consistency"), None)
        assert tc is not None
        assert tc.status in ("green", "yellow", "red")
        assert tc.coverage_vector["manual_coverage_7d"] >= 0.0
