"""Pure stateless feature functions — math only, never raises."""

from __future__ import annotations

from datetime import date, datetime, timedelta


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


# ---------------------------------------------------------------------------
# Phase 1: Tracking consistency helpers
# ---------------------------------------------------------------------------

def find_tracking_start_date(rows: list[dict]) -> date | None:
    """Find the earliest date with manual tracking signals (weight OR calories).

    Returns None if no manual signals found.
    """
    if not rows:
        return None
    
    manual_dates: list[date] = []
    for row in rows:
        raw = row.get("raw_data") or {}
        row_date = row.get("date")
        if not isinstance(row_date, date):
            continue
        
        # Check for calories_total
        nutrition = raw.get("nutrition_summary")
        if isinstance(nutrition, dict) and nutrition.get("calories_total") is not None:
            manual_dates.append(row_date)
            continue
        
        # Check for weight_kg
        body = raw.get("body_metrics")
        if isinstance(body, dict) and body.get("weight_kg") is not None:
            manual_dates.append(row_date)
    
    return min(manual_dates) if manual_dates else None


def manual_tracking_coverage_vector(
    rows: list[dict],
    recent_days: int,
    tracking_start: date,
    current_date: date,
) -> dict[str, float]:
    """Compute manual tracking coverage vector.

    Returns:
        - manual_coverage_7d: ratio of days with weight OR calories in last N days
        - manual_coverage_30d: ratio in last 30 days (or since tracking_start, whichever shorter)
        - days_since_last_manual_entry: days since last weight OR calories entry
        - streak_manual_days: current consecutive days with weight OR calories
    """
    if not rows:
        return {
            "manual_coverage_7d": 0.0,
            "manual_coverage_30d": 0.0,
            "days_since_last_manual_entry": 999.0,
            "streak_manual_days": 0,
        }
    
    # Filter rows to those with manual signals
    manual_rows: list[dict] = []
    for row in rows:
        raw = row.get("raw_data") or {}
        row_date = row.get("date")
        if not isinstance(row_date, date):
            continue
        
        has_calories = False
        nutrition = raw.get("nutrition_summary")
        if isinstance(nutrition, dict) and nutrition.get("calories_total") is not None:
            has_calories = True
        
        has_weight = False
        body = raw.get("body_metrics")
        if isinstance(body, dict) and body.get("weight_kg") is not None:
            has_weight = True
        
        if has_calories or has_weight:
            manual_rows.append(row)
    
    if not manual_rows:
        return {
            "manual_coverage_7d": 0.0,
            "manual_coverage_30d": 0.0,
            "days_since_last_manual_entry": float("inf"),
            "streak_manual_days": 0,
        }
    
    # Sort by date
    manual_rows.sort(key=lambda r: r.get("date") or date.min)
    manual_dates = {r.get("date") for r in manual_rows if isinstance(r.get("date"), date)}
    
    # Recent coverage (last N days)
    recent_cutoff = current_date - timedelta(days=recent_days)
    recent_manual = sum(1 for d in manual_dates if d >= recent_cutoff)
    recent_coverage_7d = recent_manual / recent_days if recent_days > 0 else 0.0
    
    # 30-day coverage (or since tracking_start, whichever shorter)
    days_since_start = (current_date - tracking_start).days
    window_30d = min(30, days_since_start + 1)
    cutoff_30d = current_date - timedelta(days=window_30d - 1)
    manual_30d = sum(1 for d in manual_dates if d >= cutoff_30d)
    recent_coverage_30d = manual_30d / window_30d if window_30d > 0 else 0.0
    
    # Days since last manual entry
    if manual_dates:
        last_manual = max(manual_dates)
        days_since_last = (current_date - last_manual).days
    else:
        days_since_last = float("inf")
    
    # Streak (consecutive days from current_date backwards)
    streak = 0
    check_date = current_date
    while check_date >= tracking_start:
        if check_date in manual_dates:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break
    
    return {
        "manual_coverage_7d": min(max(recent_coverage_7d, 0.0), 1.0),
        "manual_coverage_30d": min(max(recent_coverage_30d, 0.0), 1.0),
        "days_since_last_manual_entry": days_since_last if days_since_last != float("inf") else 999.0,
        "streak_manual_days": streak,
    }


def tracking_status_from_coverage(coverage_7d: float) -> str:
    """Map 7-day coverage to status: Green ≥85%, Yellow ≥70%, Red <70%."""
    if coverage_7d >= 0.85:
        return "green"
    if coverage_7d >= 0.70:
        return "yellow"
    return "red"


# ---------------------------------------------------------------------------
# Phase 2: Weekly deficit helpers (BMR + steps-based activity)
# ---------------------------------------------------------------------------

def _bmr_mifflin_st_jeor(weight_kg: float, height_cm: float, age_years: int, sex: str) -> float:
    """Mifflin-St Jeor BMR formula. Returns kcal/day."""
    base = 10.0 * weight_kg + 6.25 * height_cm - 5.0 * age_years
    if sex and str(sex).lower().startswith("f"):
        return base - 161.0
    return base + 5.0  # male default


def _bmr_from_row(raw: dict, age_years: int | None, sex: str | None) -> float | None:
    """Get BMR for a row: prefer body_metrics.bmr_kcal, else Mifflin-St Jeor from weight/height."""
    body = raw.get("body_metrics") if isinstance(raw, dict) else None
    if not isinstance(body, dict):
        return None
    bmr = body.get("bmr_kcal")
    if bmr is not None:
        try:
            return float(bmr)
        except (TypeError, ValueError):
            pass
    w = body.get("weight_kg")
    h = body.get("height_cm")
    if w is None or h is None:
        return None
    try:
        weight = float(w)
        height = float(h)
    except (TypeError, ValueError):
        return None
    age = age_years if age_years is not None and age_years > 0 else 30
    return _bmr_mifflin_st_jeor(weight, height, age, sex or "male")


def _activity_kcal_from_steps(steps: float, steps_to_kcal: float, activity_modifier: float) -> float:
    """Earned activity calories = steps * steps_to_kcal * activity_modifier (conservative)."""
    return max(0.0, steps * steps_to_kcal * activity_modifier)


def compute_weekly_deficit_from_rows(
    rows: list[dict],
    steps_to_kcal: float,
    activity_modifier: float,
    age_years: int | None = None,
    sex: str | None = None,
) -> float:
    """Compute weekly deficit from date-aligned rows.

    Model: daily burn = BMR + (steps * steps_to_kcal * activity_modifier)
    Deficit = burn - eaten. Uses height, weight, steps from each row; BMR from
    body_metrics.bmr_kcal or Mifflin-St Jeor; activity from steps only.
    """
    total = 0.0
    for row in rows:
        raw = row.get("raw_data") or {}
        bmr = _bmr_from_row(raw, age_years, sex)
        if bmr is None or bmr <= 0:
            bmr = 1500.0  # fallback
        steps_val = 0.0
        if "steps_total" in raw and raw["steps_total"] is not None:
            try:
                steps_val = float(raw["steps_total"])
            except (TypeError, ValueError):
                pass
        activity = _activity_kcal_from_steps(steps_val, steps_to_kcal, activity_modifier)
        burned = bmr + activity
        eaten = 0.0
        nut = raw.get("nutrition_summary")
        if isinstance(nut, dict) and nut.get("calories_total") is not None:
            try:
                eaten = float(nut["calories_total"])
            except (TypeError, ValueError):
                pass
        total += burned - eaten
    return total


def compute_weekly_deficit(
    calories_burned: list[float],
    calories_eaten: list[float],
    modifier: float,
) -> float:
    """Legacy: Σ(burned * modifier - eaten). Prefer compute_weekly_deficit_from_rows."""
    if not calories_burned and not calories_eaten:
        return 0.0
    n = max(len(calories_burned), len(calories_eaten))
    total = 0.0
    for i in range(n):
        burned = calories_burned[i] if i < len(calories_burned) else 0.0
        eaten = calories_eaten[i] if i < len(calories_eaten) else 0.0
        total += (burned * modifier) - eaten
    return total


def weekly_deficit_progress(actual_deficit: float, target_deficit: float) -> float:
    """Progress toward weekly deficit goal. Capped at 100%."""
    if target_deficit <= 0.0:
        return 0.0
    return min(100.0, (actual_deficit / target_deficit) * 100.0)


def calorie_status_from_progress(progress_pct: float) -> str:
    """Map weekly deficit progress to status: Red <20%, Yellow 20-70%, Green ≥70%."""
    if progress_pct >= 70.0:
        return "green"
    if progress_pct >= 20.0:
        return "yellow"
    return "red"


# ---------------------------------------------------------------------------
# Phase 3: Steps gated ramp helpers
# ---------------------------------------------------------------------------

def compute_steps_baseline(steps_series: list[float], window: int = 14) -> float:
    """14-day rolling average of steps. Uses all available if < 14 days."""
    if not steps_series:
        return 0.0
    subset = steps_series[-window:] if len(steps_series) >= window else steps_series
    return sum(subset) / len(subset)


def compute_dynamic_steps_target(
    baseline_14d_avg: float,
    tracking_status: str,
    calories_status: str,
    ramp_rate_fast: float,
    ramp_rate_slow: float,
    long_term_target: float,
    floor: float,
) -> float:
    """Compute dynamic steps target based on P1/P2 statuses (gated ramp).

    - tracking green AND calories green → ramp_rate_fast
    - tracking yellow OR calories yellow → ramp_rate_slow
    - either red → 0% (stabilize)
    Target = baseline * (1 + ramp_rate), capped at long_term_target, floored at floor.
    """
    if tracking_status == "red" or calories_status == "red":
        ramp_rate = 0.0
    elif tracking_status == "green" and calories_status == "green":
        ramp_rate = ramp_rate_fast
    else:
        ramp_rate = ramp_rate_slow

    target = baseline_14d_avg * (1.0 + ramp_rate)
    target = min(target, long_term_target)
    return max(target, floor)


def steps_status_from_avg(avg_14d: float, dynamic_target: float, floor: float) -> str:
    """Map 14d avg vs dynamic target to status: below floor=red, above target=green, else yellow."""
    if avg_14d < floor:
        return "red"
    if avg_14d >= dynamic_target:
        return "green"
    return "yellow"
