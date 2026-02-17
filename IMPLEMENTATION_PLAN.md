# Goals System Upgrade — Implementation Plan

## Overview

Upgrade the goals system from simple threshold-based to operational/trajectory-aware with three phases:
- **Phase 1**: Tracking consistency (P1) — vector output, maturity-aware
- **Phase 2**: Calories (P2) — weekly deficit trend evaluation
- **Phase 3**: Steps (P3) — gated ramp with dynamic targets

---

## Phase 1: Tracking Consistency (P1)

### Goal
Replace scalar tracking consistency with a vector that includes recent reliability + maturity-aware coverage.

### Decisions
- **Recent reliability window**: 7 days (configurable via `GOALS_TRACKING_RECENT_DAYS`)
- **Manual signals**: Weight + calories only (protein later)
- **Coverage thresholds**: Green ≥85%, Yellow 70-84%, Red <70%
- **Tracking start date**: Feb 9, 2026 (configurable via `GOALS_TRACKING_START_DATE`)
- **30-day coverage**: Use `min(30 days, days_since_tracking_start)`

### Implementation Tasks

#### 1.1 Config Updates (`app/config.py`)
```python
# Add to Settings class:
goals_tracking_recent_days: int = 7
goals_tracking_start_date: str | None = None  # ISO date string, e.g. "2026-02-09"
```

#### 1.2 Goals Config (`app/kernel/goals_config.py`)
- Update `tracking_consistency` goal definition to mark it as "vector output" type
- Add helper: `get_tracking_start_date(session)` → queries DB or uses config

#### 1.3 Features (`app/kernel/features.py`)
Add functions:
- `compute_tracking_start_date(rows: list[dict]) -> date | None`
  - Query DB: `SELECT MIN(date) FROM health_connect_daily WHERE (calories_total IS NOT NULL OR weight_kg IS NOT NULL) AND source_type = 'daily'`
  - Fallback to config `GOALS_TRACKING_START_DATE` if provided
  - Return `None` if neither available (shouldn't happen)

- `manual_tracking_coverage_vector(rows: list[dict], recent_days: int, tracking_start: date) -> dict[str, float]`
  - Returns:
    - `manual_coverage_7d`: ratio of days with weight OR calories in last 7 days
    - `manual_coverage_30d`: ratio of days with weight OR calories in last 30 days (or since tracking_start, whichever shorter)
    - `days_since_last_manual_entry`: days since last weight OR calories entry
    - `streak_manual_days`: current consecutive days with weight OR calories

- `tracking_status_from_coverage(coverage_7d: float) -> str`
  - Green if ≥0.85, Yellow if ≥0.70, Red otherwise

#### 1.4 Models (`app/kernel/models.py`)
Extend `Signal`:
```python
class Signal(BaseModel):
    # ... existing fields ...
    coverage_vector: dict[str, float] | None = None  # For tracking consistency
```

#### 1.5 Builders (`app/kernel/builders.py`)
In `_build_card`:
- After building all regular signals, compute tracking consistency vector
- Create `tracking_consistency` signal with `coverage_vector` populated
- Use `tracking_start_date` for denominator calculations
- Attach priority=1, status from `tracking_status_from_coverage`

#### 1.6 Tests (`tests/test_goals.py`)
- Test `compute_tracking_start_date` (DB query + config fallback)
- Test `manual_tracking_coverage_vector` (7d, 30d, days_since_last, streak)
- Test `tracking_status_from_coverage` (thresholds)
- Test builder integration (tracking_consistency signal appears with vector)

---

## Phase 2: Calories (P2) — Weekly Deficit Trend

### Goal
Replace daily calorie threshold with weekly deficit evaluation using TDEE estimation.

### Decisions
- **Weekly deficit goal**: 500 kcal/day = 3500 kcal/week (configurable via `GOALS_CALORIE_DEFICIT_TARGET`)
- **TDEE calculation**: Use `total_calories_burned * modifier` (not BMR formula for now)
- **Calories burned modifier**: 0.5 (configurable via `GOALS_CALORIES_BURNED_MODIFIER`)
- **Weekly deficit formula**: `Σ(total_calories_burned * modifier - calories_total)` over 7 days
- **Progress cap**: 100% max
- **Status thresholds**: Red <20%, Yellow 20-70%, Green ≥70%

### Implementation Tasks

#### 2.1 Config Updates (`app/config.py`)
```python
# Add to Settings class:
goals_calorie_deficit_target: float = 500.0  # kcal/day
goals_calories_burned_modifier: float = 0.5  # Multiplier for total_calories_burned
```

#### 2.2 Signal Map (`app/kernel/signal_map.py`)
Add `total_calories_burned` signal:
```python
"total_calories_burned": SignalConfig(
    column="raw_data",
    path="total_calories_burned",
    agg="sum",
    unit="kcal"
)
```

#### 2.3 Features (`app/kernel/features.py`)
Add functions:
- `compute_weekly_deficit(calories_burned: list[float], calories_eaten: list[float], modifier: float) -> float`
  - Takes 7-day series
  - Returns: `sum((burned * modifier - eaten) for each day)`

- `weekly_deficit_progress(actual_deficit: float, target_deficit: float) -> float`
  - Returns: `min(100.0, (actual_deficit / target_deficit) * 100.0)`

- `calorie_status_from_progress(progress_pct: float) -> str`
  - Red if <20%, Yellow if <70%, Green otherwise

#### 2.4 Goals Config (`app/kernel/goals_config.py`)
Update `calories_total` goal:
- Mark as "weekly_deficit" evaluation type
- Store `deficit_target` (from config)

#### 2.5 Builders (`app/kernel/builders.py`)
In `_build_card`:
- For `calories_total` signal:
  - Extract `total_calories_burned` series (7-day window)
  - Extract `calories_total` series (7-day window)
  - Compute `weekly_deficit_actual = compute_weekly_deficit(burned, eaten, modifier)`
  - Compute `weekly_deficit_target = 7 * deficit_target`
  - Compute `progress_pct = weekly_deficit_progress(actual, target)`
  - Set `status = calorie_status_from_progress(progress_pct)`
  - Set `target_progress_pct = progress_pct`
  - Set `target = weekly_deficit_target` (for reference)

#### 2.6 Tests (`tests/test_goals.py`)
- Test `compute_weekly_deficit` (7-day series, modifier application)
- Test `weekly_deficit_progress` (progress calculation, 100% cap)
- Test `calorie_status_from_progress` (thresholds: <20%, 20-70%, ≥70%)
- Test builder integration (calories signal has weekly_deficit fields)

---

## Phase 3: Steps (P3) — Gated Ramp

### Goal
Replace fixed 8000-step threshold with dynamic target based on 14-day rolling average + gated ramp.

### Decisions
- **Evaluation window**: 14-day rolling average
- **Floor**: Configurable (default TBD, suggest 4000)
- **Ramp rates**:
  - Fast (tracking green AND calories green): 7.5% per week
  - Slow (tracking yellow OR calories yellow): 2.5% per week
  - None (either red): 0% (stabilize)
- **Baseline start**: First day with steps data (not tracking start)
- **Long-term target**: 8000 steps/day (configurable)
- **Status logic**: Compare 14d avg to dynamic target, apply floor check

### Implementation Tasks

#### 3.1 Config Updates (`app/config.py`)
```python
# Add to Settings class:
goals_steps_floor: float = 4000.0  # Minimum acceptable 14d avg
goals_steps_long_term_target: float = 8000.0  # Ultimate goal
goals_steps_ramp_rate_fast: float = 0.075  # 7.5% per week
goals_steps_ramp_rate_slow: float = 0.025  # 2.5% per week
```

#### 3.2 Features (`app/kernel/features.py`)
Add functions:
- `compute_steps_baseline(steps_series: list[float], baseline_start_date: date) -> float`
  - Returns 14-day average from `baseline_start_date` (or first available if <14 days)

- `compute_dynamic_steps_target(
    current_14d_avg: float,
    baseline_14d_avg: float,
    tracking_status: str,
    calories_status: str,
    ramp_rate_fast: float,
    ramp_rate_slow: float,
    long_term_target: float
) -> float`
  - Determine ramp rate from statuses
  - Compute: `target = baseline * (1 + ramp_rate)`
  - Cap at `long_term_target`
  - Return `max(target, floor)` (floor check)

- `steps_status_from_avg(avg_14d: float, dynamic_target: float, floor: float) -> str`
  - If `avg_14d < floor`: Red
  - If `avg_14d >= dynamic_target`: Green
  - Else: Yellow (between floor and target)

#### 3.3 Goals Config (`app/kernel/goals_config.py`)
Update `steps_total` goal:
- Mark as "gated_ramp" evaluation type
- Store `floor`, `long_term_target`, `ramp_rates` (from config)

#### 3.4 Builders (`app/kernel/builders.py`)
In `_build_card`:
- **Dependency**: Compute P1 (tracking) and P2 (calories) first
- For `steps_total` signal:
  - Extract steps series (14-day window for current, longer for baseline)
  - Find `baseline_start_date` = first day with steps data
  - Compute `baseline_14d_avg = compute_steps_baseline(baseline_series, baseline_start_date)`
  - Compute `current_14d_avg = trailing_average(steps_series[-14:])`
  - Get `tracking_status` and `calories_status` from their signals
  - Compute `dynamic_target = compute_dynamic_steps_target(...)`
  - Compute `status = steps_status_from_avg(current_14d_avg, dynamic_target, floor)`
  - Set `target = dynamic_target`
  - Set `value = current_14d_avg`
  - Set `target_progress_pct = min(100.0, (current_14d_avg / dynamic_target) * 100.0)`

#### 3.5 Tests (`tests/test_goals.py`)
- Test `compute_steps_baseline` (14-day avg, <14 days handling)
- Test `compute_dynamic_steps_target` (ramp rate selection, capping, floor)
- Test `steps_status_from_avg` (red/yellow/green logic)
- Test builder integration (steps signal uses dynamic target, depends on P1/P2 statuses)

---

## Cross-Phase Tasks

### Config Consolidation
- Move all goal-related config to `app/config.py` (Settings class)
- Keep `app/kernel/goals_config.py` for goal definitions only (references config values)
- Remove `app/kernel/user_profile_stub.py` (merge into config if needed, or delete)

### API Contract Updates
- `Signal` model: Add `coverage_vector`, `weekly_progress`, `dynamic_target` (all optional)
- `CardEnvelope`: `priority_summary` already exists, ensure it reflects new statuses

### Testing Strategy
- Phase 1: Test tracking vector computation, status thresholds
- Phase 2: Test weekly deficit math, modifier application
- Phase 3: Test ramp logic, dependency on P1/P2

### Documentation
- Update `README.md` with new config vars
- Update `goals.md` with final design decisions
- Document config vars in `app/config.py` docstrings

---

## Implementation Order

1. **Phase 1** (Tracking Consistency)
   - Config vars
   - Features helpers
   - Models update
   - Builder integration
   - Tests
   - Verify tracking_consistency signal appears with vector

2. **Phase 2** (Weekly Deficit)
   - Config vars
   - Signal map update (total_calories_burned)
   - Features helpers
   - Goals config update
   - Builder integration
   - Tests
   - Verify calories signal uses weekly deficit

3. **Phase 3** (Gated Ramp)
   - Config vars
   - Features helpers
   - Goals config update
   - Builder integration (depends on P1/P2)
   - Tests
   - Verify steps signal uses dynamic target

---

## Success Criteria

- All existing tests pass
- New tests cover all three phases
- Config vars are documented and have sensible defaults
- API responses include new fields (backward compatible)
- Priority summary reflects new statuses correctly
- No performance regressions (DB queries are efficient)

---

## Notes

- **Backward compatibility**: Existing `Signal.target` and `Signal.status` still populated for non-goal signals
- **Config overrides**: All tunables can be set via env vars (Railway-friendly)
- **DB queries**: Tracking start date query should be cached (one-time per session/build)
- **Legacy data**: Pre-tracking data (before Feb 9) excluded from manual tracking calculations
