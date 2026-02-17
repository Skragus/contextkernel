"""Signals catalog endpoint — user context + signal semantics."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import verify_api_key
from app.config import settings

router = APIRouter(prefix="/kernel", tags=["signals"])


@router.get("/signals")
async def get_signals_catalog(
    _: str = Depends(verify_api_key),
) -> dict:
    """Return user context + signal catalog for agent interpretation.
    
    This is the 'context' endpoint — call once to understand:
    - Who the user is (demographics)
    - How signals work (semantics, targets, directions)
    - What goals are (long-term targets)
    
    Then use lightweight data endpoints for temporal values.
    """
    return {
        "context": {
            "user": {
                "age": settings.user_age,
                "sex": settings.user_sex,
                "height_cm": settings.user_height_cm,
                "weight_kg": settings.user_weight_kg,
                "tracking_start_date": settings.goals_tracking_start_date,
            },
            "defaults": {
                "timezone": settings.default_tz,
                "calorie_deficit_daily": settings.goals_calorie_deficit_target,
                "steps_target_longterm": settings.goals_steps_long_term_target,
                "steps_floor": settings.goals_steps_floor,
            },
        },
        "signals": [
            {
                "path": "steps_total",
                "display_name": "Steps",
                "unit": "steps",
                "source": "automatic",
                "cadence": "intraday",
                "direction": "higher_better",
                "target_longterm": settings.goals_steps_long_term_target,
                "required_for_tracking": False,
            },
            {
                "path": "total_calories_burned",
                "display_name": "Calories Burned",
                "unit": "kcal",
                "source": "automatic",
                "cadence": "intraday",
                "direction": "neutral",
                "target_longterm": None,
                "required_for_tracking": False,
            },
            {
                "path": "nutrition_summary.calories_total",
                "display_name": "Calories Eaten",
                "unit": "kcal",
                "source": "manual",
                "cadence": "daily",
                "direction": "neutral",
                "target_longterm": None,
                "target_dynamic": True,
                "required_for_tracking": True,
            },
            {
                "path": "nutrition_summary.protein_grams",
                "display_name": "Protein",
                "unit": "g",
                "source": "manual",
                "cadence": "daily",
                "direction": "higher_better",
                "target_longterm": 150.0,
                "required_for_tracking": False,
            },
            {
                "path": "body_metrics.weight_kg",
                "display_name": "Weight",
                "unit": "kg",
                "source": "manual",
                "cadence": "daily",
                "direction": "lower_better",
                "target_longterm": None,
                "required_for_tracking": True,
            },
            {
                "path": "body_metrics.body_fat_percentage",
                "display_name": "Body Fat",
                "unit": "%",
                "source": "automatic",
                "cadence": "daily",
                "direction": "lower_better",
                "target_longterm": None,
                "required_for_tracking": False,
            },
            {
                "path": "heart_rate_summary.resting_hr",
                "display_name": "Resting Heart Rate",
                "unit": "bpm",
                "source": "automatic",
                "cadence": "intraday",
                "direction": "lower_better",
                "target_longterm": 60.0,
                "required_for_tracking": False,
            },
            {
                "path": "sleep_sessions",
                "display_name": "Sleep Duration",
                "unit": "minutes",
                "source": "automatic",
                "cadence": "daily",
                "direction": "higher_better",
                "target_longterm": 480,
                "required_for_tracking": False,
            },
            {
                "path": "oxygen_saturation_percentage",
                "display_name": "Blood Oxygen",
                "unit": "%",
                "source": "automatic",
                "cadence": "intraday",
                "direction": "higher_better",
                "target_longterm": 95.0,
                "required_for_tracking": False,
            },
            {
                "path": "tracking_consistency",
                "display_name": "Tracking Consistency",
                "unit": "ratio",
                "source": "derived",
                "cadence": "daily",
                "direction": "higher_better",
                "target_longterm": 1.0,
                "required_for_tracking": True,
            },
        ],
    }
