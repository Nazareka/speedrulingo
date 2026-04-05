from __future__ import annotations

from collections.abc import Generator
import os

from alembic.config import Config
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from alembic import command

TEST_DATABASE_URL = os.getenv(
    "SPEEDRULINGO_TEST_DATABASE_URL",
    "postgresql+psycopg://speedrulingo:speedrulingo@localhost:5432/speedrulingo_test",
)


def _build_alembic_config(*, database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture(scope="session")
def admin_engine() -> Generator[Engine, None, None]:
    engine = create_engine(TEST_DATABASE_URL, future=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def prepared_database(admin_engine: Engine) -> Generator[None, None, None]:
    with admin_engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    command.upgrade(_build_alembic_config(database_url=TEST_DATABASE_URL), "head")
    yield


@pytest.fixture
def test_engine(prepared_database: None, admin_engine: Engine) -> Generator[Engine, None, None]:
    yield admin_engine


@pytest.fixture
def db_connection(test_engine: Engine) -> Generator[Connection, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()
    try:
        yield connection
    finally:
        transaction.rollback()
        connection.close()


@pytest.fixture
def db_session(db_connection: Connection) -> Generator[Session, None, None]:
    testing_session_local = sessionmaker(
        bind=db_connection,
        autoflush=False,
        autocommit=False,
        future=True,
        join_transaction_mode="create_savepoint",
    )
    with testing_session_local() as session:
        yield session
