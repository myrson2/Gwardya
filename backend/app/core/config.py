from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Typed configuration loaded from backend/.env.

    Importing this module fails fast if a required value (notably SECRET_KEY)
    is missing — the app must never boot with a default secret.
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    secret_key: str = Field(min_length=32)
    database_url: str
    test_database_url: str
    frontend_origin: str = "http://localhost:5173"
    access_token_minutes: int = Field(default=15, gt=0)
    refresh_token_days: int = Field(default=7, gt=0)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


settings = Settings() # type:ignore
