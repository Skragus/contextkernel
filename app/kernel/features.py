"""Pure stateless feature functions — math only, never raises."""

from __future__ import annotations

from datetime import datetime


def trailing_average(values: list[float], window: int | None = None) -> float | None:
    """Average of `values` (or last `window` items). Returns None if empty."""
    if not values:
        return None
    subset = values[-window:] if window else values
    if not subset:
        return None
    return sum(subset) / len(subset)


def aggregate(values: list[float], method: str) -> float | None:
    """Aggregate a list of floats by method. Returns None if empty."""
    if not values:
        return None
    if method == "sum":
        return sum(values)
    if method == "avg":
        return sum(values) / len(values)
    if method == "max":
        return max(values)
    if method == "min":
        return min(values)
    if method == "last":
        return values[-1]
    # Unknown method falls back to avg
    return sum(values) / len(values)


def baseline_window(granularity: str) -> int:
    """Number of prior periods used for baseline computation."""
    return {"daily": 7, "weekly": 4, "monthly": 3}.get(granularity, 7)


def compute_delta(current: float | None, baseline: float | None) -> float | None:
    """Absolute delta (current - baseline). None if either is missing."""
    if current is None or baseline is None:
        return None
    return current - baseline


def compute_delta_pct(current: float | None, baseline: float | None) -> float | None:
    """Percentage delta. None if either is missing or baseline is zero."""
    if current is None or baseline is None or baseline == 0.0:
        return None
    return ((current - baseline) / abs(baseline)) * 100.0


def coverage_ratio(actual: int, expected: int) -> float:
    """Fraction of expected data points present. Clamped to [0, 1]."""
    if expected <= 0:
        return 0.0
    return min(max(actual / expected, 0.0), 1.0)


def detect_partial_days(
    timestamps: list[datetime],
) -> list[str]:
    """Return ISO-date strings for days with below-median record counts.

    An empty input returns an empty list.
    """
    if not timestamps:
        return []

    day_counts: dict[str, int] = {}
    for ts in timestamps:
        day_key = ts.strftime("%Y-%m-%d")
        day_counts[day_key] = day_counts.get(day_key, 0) + 1

    if not day_counts:
        return []

    counts = sorted(day_counts.values())
    mid = len(counts) // 2
    if len(counts) % 2 == 0:
        median = (counts[mid - 1] + counts[mid]) / 2
    else:
        median = counts[mid]

    # Threshold: strictly below median (only meaningful when median > 1)
    if median <= 1:
        return []

    return sorted(day for day, c in day_counts.items() if c < median)
