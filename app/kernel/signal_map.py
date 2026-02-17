"""
Signal extraction config for health_connect_daily.

Table: health_connect_daily
Columns: id, device_id, date, steps_total, body_metrics (JSONB), heart_rate_summary (JSONB),
         sleep_sessions (JSONB), exercise_sessions (JSONB), nutrition_summary (JSONB)

Each signal maps to:
  - column: source column (typed or JSONB)
  - path: dot-path into column (None for typed column like steps_total)
  - agg: aggregation ("sum" | "avg" | "max" | "min" | "last")
  - unit: human-readable unit

Paths use actual DB field names (avg_hr, resting_hr, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SignalConfig:
    column: str
    path: str | None  # None = typed column; "weight_kg" = into JSONB
    agg: str
    unit: str | None = None


# Signals we can extract from health_connect_daily
SIGNAL_CONFIG: dict[str, SignalConfig] = {
    "steps_total": SignalConfig(column="steps_total", path=None, agg="sum", unit="steps"),
    "weight_kg": SignalConfig(column="body_metrics", path="weight_kg", agg="last", unit="kg"),
    "body_fat_percentage": SignalConfig(column="body_metrics", path="body_fat_percentage", agg="last", unit="%"),
    "avg_hr": SignalConfig(column="heart_rate_summary", path="avg_hr", agg="avg", unit="bpm"),
    "max_hr": SignalConfig(column="heart_rate_summary", path="max_hr", agg="max", unit="bpm"),
    "min_hr": SignalConfig(column="heart_rate_summary", path="min_hr", agg="min", unit="bpm"),
    "resting_hr": SignalConfig(column="heart_rate_summary", path="resting_hr", agg="avg", unit="bpm"),
    "sleep_duration_minutes": SignalConfig(column="sleep_sessions", path="0.duration_minutes", agg="avg", unit="min"),
    "calories_total": SignalConfig(column="nutrition_summary", path="calories_total", agg="sum", unit="kcal"),
    "protein_grams": SignalConfig(column="nutrition_summary", path="protein_grams", agg="sum", unit="g"),
}


def get_signal_config(signal_name: str) -> SignalConfig | None:
    return SIGNAL_CONFIG.get(signal_name)


def list_signals() -> list[str]:
    return list(SIGNAL_CONFIG.keys())
