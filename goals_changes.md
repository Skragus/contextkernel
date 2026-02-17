## Upgrade changes

Data Reliability (Is the system alive?)

Behavior Direction (Are we steering the right way?)

Intervention Policy (When do we notify?)

And you want each of those to have time-awareness, ramp-up awareness, and “don’t be a dumbass” filters.

1) Priority #1: Tracking as “system operational”

This is the right obsession. If tracking is broken, everything downstream becomes fiction.

But you nailed the two traps:

“100% for a month → too slow to detect failure” (low sensitivity)

“50% for the month because you started 2 weeks ago → false red” (bad denominator)

So tracking needs two scores:

Recent reliability: last 7 days (or 10) — “is it alive right now?”

Maturity-aware coverage: since tracking-start date — “how established is this habit?”

And you also want “manual-only counts” vs “automatic doesn’t count.” That’s another smart separation:

Weight and calories are manual signals, steps/sleep are mostly automatic.
So define tracking consistency as:
manual_tracking = weighted_presence(weight, calories, maybe protein later)
where presence is “did we see an entry that day?”

Now the denominator issue (“started 2 weeks ago”) is solved by a concept you should formalize in Kernel:

Tracking Start Date = first day with any manual signal present (or first day with calories OR weight).
Then coverage calculations use from = max(user_from, tracking_start).

Also your “one number isn’t good” is correct. Coverage should output a small vector, not a scalar:

manual_coverage_7d

manual_coverage_30d (or since-start)

days_since_last_manual_entry

streak_manual_days (optional)

Green flag being 80–85% is sensible for humans. But make it soft thresholds: green/yellow/red bands, not pass/fail.

2) Calories: murky by nature, so don’t force purity

Calories are not a “did you hit exactly 500 deficit” sport. It’s an energy trend thing.

What you want is basically:

A weekly deficit target (because daily noise is huge)

A tolerance zone (“300 deficit is still good”)

A dynamic budget tied to TDEE, but not worshipping it

So instead of “target calories = X”, make it:

daily_budget = TDEE_est - deficit_goal (deficit_goal maybe 500)

but evaluate on weekly averages / weekly sums:

weekly_deficit_actual = Σ(TDEE_est - intake)

compare to weekly_deficit_goal = 7 * deficit_goal

Then your “80% of results aimed for” becomes clean math:

progress_pct = clamp(weekly_deficit_actual / weekly_deficit_goal)

Now the grey area becomes a feature:

If you hit 60% of deficit goal, that’s not red doom, that’s yellow “fine but drifting.”

And yes: events exist. So you add a “spike tolerance” rule:

one high day doesn’t tank the week as long as weekly deficit is decent

That’s literally why weekly evaluation exists.

Active calories: don’t bake it into budget as a primary lever unless you really want chaos. Better:

Use steps as a proxy for activity adjustment (more stable)

Or if you do active calories, multiply by a conservative factor like you said (e.g., 0.5) and cap it (e.g., +300/day max adjustment) so it can’t excuse a pizza apocalypse.

3) Steps: don’t set 8k as a daily courtroom, set it as a trajectory

Your instinct is “raise baseline gradually,” and you want it to depend on other greens (tracking/calories). That’s actually cool: a gated ramp.

Steps should be evaluated as:

14-day rolling average (less noisy than 7)

with a floor (minimum acceptable like 4k avg)

and a ramp rate (increase target by X% when conditions are good)

So the goal isn’t “8000 every day,” it’s:

“your rolling avg target this period is baseline * (1 + ramp_rate)”

Where baseline could be last 14d avg at the moment the goal starts.

Then you can do:

if tracking green AND calories green → ramp_rate = 5–10% per week

if tracking yellow OR calories yellow → ramp_rate = 2–3%

if either red → ramp_rate = 0% (stabilize, don’t push)

That avoids the system demanding growth during chaos weeks.

And yes, 14d windows feel right for steps, because steps are weather/shift dependent and noisy as hell.

1. Tracking as “system operational” — correct framing
Two-score model (recent reliability + maturity-aware) solves the denominator problem.
Tracking start date = max(first_manual_signal_date, user_from) is clean.
Manual vs automatic separation is correct (weight/calories vs steps/sleep).
Vector output (manual_coverage_7d, manual_coverage_30d, days_since_last, streak) is more useful than a scalar.
Implementation note: You’ll need to track “first manual signal date” somewhere. Options:
Config: TRACKING_START_DATE env var or config field (manual, but explicit).
DB query: SELECT MIN(date) FROM health_connect_daily WHERE raw_data->'nutrition_summary'->>'calories_total' IS NOT NULL OR raw_data->'body_metrics'->>'weight_kg' IS NOT NULL (automatic, but adds a query).
Hybrid: cache it on first card build, store in memory/config.
Recommendation: Start with DB query (one-time per build), cache it, and allow override via config if needed.
2. Calories as weekly deficit trend — correct direction
Weekly evaluation reduces daily noise.
weekly_deficit_actual / weekly_deficit_goal is straightforward.
Spike tolerance (one high day doesn’t tank the week) is sensible.
Open questions:
TDEE estimation: Do you have TDEE in the DB, or compute it? If compute, what formula (BMR + activity multiplier)? This affects daily_budget = TDEE_est - deficit_goal.
Active calories: The 0.5x factor + 300 cap is conservative. Do you have active_calories in raw_data, or derive from steps?
Recommendation: Start with a fixed deficit_goal (e.g., 500 kcal/day → 3500/week). Add TDEE/active-calorie adjustments later if data is available.
3. Steps as gated ramp — psychologically sound
14-day rolling average reduces noise.
Gated ramp (tracking/calories green → ramp; red → stabilize) prevents pushing during chaos.
Floor (4k minimum) avoids punishing low-activity periods.
Implementation note: The ramp logic creates a dependency graph:
steps_goal = f(tracking_status, calories_status, current_baseline)
This means:
Steps evaluation depends on tracking + calories status.
Priority summary ordering matters (P1 → P2 → P3).
Recommendation: Compute P1 and P2 first, then compute P3 with their statuses as inputs. This fits the current builder flow.
Concerns and recommendations
1. Complexity vs MVP
Current system: ~60 lines of config + simple threshold math.
Proposed: tracking start date detection, weekly deficit math, TDEE estimation, gated ramps, vector outputs.
Recommendation: Phased rollout:
Phase 1: Tracking start date + manual coverage vector (P1 upgrade).
Phase 2: Weekly calorie evaluation (P2 upgrade).
Phase 3: Gated steps ramp (P3 upgrade).
2. Data availability
Do you have TDEE in raw_data?
Do you have active_calories separate from calories_total?
Can you reliably detect “first manual signal date” from the DB?
Recommendation: Audit your raw_data schema first. If TDEE/active calories aren’t present, start with simplified models (fixed deficit goal, steps-only ramp) and extend later.
3. Config vs computation
Current: Goals are pure config (GOALS_BY_SIGNAL dict).
Proposed: Goals become computed (ramp rates, tracking start, weekly windows).
Recommendation: Keep config for “what goals exist” and “targets/thresholds,” but move evaluation logic into features.py helpers. Example:
# Config stays simpleGOALS_BY_SIGNAL = {    "steps_total": GoalDefinition(priority=3, baseline_target=8000, ramp_rate=0.05, ...)}# Features.py gets smart helpersdef compute_steps_goal_with_ramp(    current_14d_avg: float,    tracking_status: str,    calories_status: str,    config: GoalDefinition) -> float:    # Gated ramp logic here
4. API contract changes
Current: Signal.target is a float, status is red/yellow/green.
Proposed: Tracking becomes a vector, calories become weekly deficit progress, steps become a dynamic target.
Recommendation: Extend Signal with optional fields:
class Signal(BaseModel):    # ... existing fields ...    # New optional fields for advanced goals    coverage_vector: dict[str, float] | None = None  # For tracking    weekly_progress: float | None = None  # For calories    dynamic_target: float | None = None  # For steps ramp
Keep backward compatibility: if a goal doesn’t use advanced features, it still populates target/status as before.