from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    secret_key: str = "dev-only-change-me"
    groq_api_key: str = ""
    groq_api_keys: str = ""
    llm_model: str = "openai/gpt-oss-120b"

    # The Verification Desk sign-in. Admin sign-in is off while the password is empty.
    admin_username: str = "admin"
    admin_password: str = "Admin123"
    admin_name: str = "Entitle reviewer"

    n8n_base_url: str = ""
    n8n_shared_secret: str = "dev-shared-secret"
    base_url: str = "http://127.0.0.1:8000"

    port: int = 8000
    database_url: str = "sqlite:///./data/entitle.db"
    database_url_unpooled: str = ""
    enable_scheduler: bool = True
    watcher_interval_seconds: int = 1800
    fetch_remote: bool = True

    @property
    def admin_ready(self) -> bool:
        return bool(self.admin_username.strip() and self.admin_password)


@lru_cache
def get_settings() -> Settings:
    return Settings()
