from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost:5432/contextkernel"
    default_tz: str = "UTC"
    kernel_api_key: str | None = None

    # Optional user profile / goals tuning (single-user, env-backed, not yet integrated)
    user_age: int | None = None
    user_height_cm: float | None = None
    user_sex: str | None = None  # "male" | "female" | other
    user_activity_level: str | None = None  # "sedentary" | "light" | "moderate" | "active" | "very_active"

    # Phase 1: Tracking consistency config
    goals_tracking_recent_days: int = 7  # Recent reliability window
    goals_tracking_start_date: str | None = None  # ISO date string, e.g. "2026-02-09" (overrides DB query)

    # Phase 2: Calories weekly deficit config
    goals_calorie_deficit_target: float = 500.0  # kcal/day target
    goals_calories_burned_modifier: float = 0.5  # Multiplier for total_calories_burned

    # Phase 3: Steps gated ramp config
    goals_steps_floor: float = 4000.0  # Minimum acceptable 14d avg
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
