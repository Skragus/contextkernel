"""Database connector — async access to health_connect_daily.

Table: health_connect_daily
  id (UUID), device_id (string), date (date), collected_at (timestamp),
  received_at (timestamp), source_type (string), schema_version (integer),
  raw_data (JSONB), source (JSONB)
"""

from __future__ import annotations

from datetime import date
from typing import Any, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def fetch_daily_rows(
    session: AsyncSession,
    start: date,
    end_exclusive: date,
    device_id: str | None = None,
) -> Sequence[dict[str, Any]]:
    """Fetch rows from health_connect_daily for date range [start, end_exclusive).

    Columns: device_id, date, raw_data. Optionally filter by device_id.
    raw_data contains the full payload (steps_total, body_metrics, etc.).

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
    return [dict(zip(columns, row)) for row in result.fetchall()]
