from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


import sys

if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "校园运动会赛事成绩管理系统"
    api_prefix: str = "/api/v1"
    secret_key: str = "change-this-secret-before-production"
    access_token_minutes: int = 480
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'sports_meet.db').as_posix()}"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    initial_developer_username: str = "developer01"
    initial_developer_password: str = "Dev123456!"
    demo_admin_password: str = "Admin123456!"
    export_dir: str = str(PROJECT_ROOT / "data" / "exports")
    auto_seed: bool = True

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
