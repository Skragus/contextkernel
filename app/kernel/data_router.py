"""Data access endpoints — latest intraday, history, trends."""

from __future__ import annotations

from datetime import date, datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_api_key
from app.config import settings
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
    now = datetime.now(timezone.utc)
    
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
    
    # Calculate freshness/completeness
    collected_at = data["collected_at"]
    hours_since_sync = (now - collected_at).total_seconds() / 3600
    
    # Day progress based on configured timezone
    tz = __import__('zoneinfo').ZoneInfo(settings.default_tz)
    local_now = now.astimezone(tz)
    day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_progress = (local_now - day_start).total_seconds() / 86400
    
    # Data freshness classification
    if hours_since_sync < 1:
        freshness = "current"
    elif hours_since_sync < 4:
        freshness = "recent"
    elif hours_since_sync < 12:
        freshness = "stale"
    else:
        freshness = "very_stale"
    
    # Completeness heuristic
    if day_progress < 0.25:  # Before 6am
        completeness = "early_day"
    elif day_progress < 0.5:  # Before noon
        completeness = "morning_partial"
    elif day_progress < 0.75:  # Before 6pm
        completeness = "afternoon_partial"
    elif hours_since_sync > 6:  # Evening, no recent sync
        completeness = "day_mostly_complete"
    else:
        completeness = "evening_ongoing"
    
    return {
        "meta": {
            "query_date": query_date.isoformat(),
            "queried_at": now.isoformat(),
            "timezone": settings.default_tz,
            "last_sync": collected_at.isoformat() if collected_at else None,
            "hours_since_sync": round(hours_since_sync, 2),
            "percent_day_elapsed": round(day_progress * 100, 1),
            "data_freshness": freshness,
            "completeness": completeness,
            "next_expected_sync": (collected_at + timedelta(hours=1)).isoformat() if collected_at else None,
        },
        "date": data["date"].isoformat() if data["date"] else None,
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
    now = datetime.now(timezone.utc)
    
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
        "meta": {
            "queried_at": now.isoformat(),
            "signal": signal,
            "days_requested": days,
            "days_returned": len(history),
        },
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
