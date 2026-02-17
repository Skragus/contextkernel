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

    # Optional overrides for goal logic (stubs for future use)
    goals_tdee_override: float | None = None
    goals_step_target_override: float | None = None
    goals_calorie_deficit_override: float | None = None
    goals_steps_floor_override: float | None = None
    goals_ramp_rate_fast: float | None = None
    goals_ramp_rate_slow: float | None = None

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
