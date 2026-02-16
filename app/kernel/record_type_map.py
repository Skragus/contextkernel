"""
Record-type extraction configuration.

Each entry maps a health_records.record_type value to:
  - agg: aggregation method ("sum" | "avg" | "max" | "min" | "last")
  - value_key: dot-path into the JSON `data` column
    Supports nested dicts ("heart_rate_summary.avg_bpm") and
    list indexing ("sleep_sessions.0.duration_minutes").
  - unit: human-readable unit label (optional)

DEFAULT_CONFIG is used as fallback for unknown record_types:
  - agg: "avg"
  - value_key: None  (triggers "first numeric value" heuristic)

Paths below are derived from example-assumed.json.  Once we see real DB
rows we can trim / extend.  The extractor gracefully falls back to the
first-numeric heuristic when a configured path misses.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RecordTypeConfig:
    agg: str = "avg"
    value_key: str | None = None
    unit: str | None = None


DEFAULT_CONFIG = RecordTypeConfig(agg="avg", value_key=None, unit=None)

RECORD_TYPE_CONFIG: dict[str, RecordTypeConfig] = {
    # -----------------------------------------------------------------------
    # Per-metric rows  (record_type is the metric name, data = {"value": N})
    # Keep these so both shapes work.
    # -----------------------------------------------------------------------
    "step_count": RecordTypeConfig(agg="sum", value_key="value", unit="steps"),
    "distance_walking_running": RecordTypeConfig(agg="sum", value_key="value", unit="km"),
    "active_energy_burned": RecordTypeConfig(agg="sum", value_key="value", unit="kcal"),
    "basal_energy_burned": RecordTypeConfig(agg="sum", value_key="value", unit="kcal"),
    "flights_climbed": RecordTypeConfig(agg="sum", value_key="value", unit="floors"),
    "exercise_time": RecordTypeConfig(agg="sum", value_key="value", unit="min"),
    "stand_time": RecordTypeConfig(agg="sum", value_key="value", unit="min"),
    "heart_rate": RecordTypeConfig(agg="avg", value_key="value", unit="bpm"),
    "resting_heart_rate": RecordTypeConfig(agg="avg", value_key="value", unit="bpm"),
    "heart_rate_variability": RecordTypeConfig(agg="avg", value_key="value", unit="ms"),
    "walking_heart_rate_average": RecordTypeConfig(agg="avg", value_key="value", unit="bpm"),
    "sleep_analysis": RecordTypeConfig(agg="sum", value_key="value", unit="hr"),
    "body_mass": RecordTypeConfig(agg="last", value_key="value", unit="kg"),
    "body_mass_index": RecordTypeConfig(agg="last", value_key="value", unit=""),
    "body_fat_percentage": RecordTypeConfig(agg="last", value_key="value", unit="%"),
    "blood_oxygen": RecordTypeConfig(agg="avg", value_key="value", unit="%"),
    "respiratory_rate": RecordTypeConfig(agg="avg", value_key="value", unit="breaths/min"),
    "blood_pressure_systolic": RecordTypeConfig(agg="avg", value_key="value", unit="mmHg"),
    "blood_pressure_diastolic": RecordTypeConfig(agg="avg", value_key="value", unit="mmHg"),
    "dietary_energy": RecordTypeConfig(agg="sum", value_key="value", unit="kcal"),
    "dietary_water": RecordTypeConfig(agg="sum", value_key="value", unit="mL"),
    "dietary_caffeine": RecordTypeConfig(agg="sum", value_key="value", unit="mg"),
    "mindful_minutes": RecordTypeConfig(agg="sum", value_key="value", unit="min"),
    # -----------------------------------------------------------------------
    # Daily-blob rows  (record_type = "daily" / "daily_summary", data = big JSON)
    # Paths match example-assumed.json structure.
    # If the real DB stores one fat row per day, these let the extractor
    # pull out individual signals from the nested blob.
    # -----------------------------------------------------------------------
    "steps_total": RecordTypeConfig(agg="sum", value_key="steps_total", unit="steps"),
    "weight": RecordTypeConfig(agg="last", value_key="body_metrics.weight_kg", unit="kg"),
    "bmi": RecordTypeConfig(agg="last", value_key="body_metrics.bmi", unit=""),
    "body_fat": RecordTypeConfig(agg="last", value_key="body_metrics.body_fat_percentage", unit="%"),
    "calories_consumed": RecordTypeConfig(agg="sum", value_key="nutrition_summary.calories_consumed", unit="kcal"),
    "calories_burned": RecordTypeConfig(agg="sum", value_key="nutrition_summary.calories_burned", unit="kcal"),
    "protein": RecordTypeConfig(agg="sum", value_key="nutrition_summary.protein_g", unit="g"),
    "carbs": RecordTypeConfig(agg="sum", value_key="nutrition_summary.carbs_g", unit="g"),
    "fat": RecordTypeConfig(agg="sum", value_key="nutrition_summary.fat_g", unit="g"),
    "water": RecordTypeConfig(agg="sum", value_key="nutrition_summary.water_ml", unit="mL"),
    "heart_rate_avg": RecordTypeConfig(agg="avg", value_key="heart_rate_summary.avg_bpm", unit="bpm"),
    "resting_hr": RecordTypeConfig(agg="avg", value_key="heart_rate_summary.resting_bpm", unit="bpm"),
    "max_hr": RecordTypeConfig(agg="max", value_key="heart_rate_summary.max_bpm", unit="bpm"),
    "min_hr": RecordTypeConfig(agg="min", value_key="heart_rate_summary.min_bpm", unit="bpm"),
    "sleep_duration": RecordTypeConfig(agg="avg", value_key="sleep_sessions.0.duration_minutes", unit="min"),
    "sleep_efficiency": RecordTypeConfig(agg="avg", value_key="sleep_sessions.0.efficiency", unit="%"),
    "sleep_deep": RecordTypeConfig(agg="avg", value_key="sleep_sessions.0.stages.deep_minutes", unit="min"),
    "sleep_rem": RecordTypeConfig(agg="avg", value_key="sleep_sessions.0.stages.rem_minutes", unit="min"),
    "sleep_light": RecordTypeConfig(agg="avg", value_key="sleep_sessions.0.stages.light_minutes", unit="min"),
}


def get_config(record_type: str) -> RecordTypeConfig:
    """Return config for a record_type, falling back to DEFAULT_CONFIG."""
    return RECORD_TYPE_CONFIG.get(record_type, DEFAULT_CONFIG)
