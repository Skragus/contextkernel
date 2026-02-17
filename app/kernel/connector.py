"""Database connector — async access to health_connect_daily."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def fetch_daily_rows(
    session: AsyncSession,
    start: date,
    end_exclusive: date,
) -> Sequence[dict[str, Any]]:
    """Fetch rows from health_connect_daily for date range [start, end_exclusive).

    Returns an empty list when nothing is found — never raises.
    """
    query = (
        "SELECT id, device_id, date, steps_total, "
        "body_metrics, heart_rate_summary, sleep_sessions, "
        "exercise_sessions, nutrition_summary "
        "FROM health_connect_daily "
        "WHERE date >= :start AND date < :end "
        "ORDER BY date"
    )
    result = await session.execute(
        text(query),
        {"start": start, "end": end_exclusive},
    )
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]
