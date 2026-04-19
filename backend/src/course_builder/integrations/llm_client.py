from functools import lru_cache
from hashlib import sha256

from langchain_core.caches import RETURN_VAL_TYPE, BaseCache
from langchain_core.globals import set_llm_cache
from langchain_core.load.dump import dumps
from langchain_core.load.load import loads
from langchain_openai import ChatOpenAI
from sqlalchemy import Integer, String, Text, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from settings import get_settings


def _hash_cache_key(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


class CacheBase(DeclarativeBase):
    pass


class HashedLLMCacheRow(CacheBase):
    __tablename__ = "hashed_llm_cache"

    prompt_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    llm_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    idx: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt: Mapped[str] = mapped_column(Text)
    llm: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)


class HashedSQLAlchemyCache(BaseCache):
    def __init__(self, engine: Engine):
        self.engine = engine
        CacheBase.metadata.create_all(self.engine)

    def lookup(self, prompt: str, llm_string: str) -> RETURN_VAL_TYPE | None:
        prompt_hash = _hash_cache_key(prompt)
        llm_hash = _hash_cache_key(llm_string)
        stmt = (
            select(HashedLLMCacheRow.response)
            .where(HashedLLMCacheRow.prompt_hash == prompt_hash)
            .where(HashedLLMCacheRow.llm_hash == llm_hash)
            .where(HashedLLMCacheRow.prompt == prompt)
            .where(HashedLLMCacheRow.llm == llm_string)
            .order_by(HashedLLMCacheRow.idx)
        )
        with Session(self.engine) as session:
            rows = session.execute(stmt).scalars().all()
            if rows:
                return [loads(row) for row in rows]
        return None

    def update(self, prompt: str, llm_string: str, return_val: RETURN_VAL_TYPE) -> None:
        prompt_hash = _hash_cache_key(prompt)
        llm_hash = _hash_cache_key(llm_string)
        items = [
            HashedLLMCacheRow(
                prompt_hash=prompt_hash,
                llm_hash=llm_hash,
                prompt=prompt,
                llm=llm_string,
                response=dumps(generation),
                idx=index,
            )
            for index, generation in enumerate(return_val)
        ]
        with Session(self.engine) as session, session.begin():
            for item in items:
                session.merge(item)

    def clear(self, **_kwargs: object) -> None:
        with Session(self.engine) as session:
            session.query(HashedLLMCacheRow).delete()
            session.commit()


@lru_cache
def _configure_llm_cache() -> None:
    settings = get_settings()
    cache_database_url = settings.llm_cache_database_url or settings.database_url
    set_llm_cache(HashedSQLAlchemyCache(create_engine(cache_database_url, pool_pre_ping=True)))


def create_chat_openai(*, model: str, reasoning_effort: str) -> ChatOpenAI:
    _configure_llm_cache()
    settings = get_settings()
    api_key = settings.openai_api_key
    if api_key is None:
        msg = "SPEEDRULINGO_OPENAI_API_KEY must be configured for real LLM calls"
        raise ValueError(msg)
    return ChatOpenAI(
        model=model,
        api_key=api_key.get_secret_value(),
        reasoning={"effort": reasoning_effort},
        base_url=settings.openai_base_url,
        timeout=settings.llm_timeout_seconds,
    )
