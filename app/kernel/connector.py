"""Database connector — async access to health_records."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_record_types(
    session: AsyncSession,
    start: datetime,
    end: datetime,
) -> list[str]:
    """Return distinct record_type values present in [start, end]."""
    result = await session.execute(
        text(
            "SELECT DISTINCT record_type FROM health_records "
            "WHERE start_date >= :start AND start_date < :end "
            "ORDER BY record_type"
        ),
        {"start": start, "end": end},
    )
    return [row[0] for row in result.fetchall()]


async def fetch_records(
    session: AsyncSession,
    start: datetime,
    end: datetime,
    record_type: str | None = None,
) -> Sequence[dict[str, Any]]:
    """Fetch rows from health_records as dicts.

    Returns an empty list when nothing is found — never raises.
    """
    query = (
        "SELECT id, record_type, start_date, end_date, data "
        "FROM health_records "
        "WHERE start_date >= :start AND start_date < :end"
    )
    params: dict[str, Any] = {"start": start, "end": end}

    if record_type is not None:
        query += " AND record_type = :rt"
        params["rt"] = record_type

    query += " ORDER BY start_date"

    result = await session.execute(text(query), params)
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]


async def check_availability(
    session: AsyncSession,
    record_types: list[str],
    start: datetime,
    end: datetime,
) -> dict[str, dict[str, Any]]:
    """Per-type counts + date bounds in [start, end].

    Returns an entry for every requested type (count=0 if absent).
    """
    if not record_types:
        return {}

    result = await session.execute(
        text(
            "SELECT record_type, COUNT(*) AS cnt, "
            "MIN(start_date) AS earliest, MAX(start_date) AS latest "
            "FROM health_records "
            "WHERE start_date >= :start AND start_date < :end "
            "  AND record_type = ANY(:types) "
            "GROUP BY record_type"
        ),
        {"start": start, "end": end, "types": record_types},
    )

    found: dict[str, dict[str, Any]] = {}
    for row in result.fetchall():
        found[row[0]] = {
            "count": row[1],
            "earliest": row[2],
            "latest": row[3],
        }

    # Ensure every requested type is represented
    for rt in record_types:
        if rt not in found:
            found[rt] = {"count": 0, "earliest": None, "latest": None}

    return found
