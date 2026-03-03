from functools import lru_cache

from langchain_community.cache import SQLiteCache
from langchain_core.globals import set_llm_cache
from langchain_openai import ChatOpenAI

from settings import get_settings


@lru_cache
def _configure_llm_cache() -> None:
    settings = get_settings()
    set_llm_cache(SQLiteCache(database_path=settings.llm_cache_path))


def create_chat_openai(*, model: str) -> ChatOpenAI:
    _configure_llm_cache()
    settings = get_settings()
    api_key = settings.openai_api_key
    if api_key is None:
        msg = "SPEEDRULINGO_OPENAI_API_KEY must be configured for real LLM calls"
        raise ValueError(msg)
    return ChatOpenAI(
        model=model,
        api_key=api_key.get_secret_value(),
        reasoning={"effort": "low"},
        base_url=settings.openai_base_url,
        timeout=settings.llm_timeout_seconds,
    )
