from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    secret_key: str = "dev-only-change-me"
    vault_key: str = ""
    groq_api_key: str = ""
    groq_api_keys: str = ""
    llm_model: str = "openai/gpt-oss-120b"

    mail_host: str = ""
    mail_port: int = 587
    mail_user: str = ""
    mail_pass: str = ""
    mail_from: str = ""
    demo_recipient: str = ""

    n8n_base_url: str = ""
    n8n_shared_secret: str = "dev-shared-secret"
    base_url: str = "http://127.0.0.1:8000"
    admin_email: str = "admin@entitle.local"
    admin_password: str = "change-me-admin"
    staff_one_email: str = "staff.one@entitle.local"
    staff_one_password: str = "change-me-staff-1"
    staff_two_email: str = "staff.two@entitle.local"
    staff_two_password: str = "change-me-staff-2"
    citizen_email: str = "citizen@entitle.local"
    citizen_password: str = "change-me-citizen"
    citizen_display_name: str = "Hina Khan"
    fetch_remote: bool = True

    port: int = 8000
    database_url: str = "sqlite:///./data/entitle.db"
    replay_mode: bool = False
    enable_scheduler: bool = True
    watcher_interval_seconds: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()
