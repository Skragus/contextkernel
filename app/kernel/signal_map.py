"""
Signal extraction config for health_connect_daily.

Table: health_connect_daily
  id (UUID), device_id (string), date (date), collected_at (timestamp),
  received_at (timestamp), source_type (string), schema_version (integer),
  raw_data (JSONB), source (JSONB)

All metrics live inside raw_data. Paths are JSON paths into raw_data:
  raw_data->>'steps_total'
  raw_data->'body_metrics'->>'weight_kg'
  raw_data->'nutrition_summary'->>'calories_total'
  raw_data->'heart_rate_summary'->>'avg_hr'
  raw_data->'sleep_sessions'->0->>'duration_minutes'
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SignalConfig:
    column: str  # Always "raw_data" — the JSONB payload
    path: str  # Dot-path into raw_data
    agg: str
    unit: str | None = None


# All signals read from raw_data
SIGNAL_CONFIG: dict[str, SignalConfig] = {
    "steps_total": SignalConfig(column="raw_data", path="steps_total", agg="sum", unit="steps"),
    "weight_kg": SignalConfig(column="raw_data", path="body_metrics.weight_kg", agg="last", unit="kg"),
    "body_fat_percentage": SignalConfig(column="raw_data", path="body_metrics.body_fat_percentage", agg="last", unit="%"),
    "avg_hr": SignalConfig(column="raw_data", path="heart_rate_summary.avg_hr", agg="avg", unit="bpm"),
    "max_hr": SignalConfig(column="raw_data", path="heart_rate_summary.max_hr", agg="max", unit="bpm"),
    "min_hr": SignalConfig(column="raw_data", path="heart_rate_summary.min_hr", agg="min", unit="bpm"),
    "resting_hr": SignalConfig(column="raw_data", path="heart_rate_summary.resting_hr", agg="avg", unit="bpm"),
    "sleep_duration_minutes": SignalConfig(column="raw_data", path="sleep_sessions.0.duration_minutes", agg="avg", unit="min"),
    "calories_total": SignalConfig(column="raw_data", path="nutrition_summary.calories_total", agg="sum", unit="kcal"),
    "protein_grams": SignalConfig(column="raw_data", path="nutrition_summary.protein_grams", agg="sum", unit="g"),
}


def get_signal_config(signal_name: str) -> SignalConfig | None:
    return SIGNAL_CONFIG.get(signal_name)


def list_signals() -> list[str]:
    return list(SIGNAL_CONFIG.keys())
