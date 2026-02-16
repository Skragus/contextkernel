"""Tests for card builders — uses mocked connector results."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.kernel.builders import (
    build_daily_summary,
    build_monthly_overview,
    build_weekly_overview,
)
from app.kernel.models import Granularity

from tests.conftest import make_row


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rows_for_day(d: date, record_type: str, values: list[float]) -> list[dict[str, Any]]:
    """Generate fake DB rows for a single day."""
    rows = []
    for i, v in enumerate(values):
        ts = datetime(d.year, d.month, d.day, 8 + i, 0, tzinfo=timezone.utc)
        rows.append(make_row(record_type, v, ts=ts, row_id=i))
    return rows


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBuildDailySummary:
    @pytest.mark.asyncio
    async def test_zero_data_returns_valid_envelope(self):
        """No data should produce a valid envelope with warnings."""
        session = AsyncMock()
        session.execute = AsyncMock()

        with patch("app.kernel.builders.connector.fetch_records", return_value=[]):
            env = await build_daily_summary(session, date(2026, 2, 15))

        assert env.card_type == "daily_summary"
        assert env.granularity == Granularity.daily
        assert env.signals == []
        assert any("No data" in w for w in env.warnings)
        assert env.schema_version == "v0"

    @pytest.mark.asyncio
    async def test_with_data(self):
        session = AsyncMock()
        target_rows = _rows_for_day(date(2026, 2, 15), "step_count", [3000, 4000, 5000])
        baseline_rows = []
        for d_offset in range(1, 8):
            d = date(2026, 2, 15) - timedelta(days=d_offset)
            baseline_rows.extend(_rows_for_day(d, "step_count", [8000]))

        async def _fetch(sess, start, end, record_type=None):
            # Target window vs baseline window
            if start >= datetime(2026, 2, 15, tzinfo=timezone.utc):
                return target_rows
            return baseline_rows

        with patch("app.kernel.builders.connector.fetch_records", side_effect=_fetch):
            env = await build_daily_summary(session, date(2026, 2, 15))

        assert env.card_type == "daily_summary"
        assert len(env.signals) == 1
        sig = env.signals[0]
        assert sig.record_type == "step_count"
        assert sig.value == 12000.0  # sum of 3000+4000+5000
        assert sig.baseline is not None
        assert env.evidence.total_rows == 3

    @pytest.mark.asyncio
    async def test_missing_baseline(self):
        session = AsyncMock()
        target_rows = _rows_for_day(date(2026, 2, 15), "heart_rate", [72, 75, 68])

        async def _fetch(sess, start, end, record_type=None):
            if start >= datetime(2026, 2, 15, tzinfo=timezone.utc):
                return target_rows
            return []

        with patch("app.kernel.builders.connector.fetch_records", side_effect=_fetch):
            env = await build_daily_summary(session, date(2026, 2, 15))

        sig = env.signals[0]
        assert sig.value is not None
        assert sig.baseline is None
        assert sig.delta is None


class TestBuildWeeklyOverview:
    @pytest.mark.asyncio
    async def test_zero_data(self):
        session = AsyncMock()
        with patch("app.kernel.builders.connector.fetch_records", return_value=[]):
            env = await build_weekly_overview(session, date(2026, 2, 9))
        assert env.granularity == Granularity.weekly
        assert env.signals == []

    @pytest.mark.asyncio
    async def test_coverage_populated(self):
        session = AsyncMock()
        rows = _rows_for_day(date(2026, 2, 10), "step_count", [5000])

        async def _fetch(sess, start, end, record_type=None):
            if start >= datetime(2026, 2, 9, tzinfo=timezone.utc):
                return rows
            return []

        with patch("app.kernel.builders.connector.fetch_records", side_effect=_fetch):
            env = await build_weekly_overview(session, date(2026, 2, 9))

        assert len(env.coverage.signals) == 1
        assert env.coverage.signals[0].completeness < 1.0  # only 1 day out of 7


class TestBuildMonthlyOverview:
    @pytest.mark.asyncio
    async def test_zero_data(self):
        session = AsyncMock()
        with patch("app.kernel.builders.connector.fetch_records", return_value=[]):
            env = await build_monthly_overview(session, 2026, 2)
        assert env.granularity == Granularity.monthly
        assert env.signals == []

    @pytest.mark.asyncio
    async def test_basic(self):
        session = AsyncMock()
        rows = _rows_for_day(date(2026, 2, 10), "active_energy_burned", [400, 300])

        async def _fetch(sess, start, end, record_type=None):
            if start >= datetime(2026, 2, 1, tzinfo=timezone.utc):
                return rows
            return []

        with patch("app.kernel.builders.connector.fetch_records", side_effect=_fetch):
            env = await build_monthly_overview(session, 2026, 2)

        assert len(env.signals) == 1
        assert env.signals[0].value == 700.0  # sum
