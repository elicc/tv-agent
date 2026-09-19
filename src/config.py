"""Environment-backed runtime settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="TV_AGENT_",
        extra="ignore",
    )

    app_name: str = "tv-agent"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    docs_enabled: bool = True

    service_api_key: SecretStr | None = None

    douban_base_url: str = "https://frodo.douban.com"
    douban_api_key: SecretStr | None = None
    douban_timeout_seconds: float = Field(default=5.0, gt=0, le=30)

    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: SecretStr | None = None
    llm_model: str = "deepseek-flash"
    llm_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    llm_reasoning_effort: str = "high"

    agent_max_rounds: int = Field(default=3, ge=1, le=5)
    agent_max_tool_calls: int = Field(default=5, ge=1, le=10)

    database_path: Path = Path("data/tv-agent.db")
    matched_cache_ttl_seconds: int = Field(default=30 * 24 * 60 * 60, ge=60)
    candidate_cache_ttl_seconds: int = Field(default=24 * 60 * 60, ge=60)

    @property
    def douban_configured(self) -> bool:
        return bool(self.douban_api_key and self.douban_api_key.get_secret_value())

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_api_key.get_secret_value())

    @property
    def authentication_enabled(self) -> bool:
        return bool(self.service_api_key and self.service_api_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
