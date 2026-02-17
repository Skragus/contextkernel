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


# ---------------------------------------------------------------------------
# Goal computation helpers
# ---------------------------------------------------------------------------

def goal_progress_pct(
    value: float | None,
    target_value: float,
    target_type: str,
) -> float | None:
    """Compute progress percentage (0–100) toward a goal.

    - minimum: progress = value / target * 100, capped at 100
    - maximum: progress = target / value * 100 (lower is better), capped at 100
    - exact: progress = 100 - abs(value - target) / target * 100, capped 0–100
    Returns None if value is None.
    """
    if value is None or target_value == 0.0:
        return None
    if target_type == "minimum":
        return min(100.0, (value / target_value) * 100.0)
    if target_type == "maximum":
        if value <= target_value:
            return 100.0
        return min(100.0, (target_value / value) * 100.0)
    if target_type == "exact":
        deviation = abs(value - target_value) / abs(target_value)
        return max(0.0, min(100.0, (1.0 - deviation) * 100.0))
    return None


def goal_status(progress_pct: float | None) -> str:
    """Map progress percentage to a status label."""
    if progress_pct is None:
        return "red"
    if progress_pct >= 100.0:
        return "green"
    if progress_pct >= 50.0:
        return "yellow"
    return "red"


def compute_trend(
    recent_values: list[float],
    prior_values: list[float],
    threshold: float = 0.05,
) -> str:
    """Compare recent vs prior window averages.

    Returns "up", "down", or "flat".
    Empty inputs yield "flat".
    """
    if not recent_values or not prior_values:
        return "flat"
    recent_avg = sum(recent_values) / len(recent_values)
    prior_avg = sum(prior_values) / len(prior_values)
    if prior_avg == 0.0:
        return "up" if recent_avg > 0 else "flat"
    ratio = recent_avg / prior_avg
    if ratio >= 1.0 + threshold:
        return "up"
    if ratio <= 1.0 - threshold:
        return "down"
    return "flat"


def tracking_consistency(
    rows: list[dict],
    expected_days: int,
    tracked_fields: tuple[str, ...] = ("calories_total", "weight_kg"),
) -> float:
    """Compute tracking consistency ratio (0–1).

    A day counts as "tracked" if raw_data contains at least one of the
    tracked_fields with a non-None value. Steps are auto-collected so
    excluded from tracking.
    """
    if expected_days <= 0:
        return 0.0
    tracked = 0
    for row in rows:
        raw = row.get("raw_data") or {}
        for field in tracked_fields:
            # Top-level fields
            if field in raw and raw[field] is not None:
                tracked += 1
                break
            # Check nested: nutrition_summary.calories_total, body_metrics.weight_kg
            for section in ("nutrition_summary", "body_metrics"):
                nested = raw.get(section)
                if isinstance(nested, dict) and field in nested and nested[field] is not None:
                    tracked += 1
                    break
            else:
                continue
            break
    return min(tracked / expected_days, 1.0)
