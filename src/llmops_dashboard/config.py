from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    # Phase 3: alerting notifiers
    slack_webhook_url: str = ""
    alert_email_from: str = ""
    alert_email_to: str = ""
    smtp_host: str = ""
    smtp_port: int = 587


settings = Settings()
