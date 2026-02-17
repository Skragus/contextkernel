from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost:5432/contextkernel"
    default_tz: str = "UTC"
    kernel_api_key: str | None = None

    # Default user profile (BMR/TDEE when DB has no body_metrics). Override via env.
    user_age: int | None = 27
    user_height_cm: float | None = 193.0
    user_sex: str | None = "male"  # "male" | "female"
    user_activity_level: str | None = "sedentary"  # TDEE uses goals_tdee_activity_factor (1.2 = sedentary)

    # Phase 1: Tracking consistency config
    goals_tracking_recent_days: int = 7  # Recent reliability window
    goals_tracking_start_date: str | None = None  # ISO date string, e.g. "2026-02-09" (overrides DB query)

    # Phase 2: Calories (daily goal from rolling 7d window, never use total_calories_burned)
    goals_calorie_deficit_target: float = 500.0  # kcal/day baseline (3500/week)
    goals_surplus_recovery_factor: float = 0.05  # When behind, deficit for remaining days +5%
    goals_tdee_activity_factor: float = 1.2  # TDEE = BMR × this (sedentary baseline)
    goals_steps_to_kcal: float = 0.04  # kcal per step (activity above TDEE)
    goals_activity_modifier: float = 0.5  # Conservative factor for earned activity (on top of TDEE)

    # Phase 3: Steps gated ramp config
    goals_steps_floor: float = 3500.0  # Minimum acceptable 14d avg
    goals_steps_long_term_target: float = 8000.0  # Ultimate goal
    goals_steps_ramp_rate_fast: float = 0.075  # 7.5% per week when conditions good
    goals_steps_ramp_rate_slow: float = 0.025  # 2.5% per week when conditions moderate

    # Optional overrides for goal logic (legacy stubs, may be removed)
    goals_tdee_override: float | None = None
    goals_step_target_override: float | None = None
    goals_calorie_deficit_override: float | None = None
    goals_steps_floor_override: float | None = None

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
