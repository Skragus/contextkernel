"""Data access endpoints — latest intraday, history, trends."""

from __future__ import annotations

from datetime import date, datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_api_key
from app.db import get_session

router = APIRouter(prefix="/kernel", tags=["data"])


@router.get("/data/latest")
async def get_latest_data(
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key),
    target_date: date | None = Query(default=None, description="Date (default: today)"),
) -> dict:
    """Return most recent intraday sync for given date.
    
    Watchdog polls this to get real-time health data without 
    hitting sh-apk-api query endpoints.
    """
    query_date = target_date or datetime.now(timezone.utc).date()
    
    sql = (
        "SELECT device_id, date, collected_at, received_at, raw_data "
        "FROM health_connect_intraday_logs "
        "WHERE date = :target_date "
        "ORDER BY collected_at DESC LIMIT 1"
    )
    
    result = await session.execute(text(sql), {"target_date": query_date})
    row = result.fetchone()
    
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No intraday data for {query_date}"
        )
    
    columns = result.keys()
    data = dict(zip(columns, row))
    
    return {
        "date": data["date"].isoformat() if data["date"] else None,
        "collected_at": data["collected_at"].isoformat() if data["collected_at"] else None,
        "received_at": data["received_at"].isoformat() if data["received_at"] else None,
        "device_id": data["device_id"],
        "data": data["raw_data"],
    }


@router.get("/data/history")
async def get_signal_history(
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key),
    signal: str = Query(..., description="Signal path: steps_total, nutrition_summary.calories_total, etc."),
    days: int = Query(default=7, ge=1, le=30),
) -> dict:
    """Return historical values for a specific signal from intraday logs."""
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
    
    sql = (
        "SELECT date, collected_at, raw_data "
        "FROM health_connect_intraday_logs "
        "WHERE date >= :cutoff "
        "ORDER BY collected_at DESC"
    )
    
    result = await session.execute(text(sql), {"cutoff": cutoff})
    rows = result.fetchall()
    columns = result.keys()
    
    history = []
    seen_dates = set()
    
    for row in rows:
        row_dict = dict(zip(columns, row))
        row_date = row_dict["date"]
        
        # Only take latest entry per date
        if row_date in seen_dates:
            continue
        seen_dates.add(row_date)
        
        value = _extract_signal(row_dict["raw_data"], signal)
        if value is not None:
            history.append({
                "date": row_date.isoformat() if row_date else None,
                "collected_at": row_dict["collected_at"].isoformat() if row_dict["collected_at"] else None,
                "value": value,
            })
    
    return {
        "signal": signal,
        "days": days,
        "count": len(history),
        "history": history,
    }


def _extract_signal(raw_data: dict, signal_path: str) -> float | None:
    """Extract value from nested raw_data using dot notation."""
    if not raw_data:
        return None
    
    keys = signal_path.split(".")
    value = raw_data
    
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
