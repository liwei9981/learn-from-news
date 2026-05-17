from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-pro"

    news_api_key: str | None = None
    google_cse_api_key: str | None = None
    google_cse_id: str | None = None
    tavily_api_key: str | None = None

    notebooklm_user_data_dir: str = ".local/notebooklm-browser"
    notebooklm_base_url: str = "https://notebooklm.google.com"
    notebooklm_enabled: bool = False
    notebooklm_storage_path: str | None = None

    notebooklm_infographic_timeout_seconds: int = Field(default=1800, ge=60, le=3600)
    notebooklm_source_wait_seconds: int = Field(default=180, ge=30, le=600)
    notebooklm_research_timeout_seconds: int = Field(default=900, ge=60, le=3600)
    notebooklm_research_poll_seconds: int = Field(default=15, ge=5, le=120)
    notebooklm_research_mode: str = "fast"
    notebooklm_import_research_sources: bool = True
    notebooklm_max_research_sources: int = Field(default=12, ge=1, le=19)
    notebooklm_output_dir: str = "Output files"
    notebooklm_max_sources: int = Field(default=10, ge=1, le=50)

    default_language: str = "en"
    default_region: str = "US"
    default_max_news_results: int = Field(default=10, ge=1, le=20)
    default_lookback_days: int = Field(default=3, ge=1, le=30)
    trending_lookback_days: int = Field(default=3, ge=1, le=7)
    trending_query: str = "artificial intelligence technology business science geopolitics"

    allow_fallback_results: bool = False
    notebooklm_progress_interval_seconds: int = Field(default=300, ge=30, le=1800)

    @field_validator("notebooklm_storage_path", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
