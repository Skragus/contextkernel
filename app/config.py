from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost:5432/contextkernel"
    default_tz: str = "UTC"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
