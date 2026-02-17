"""Card builders — the kernel.

Queries health_connect_daily (raw_data JSONB), extracts signals,
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
from app.kernel.goals_config import get_goal, list_goals
from app.kernel.models import PriorityStatus
from app.kernel.signal_map import get_signal_config, list_signals


def _tz(tz_name: str) -> ZoneInfo:
    return ZoneInfo(tz_name)


def _to_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc)


def _date_range_utc(start: date, end_exclusive: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    s = datetime.combine(start, time.min, tzinfo=tz)
    e = datetime.combine(end_exclusive, time.min, tzinfo=tz)
    return _to_utc(s), _to_utc(e)


def _build_priority_summary(signals: list[Signal]) -> dict[str, PriorityStatus] | None:
    """Build per-priority status summary from goal-bearing signals."""
    buckets: dict[int, list[Signal]] = {}
    for sig in signals:
        if sig.priority is not None:
            buckets.setdefault(sig.priority, []).append(sig)

    if not buckets:
        return None

    result: dict[str, PriorityStatus] = {}
    for pri in sorted(buckets):
        sigs = buckets[pri]
        progresses = [s.target_progress_pct for s in sigs if s.target_progress_pct is not None]
        avg_progress = sum(progresses) / len(progresses) if progresses else 0.0

        statuses = [s.status for s in sigs if s.status]
        if "red" in statuses:
            overall_status = "red"
        elif "yellow" in statuses:
            overall_status = "yellow"
        else:
            overall_status = "green"

        trends = [s.trend for s in sigs if s.trend]
        if "up" in trends and "down" not in trends:
            overall_trend = "up"
        elif "down" in trends and "up" not in trends:
            overall_trend = "down"
        else:
            overall_trend = "flat"

        labels = [s.name for s in sigs]
        msg = f"{', '.join(labels)}: {overall_status}"

        result[f"P{pri}"] = PriorityStatus(
            status=overall_status,
            progress=round(avg_progress, 1),
            trend=overall_trend,
            message=msg,
        )

    return result


async def _build_card(
    session: AsyncSession,
    card_type: str,
    granularity: Granularity,
    target_start: date,
    target_end_exclusive: date,
    baseline_start: date,
    tz_name: str,
    device_id: str | None = None,
) -> CardEnvelope:
    tz = _tz(tz_name)
    range_start, range_end = _date_range_utc(target_start, target_end_exclusive, tz)

    warnings: list[str] = []
    if range_start > datetime.now(timezone.utc):
        warnings.append("Requested range is entirely in the future.")

    target_rows = await connector.fetch_daily_rows(session, target_start, target_end_exclusive, device_id)

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

    baseline_rows = await connector.fetch_daily_rows(session, baseline_start, target_start, device_id)

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

        goal = get_goal(signal_name)
        progress_pct = None
        status = None
        priority = None
        trend = None
        target = None
        if goal:
            target = goal.target_value
            progress_pct = features.goal_progress_pct(current_val, goal.target_value, goal.target_type)
            status = features.goal_status(progress_pct)
            priority = goal.priority
            trend = features.compute_trend(vals, bl_vals)

        signals.append(
            Signal(
                name=signal_name.replace("_", " ").title(),
                record_type=signal_name,
                value=current_val,
                unit=cfg.unit,
                aggregation=cfg.agg,
                baseline=baseline_val,
                delta=delta,
                target=target,
                target_progress_pct=round(progress_pct, 1) if progress_pct is not None else None,
                priority=priority,
                status=status,
                trend=trend,
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

    # Virtual signal: tracking consistency (T1)
    tc_goal = get_goal("tracking_consistency")
    if tc_goal:
        tc_value = features.tracking_consistency(target_rows, target_days)
        tc_bl_value = features.tracking_consistency(baseline_rows, (target_start - baseline_start).days or 1) if baseline_rows else 0.0
        tc_pct = features.goal_progress_pct(tc_value, tc_goal.target_value, tc_goal.target_type)
        tc_trend = features.compute_trend([tc_value], [tc_bl_value]) if tc_bl_value > 0 else "flat"
        signals.append(
            Signal(
                name="Tracking Consistency",
                record_type="tracking_consistency",
                value=round(tc_value, 2),
                unit="ratio",
                aggregation="avg",
                target=tc_goal.target_value,
                target_progress_pct=round(tc_pct, 1) if tc_pct is not None else None,
                priority=tc_goal.priority,
                status=features.goal_status(tc_pct),
                trend=tc_trend,
            )
        )

    dates_present = [row["date"] for row in target_rows]
    partial_days = features.detect_partial_days(
        [datetime.combine(d, time.min, tzinfo=timezone.utc) for d in dates_present]
    )

    missing_sources = [s for s in list_signals() if not target_series.get(s)]
    if missing_sources:
        warnings.append(f"Missing in target range: {', '.join(missing_sources)}")

    # Build priority_summary from goal-bearing signals
    priority_summary = _build_priority_summary(signals)

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
        priority_summary=priority_summary,
    )


async def build_daily_summary(
    session: AsyncSession,
    target_date: date,
    tz_name: str = "UTC",
    device_id: str | None = None,
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
        device_id=device_id,
    )


async def build_weekly_overview(
    session: AsyncSession,
    week_start: date,
    tz_name: str = "UTC",
    device_id: str | None = None,
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
        device_id=device_id,
    )


async def build_monthly_overview(
    session: AsyncSession,
    year: int,
    month: int,
    tz_name: str = "UTC",
    device_id: str | None = None,
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
        device_id=device_id,
    )
