"""Card builders — the kernel.

Each builder queries the connector, extracts values, computes aggregates /
baselines / deltas / coverage, and returns a fully-formed CardEnvelope.
Graceful degradation: missing data never causes an exception.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
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
from app.kernel.record_type_map import get_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tz(tz_name: str) -> ZoneInfo:
    return ZoneInfo(tz_name)


def _to_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc)


def _day_range(d: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Return (start_utc, end_utc) spanning a single calendar day in `tz`."""
    start = datetime.combine(d, time.min, tzinfo=tz)
    end = datetime.combine(d + timedelta(days=1), time.min, tzinfo=tz)
    return _to_utc(start), _to_utc(end)


def _date_range_utc(
    start: date, end_exclusive: date, tz: ZoneInfo
) -> tuple[datetime, datetime]:
    s = datetime.combine(start, time.min, tzinfo=tz)
    e = datetime.combine(end_exclusive, time.min, tzinfo=tz)
    return _to_utc(s), _to_utc(e)


# ---------------------------------------------------------------------------
# Shared builder core
# ---------------------------------------------------------------------------

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
    now = datetime.now(timezone.utc)

    # UTC boundaries
    range_start, range_end = _date_range_utc(target_start, target_end_exclusive, tz)
    bl_start_utc, _ = _date_range_utc(baseline_start, target_start, tz)

    # Warn for future ranges
    warnings: list[str] = []
    if range_start > now:
        warnings.append("Requested range is entirely in the future.")

    # Fetch target records
    target_rows = await connector.fetch_records(session, range_start, range_end)

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

    # Group by record_type
    by_type: dict[str, list[dict]] = defaultdict(list)
    for row in target_rows:
        by_type[row["record_type"]].append(row)

    # Fetch baseline records
    baseline_rows = await connector.fetch_records(session, bl_start_utc, range_start)
    bl_by_type: dict[str, list[dict]] = defaultdict(list)
    for row in baseline_rows:
        bl_by_type[row["record_type"]].append(row)

    # Discover all known types present
    all_types = sorted(by_type.keys())

    signals: list[Signal] = []
    evidence_sources: list[EvidenceSource] = []
    signal_coverages: list[SignalCoverage] = []
    drilldowns: list[Drilldown] = []
    total_rows = 0

    target_days = (target_end_exclusive - target_start).days or 1

    for rt in all_types:
        cfg = get_config(rt)
        rows = by_type[rt]
        pairs = extractor.extract_batch(rows)
        values = [v for _, v in pairs]
        timestamps = [ts for ts, _ in pairs]

        # Aggregate
        current_val = features.aggregate(values, cfg.agg)

        # Baseline
        bl_rows = bl_by_type.get(rt, [])
        bl_pairs = extractor.extract_batch(bl_rows)
        bl_values = [v for _, v in bl_pairs]
        baseline_val = features.trailing_average(bl_values) if bl_values else None

        if baseline_val is None and bl_values:
            warnings.append(f"Baseline insufficient for {rt}.")

        # Delta
        delta = features.compute_delta(current_val, baseline_val)

        signals.append(
            Signal(
                name=rt.replace("_", " ").title(),
                record_type=rt,
                value=current_val,
                unit=cfg.unit,
                aggregation=cfg.agg,
                baseline=baseline_val,
                delta=delta,
            )
        )

        # Evidence
        earliest = min(timestamps) if timestamps else None
        latest = max(timestamps) if timestamps else None
        evidence_sources.append(
            EvidenceSource(
                record_type=rt,
                row_count=len(rows),
                earliest=earliest,
                latest=latest,
            )
        )
        total_rows += len(rows)

        # Coverage per signal
        days_with_data = len({ts.strftime("%Y-%m-%d") for ts in timestamps})
        completeness = features.coverage_ratio(days_with_data, target_days)
        signal_coverages.append(
            SignalCoverage(signal_name=rt, completeness=completeness)
        )

        # Drilldowns
        drilldowns.append(
            Drilldown(
                label=f"Records: {rt}",
                type="records",
                params={
                    "record_type": rt,
                    "from": target_start.isoformat(),
                    "to": target_end_exclusive.isoformat(),
                },
            )
        )

    # Detect partial days across all timestamps
    all_timestamps = []
    for rt in all_types:
        pairs = extractor.extract_batch(by_type[rt])
        all_timestamps.extend(ts for ts, _ in pairs)
    partial_days = features.detect_partial_days(all_timestamps)

    # Missing sources: types in baseline but not target
    baseline_only = sorted(set(bl_by_type.keys()) - set(by_type.keys()))
    missing_sources = baseline_only
    if missing_sources:
        warnings.append(
            f"Missing in target range: {', '.join(missing_sources)}"
        )

    # Summary
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


# ---------------------------------------------------------------------------
# Public builders
# ---------------------------------------------------------------------------

async def build_daily_summary(
    session: AsyncSession,
    target_date: date,
    tz_name: str = "UTC",
) -> CardEnvelope:
    """Single-day card with 7-day trailing baseline."""
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
    """7-day card with 4-week trailing baseline."""
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
    """Full-month card with 3-month trailing baseline."""
    first_day = date(year, month, 1)
    _, last = calendar.monthrange(year, month)
    end_exclusive = first_day + timedelta(days=last)
    months = features.baseline_window("monthly")
    # Approximate baseline: months * 30 days
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
