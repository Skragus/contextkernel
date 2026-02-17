"""Database connector — async access to health_connect_daily and health_connect_intraday_logs.

Tables share schema: id, device_id, date, collected_at, received_at, source_type,
schema_version, source, raw_data (JSONB). Intraday has cumulative data; for today
we fetch the latest row when daily may not be finalized yet.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def fetch_intraday_latest_for_date(
    session: AsyncSession,
    target_date: date,
    device_id: str | None = None,
) -> dict[str, Any] | None:
    """Fetch latest cumulative row from health_connect_intraday_logs for a date.

    Uses ORDER BY collected_at DESC LIMIT 1. Same row shape as daily (device_id, date, raw_data).
    Returns None when nothing found — never raises.
    """
    query = (
        "SELECT device_id, date, raw_data "
        "FROM health_connect_intraday_logs "
        "WHERE date = :target_date"
    )
    params: dict[str, Any] = {"target_date": target_date}
    if device_id is not None:
        query += " AND device_id = :device_id"
        params["device_id"] = device_id
    query += " ORDER BY collected_at DESC LIMIT 1"

    result = await session.execute(text(query), params)
    row = result.fetchone()
    if row is None:
        return None
    columns = result.keys()
    return dict(zip(columns, row))


async def fetch_daily_rows(
    session: AsyncSession,
    start: date,
    end_exclusive: date,
    device_id: str | None = None,
    use_intraday_for_today: date | None = None,
) -> Sequence[dict[str, Any]]:
    """Fetch rows from health_connect_daily for date range [start, end_exclusive).

    Columns: device_id, date, raw_data. Optionally filter by device_id.

    When use_intraday_for_today is set and within [start, end_exclusive), fetches
    the latest row from health_connect_intraday_logs for that date and uses it
    (replaces daily row if present, else adds it). Enables fresh data for today.

    Returns an empty list when nothing is found — never raises.
    """
    query = (
        "SELECT device_id, date, raw_data "
        "FROM health_connect_daily "
        "WHERE date >= :start AND date < :end "
        "AND source_type = 'daily'"
    )
    params: dict[str, Any] = {"start": start, "end": end_exclusive}
    if device_id is not None:
        query += " AND device_id = :device_id"
        params["device_id"] = device_id
    query += " ORDER BY date"

    result = await session.execute(text(query), params)
    columns = result.keys()
    rows = [dict(zip(columns, r)) for r in result.fetchall()]

    if use_intraday_for_today is not None and start <= use_intraday_for_today < end_exclusive:
        intra = await fetch_intraday_latest_for_date(session, use_intraday_for_today, device_id)
        if intra is not None:
            rows = [r for r in rows if r.get("date") != use_intraday_for_today]
            rows.append(intra)
            rows.sort(key=lambda r: r.get("date") or date.min)

    return rows
