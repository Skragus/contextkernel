**Updated hierarchy (conceptual priorities)**

| Tier | Goal                | Target       | Source in CK today                    |
|------|---------------------|--------------|---------------------------------------|
| **T1** | Tracking consistency | 100% days logged | coverage from `health_connect_daily`    |
| **T2** | Calorie deficit      | -500 kcal    | `raw_data.nutrition_summary`          |
| **T3** | Daily steps          | 8,000 steps  | `raw_data.steps_total`                |
| **T4** | Weight training      | 4 sessions/wk | Hevy / `exercise_sessions` (future)   |

T1–T5 are **conceptual tiers**; in the API we expose a numeric `priority` field
instead of a `tier` field on each signal.

Goals are **config-only** (no DB table) and **API-key protected**, designed to be used
as tools by a Jarvis-style agent.

---

## 1. Goals config (no DB)

New module: `app/kernel/goals_config.py`

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GoalDefinition:
    signal_name: str         # \"steps_total\", \"calories_total\", \"protein_grams\"
    target_value: float
    target_type: str         # \"minimum\" | \"maximum\" | \"exact\"
    priority: int            # 1–5, maps conceptually to T1–T5
    window_days: int = 1     # 1=daily, 7=weekly, etc.


GOALS_BY_SIGNAL: dict[str, GoalDefinition] = {
    # T1 – tracking consistency (derived from coverage)
    \"tracking_consistency\": GoalDefinition(
        signal_name=\"tracking_consistency\",
        target_value=1.0,
        target_type=\"minimum\",
        priority=1,
        window_days=7,
    ),
    # T2 – calories (deficit vs TDEE, interpreted by the agent/upstream)
    \"calories_total\": GoalDefinition(
        signal_name=\"calories_total\",
        target_value=500.0,   # target deficit magnitude
        target_type=\"maximum\",
        priority=2,
        window_days=7,
    ),
    # T3 – steps
    \"steps_total\": GoalDefinition(
        signal_name=\"steps_total\",
        target_value=8000.0,
        target_type=\"minimum\",
        priority=3,
        window_days=1,
    ),
}
```

- No `user_goals` table in the MVP; per-user, mutable goals are a **later** phase.
- The kernel uses this config to attach goal metadata onto `Signal`s and to compute
  summary views.

---

## 2. API endpoints (read-only, API-key protected)

All new endpoints live in `app/kernel/router.py` and use `Depends(verify_api_key)`.

```http
GET /kernel/goals
  - Returns static goals config (GOALS_BY_SIGNAL) as JSON.

GET /kernel/goals/progress
  - Query: device_id, from, to, tz
  - Internally calls one or more builders (e.g. daily_summary)
  - Returns per-goal progress + per-priority (T1–T5) summary.
```

Example response for `/kernel/goals/progress`:

```json
{
  \"date\": \"2026-02-16\",
  \"device_id\": \"…\",
  \"priorities\": {
    \"1\": {\"status\": \"green\", \"progress\": 100, \"trend\": \"flat\", \"message\": \"7/7 days logged\"},
    \"2\": {\"status\": \"yellow\", \"progress\": 75, \"trend\": \"up\",   \"message\": \"-375 kcal avg (target -500)\"},
    \"3\": {\"status\": \"red\",   \"progress\": 78, \"trend\": \"up\",   \"message\": \"6,240 / 8,000 steps\"}
  }
}
```

CRUD-style endpoints (`POST /kernel/goals`, `PUT /kernel/goals/{id}`) are intentionally
**out of scope** until we have a clear persistence story and are ready to add DB
migrations.

---

## 3. Card / Signal modifications

We reuse `Signal.target` and add lightweight, optional goal fields. Naming:

- `priority` instead of `tier`
- `status` instead of `tier_status`
- a simple `trend` field

Per `Signal` (conceptual JSON):

```json
{
  \"name\": \"steps_total\",
  \"value\": 6240,
  \"baseline\": 5800,
  \"delta\": 440,
  \"target\": 8000,
  \"target_progress_pct\": 78,
  \"priority\": 3,         // maps to T3 in the table above
  \"status\": \"yellow\",  // red <50%, yellow 50-99%, green 100%
  \"trend\": \"up\"        // \"up\" | \"down\" | \"flat\"
}
```

Add an optional `priority_summary` field on `CardEnvelope`:

```json
{
  \"priority_summary\": {
    \"1\": {\"status\": \"green\", \"progress\": 100, \"trend\": \"flat\", \"message\": \"7/7 days logged\"},
    \"2\": {\"status\": \"yellow\", \"progress\": 75, \"trend\": \"up\",   \"message\": \"-375 kcal avg (target -500)\"},
    \"3\": {\"status\": \"red\",   \"progress\": 78, \"trend\": \"up\",   \"message\": \"6,240 / 8,000 steps\"}
  }
}
```

### Trend heuristic (kernel-computed)

Trend is a coarse label computed in the kernel, so the agent does not have to rebuild
the heuristic each time:

- Take a **recent window** vs a **prior window** (`window_days`):
  - For daily goals: last 3–7 days vs the prior 3–7 days.
  - For weekly: this week vs last week.
- Compute `recent_avg` and `prior_avg`:
- For `target_type = \"minimum\"` (e.g. steps):
    - `trend = \"up\"` if `recent_avg >= prior_avg * 1.05`
    - `trend = \"down\"` if `recent_avg <= prior_avg * 0.95`
    - else `trend = \"flat\"`.
  - For `target_type = \"maximum\"` (calories):
    - Interpret “up”/“down” as **better/worse** relative to the goal when computing
      the label, but keep the enum as `\"up\" | \"down\" | \"flat\"` for simplicity.

The agent can still inspect raw values/baselines for nuance, but gets a cheap,
pre-baked trend signal for routing/decision-making.

---

## 4. Compliance & streaks (Phase 2)

Planned but not part of the first implementation:

- **Daily score**: weighted average of progress across priorities, using
  `GoalDefinition.priority` as weights.
- **Streak tracking**: consecutive days where all configured priorities are `status =
  \"green\"`.

These are likely exposed as separate cards/presets (e.g. `/kernel/cards/compliance_week`)
rather than baked into every envelope.

---

## 5. Hevy integration (future-friendly)

Hevy sample payload (simplified):

```json
{
  \"title\": \"Push\",
  \"start_time\": \"2026-02-12T14:55:30Z\",
  \"end_time\": \"2026-02-12T15:00:30Z\",
  \"duration_minutes\": 5,
  \"notes\": \"Push\\nThursday, ...\\nBench Press (Barbell) ... @hevyapp\\nhttps://hevy.com/workout/...\"
}
```

Because the detailed sets/reps are squeezed into a **free-text `notes` field**, we do
**not** try to parse them inside ContextKernel. Instead:

- Near-term: treat Hevy as a **binary strength flag** per day (did strength training or not).
  - This flag can be computed upstream and written into `raw_data.exercise_sessions` or
    another normalized field.
  - Then a future T4/priority-4 goal can be defined as “≥4 days/week with
    `strength_session = true`”.
- Longer-term: if we want richer strength metrics, introduce a dedicated Hevy/strength
  connector and schema; this stays **out of scope** for the current kernel MVP.
