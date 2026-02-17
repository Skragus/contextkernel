"""Card builders — the kernel.

Queries health_connect_daily, extracts signals from typed + JSONB columns,
aggregates, computes baselines/deltas, returns CardEnvelope.
Graceful degradation: missing data never raises.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.kernel import connector, extractor, features
from app.kernel.models import (
    CardEnvelope,
    Coverage,
    Drilldown,
    Evidence,
    EvidenceSource,
    Granularity,
    Signal,
    SignalCoverage,
    TimeRange,
)
from app.kernel.signal_map import get_signal_config, list_signals


def _tz(tz_name: str) -> ZoneInfo:
    return ZoneInfo(tz_name)


def _to_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc)


def _date_range_utc(start: date, end_exclusive: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    s = datetime.combine(start, time.min, tzinfo=tz)
    e = datetime.combine(end_exclusive, time.min, tzinfo=tz)
    return _to_utc(s), _to_utc(e)


async def _build_card(
    session: AsyncSession,
    card_type: str,
    granularity: Granularity,
    target_start: date,
    target_end_exclusive: date,
    baseline_start: date,
    tz_name: str,
) -> CardEnvelope:
    tz = _tz(tz_name)
    range_start, range_end = _date_range_utc(target_start, target_end_exclusive, tz)

    warnings: list[str] = []
    if range_start > datetime.now(timezone.utc):
        warnings.append("Requested range is entirely in the future.")

    target_rows = await connector.fetch_daily_rows(session, target_start, target_end_exclusive)

    if not target_rows:
        warnings.append("No data found in the requested range.")
        return CardEnvelope(
            card_type=card_type,
            granularity=granularity,
            time_range=TimeRange(start=range_start, end=range_end, timezone=tz_name),
            summary="No data available for this period.",
            warnings=warnings,
            coverage=Coverage(missing_sources=[], partial_days=[]),
        )

    baseline_rows = await connector.fetch_daily_rows(session, baseline_start, target_start)

    target_series = extractor.extract_signal_series(target_rows)
    baseline_series = extractor.extract_signal_series(baseline_rows)

    signals: list[Signal] = []
    evidence_sources: list[EvidenceSource] = []
    signal_coverages: list[SignalCoverage] = []
    drilldowns: list[Drilldown] = []
    total_rows = len(target_rows)
    target_days = (target_end_exclusive - target_start).days or 1

    for signal_name in list_signals():
        cfg = get_signal_config(signal_name)
        if cfg is None:
            continue

        vals = target_series.get(signal_name, [])
        bl_vals = baseline_series.get(signal_name, [])

        current_val = features.aggregate(vals, cfg.agg)
        baseline_val = features.trailing_average(bl_vals) if bl_vals else None
        delta = features.compute_delta(current_val, baseline_val)

        signals.append(
            Signal(
                name=signal_name.replace("_", " ").title(),
                record_type=signal_name,
                value=current_val,
                unit=cfg.unit,
                aggregation=cfg.agg,
                baseline=baseline_val,
                delta=delta,
            )
        )

        days_with_data = len(vals)
        completeness = features.coverage_ratio(days_with_data, target_days)
        signal_coverages.append(SignalCoverage(signal_name=signal_name, completeness=completeness))

        earliest_date = min(row["date"] for row in target_rows) if target_rows else None
        latest_date = max(row["date"] for row in target_rows) if target_rows else None
        evidence_sources.append(
            EvidenceSource(
                record_type=signal_name,
                row_count=days_with_data,
                earliest=datetime.combine(earliest_date, time.min, tzinfo=timezone.utc) if earliest_date else None,
                latest=datetime.combine(latest_date, time.min, tzinfo=timezone.utc) if latest_date else None,
            )
        )

        drilldowns.append(
            Drilldown(
                label=f"Signal: {signal_name}",
                type="records",
                params={"signal": signal_name, "from": target_start.isoformat(), "to": target_end_exclusive.isoformat()},
            )
        )

    dates_present = [row["date"] for row in target_rows]
    partial_days = features.detect_partial_days(
        [datetime.combine(d, time.min, tzinfo=timezone.utc) for d in dates_present]
    )

    missing_sources = [s for s in list_signals() if not target_series.get(s)]
    if missing_sources:
        warnings.append(f"Missing in target range: {', '.join(missing_sources)}")

    n_signals = len([s for s in signals if s.value is not None])
    summary = f"{n_signals} signal(s) computed across {total_rows} records."

    return CardEnvelope(
        card_type=card_type,
        granularity=granularity,
        time_range=TimeRange(start=range_start, end=range_end, timezone=tz_name),
        summary=summary,
        signals=signals,
        evidence=Evidence(sources=evidence_sources, total_rows=total_rows),
        coverage=Coverage(
            signals=signal_coverages,
            missing_sources=missing_sources,
            partial_days=partial_days,
        ),
        warnings=warnings,
        drilldowns=drilldowns,
    )


async def build_daily_summary(
    session: AsyncSession,
    target_date: date,
    tz_name: str = "UTC",
) -> CardEnvelope:
    baseline_start = target_date - timedelta(days=features.baseline_window("daily"))
    return await _build_card(
        session,
        card_type="daily_summary",
        granularity=Granularity.daily,
        target_start=target_date,
        target_end_exclusive=target_date + timedelta(days=1),
        baseline_start=baseline_start,
        tz_name=tz_name,
    )


async def build_weekly_overview(
    session: AsyncSession,
    week_start: date,
    tz_name: str = "UTC",
) -> CardEnvelope:
    weeks = features.baseline_window("weekly")
    baseline_start = week_start - timedelta(weeks=weeks)
    return await _build_card(
        session,
        card_type="weekly_overview",
        granularity=Granularity.weekly,
        target_start=week_start,
        target_end_exclusive=week_start + timedelta(days=7),
        baseline_start=baseline_start,
        tz_name=tz_name,
    )


async def build_monthly_overview(
    session: AsyncSession,
    year: int,
    month: int,
    tz_name: str = "UTC",
) -> CardEnvelope:
    first_day = date(year, month, 1)
    _, last = calendar.monthrange(year, month)
    end_exclusive = first_day + timedelta(days=last)
    months = features.baseline_window("monthly")
    baseline_start = first_day - timedelta(days=months * 30)
    return await _build_card(
        session,
        card_type="monthly_overview",
        granularity=Granularity.monthly,
        target_start=first_day,
        target_end_exclusive=end_exclusive,
        baseline_start=baseline_start,
        tz_name=tz_name,
    )
