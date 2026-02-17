"""Static goals configuration — no DB, config only.

Each GoalDefinition ties a signal (or virtual signal) to a target.
The kernel attaches goal metadata to signals and computes priority_summary
on every CardEnvelope automatically.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GoalDefinition:
    signal_name: str
    target_value: float
    target_type: str  # "minimum" | "maximum" | "exact"
    priority: int  # 1–3 for now (T1–T3)
    window_days: int = 1  # 1=daily, 7=weekly
    label: str = ""


GOALS_BY_SIGNAL: dict[str, GoalDefinition] = {
    # T1 – tracking consistency (virtual signal derived from coverage)
    "tracking_consistency": GoalDefinition(
        signal_name="tracking_consistency",
        target_value=1.0,
        target_type="minimum",
        priority=1,
        window_days=7,
        label="Tracking consistency",
    ),
    # T2 – calorie deficit
    "calories_total": GoalDefinition(
        signal_name="calories_total",
        target_value=2000.0,
        target_type="maximum",
        priority=2,
        window_days=1,
        label="Calorie target",
    ),
    # T3 – daily steps
    "steps_total": GoalDefinition(
        signal_name="steps_total",
        target_value=8000.0,
        target_type="minimum",
        priority=3,
        window_days=1,
        label="Daily steps",
    ),
}


def get_goal(signal_name: str) -> GoalDefinition | None:
    return GOALS_BY_SIGNAL.get(signal_name)


def list_goals() -> list[GoalDefinition]:
    return list(GOALS_BY_SIGNAL.values())
