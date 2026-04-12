from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SPEEDRULINGO_",
        extra="ignore",
    )

    app_name: str = "Speedrulingo API"
    database_url: str = Field(default="postgresql+psycopg://speedrulingo:speedrulingo@localhost:5432/speedrulingo")
    dbos_system_database_url: str | None = Field(default=None)
    redis_url: str | None = Field(default=None)
    audio_storage_root: Path = Field(default=Path("data/audio"))
    sentence_audio_storage_root: Path = Field(default=Path("data/sentence_audio"))
    word_audio_storage_root: Path = Field(default=Path("data/word_audio"))
    jwt_secret: str = Field(default="dev-secret-change-me-min-32-characters")
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("SPEEDRULINGO_OPENAI_API_KEY", "OPENAI_API_KEY", "openai_api_key"),
    )
    openai_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SPEEDRULINGO_OPENAI_BASE_URL", "OPENAI_BASE_URL", "openai_base_url"),
    )
    llm_timeout_seconds: float = Field(default=200.0)
    llm_cache_database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SPEEDRULINGO_LLM_CACHE_DATABASE_URL",
            "LLM_CACHE_DATABASE_URL",
            "llm_cache_database_url",
        ),
    )
    openai_debug_logging: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "SPEEDRULINGO_OPENAI_DEBUG_LOGGING",
            "OPENAI_DEBUG_LOGGING",
            "openai_debug_logging",
        ),
    )
    langsmith_tracing: bool = Field(
        default=False,
        validation_alias=AliasChoices("SPEEDRULINGO_LANGSMITH_TRACING", "LANGSMITH_TRACING"),
    )
    langsmith_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("SPEEDRULINGO_LANGSMITH_API_KEY", "LANGSMITH_API_KEY"),
    )
    langsmith_project: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SPEEDRULINGO_LANGSMITH_PROJECT", "LANGSMITH_PROJECT"),
    )
    langsmith_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SPEEDRULINGO_LANGSMITH_ENDPOINT", "LANGSMITH_ENDPOINT"),
    )
    elevenlabs_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("SPEEDRULINGO_ELEVENLABS_API_KEY", "ELEVENLABS_API_KEY"),
    )
    elevenlabs_voice_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SPEEDRULINGO_ELEVENLABS_VOICE_ID", "ELEVENLABS_VOICE_ID"),
    )
    elevenlabs_model_id: str = Field(
        default="eleven_multilingual_v2",
        validation_alias=AliasChoices("SPEEDRULINGO_ELEVENLABS_MODEL_ID", "ELEVENLABS_MODEL_ID"),
    )
    elevenlabs_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SPEEDRULINGO_ELEVENLABS_BASE_URL", "ELEVENLABS_BASE_URL"),
    )

    llm_model_word_detail: str = "mock-gpt"
    prompt_version_word_detail: str = "v1"
    llm_model_unit_article: str = "gpt-5-nano-2025-08-07"
    prompt_version_unit_article: str = "v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
