"""Tests for card builders — uses mocked connector results."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.kernel.builders import (
    build_daily_summary,
    build_monthly_overview,
    build_weekly_overview,
)
from app.kernel.models import Granularity

from tests.conftest import make_daily_row


def _target_rows(d: date, steps_total: int = 2530, avg_hr: int = 76) -> list[dict]:
    return [
        make_daily_row(
            d,
            steps_total=steps_total,
            heart_rate_summary={"avg_hr": avg_hr, "max_hr": 109, "min_hr": 58, "resting_hr": 76},
        )
    ]


class TestBuildDailySummary:
    @pytest.mark.asyncio
    async def test_zero_data_returns_valid_envelope(self):
        session = AsyncMock()
        with patch("app.kernel.builders.connector.fetch_daily_rows", return_value=[]):
            env = await build_daily_summary(session, date(2026, 2, 15))

        assert env.card_type == "daily_summary"
        assert env.granularity == Granularity.daily
        assert len(env.signals) == 0 or all(s.value is None for s in env.signals) or env.signals == []
        assert any("No data" in w for w in env.warnings)
        assert env.schema_version == "v0"

    @pytest.mark.asyncio
    async def test_with_data(self):
        session = AsyncMock()
        target_rows = _target_rows(date(2026, 2, 15), steps_total=2530)
        baseline_rows = [
            make_daily_row(date(2026, 2, 15) - timedelta(days=i), steps_total=8000)
            for i in range(1, 8)
        ]

        async def _fetch(sess, start, end_exclusive, device_id=None, **kwargs):
            if start >= date(2026, 2, 15):
                return target_rows
            return baseline_rows

        with patch("app.kernel.builders.connector.fetch_daily_rows", side_effect=_fetch):
            env = await build_daily_summary(session, date(2026, 2, 15))

        assert env.card_type == "daily_summary"
        steps_sig = next((s for s in env.signals if s.record_type == "steps_total"), None)
        assert steps_sig is not None
        # Phase 3: steps value is 14d rolling avg, not raw sum
        assert steps_sig.value is not None
        assert steps_sig.baseline is not None
        assert env.evidence.total_rows >= 1

    @pytest.mark.asyncio
    async def test_missing_baseline(self):
        session = AsyncMock()
        target_rows = _target_rows(date(2026, 2, 15), avg_hr=72)

        async def _fetch(sess, start, end_exclusive, device_id=None, **kwargs):
            if start >= date(2026, 2, 15):
                return target_rows
            return []

        with patch("app.kernel.builders.connector.fetch_daily_rows", side_effect=_fetch):
            env = await build_daily_summary(session, date(2026, 2, 15))

        hr_sig = next((s for s in env.signals if s.record_type == "avg_hr"), None)
        assert hr_sig is not None
        assert hr_sig.value is not None
        assert hr_sig.baseline is None
        assert hr_sig.delta is None


class TestBuildWeeklyOverview:
    @pytest.mark.asyncio
    async def test_zero_data(self):
        session = AsyncMock()
        with patch("app.kernel.builders.connector.fetch_daily_rows", return_value=[]):
            env = await build_weekly_overview(session, date(2026, 2, 9))
        assert env.granularity == Granularity.weekly
        assert any("No data" in w for w in env.warnings)

    @pytest.mark.asyncio
    async def test_coverage_populated(self):
        session = AsyncMock()
        rows = _target_rows(date(2026, 2, 10), steps_total=5000)

        async def _fetch(sess, start, end_exclusive, device_id=None, **kwargs):
            if start >= date(2026, 2, 9):
                return rows
            return []

        with patch("app.kernel.builders.connector.fetch_daily_rows", side_effect=_fetch):
            env = await build_weekly_overview(session, date(2026, 2, 9))

        assert len(env.coverage.signals) >= 1


class TestBuildMonthlyOverview:
    @pytest.mark.asyncio
    async def test_zero_data(self):
        session = AsyncMock()
        with patch("app.kernel.builders.connector.fetch_daily_rows", return_value=[]):
            env = await build_monthly_overview(session, 2026, 2)
        assert env.granularity == Granularity.monthly
        assert any("No data" in w for w in env.warnings)

    @pytest.mark.asyncio
    async def test_basic(self):
        session = AsyncMock()
        rows = [
            make_daily_row(date(2026, 2, 10), steps_total=400),
            make_daily_row(date(2026, 2, 11), steps_total=300),
        ]

        async def _fetch(sess, start, end_exclusive, device_id=None, **kwargs):
            if start >= date(2026, 2, 1):
                return rows
            return []

        with patch("app.kernel.builders.connector.fetch_daily_rows", side_effect=_fetch):
            env = await build_monthly_overview(session, 2026, 2)

        steps_sig = next((s for s in env.signals if s.record_type == "steps_total"), None)
        assert steps_sig is not None
        # Phase 3: steps value is 14d rolling avg (2 days: 400+300)/2 = 350
        assert steps_sig.value == 350.0
