from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from admin_panel import install_admin
from api.v1.router import router as v1_router
from app_logging import configure_logging
from db.base import Base
from db.engine import engine
from errors import register_error_handlers
from settings import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        return {"status": "ready"}

    admin_session_maker = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    install_admin(app, secret_key=settings.jwt_secret, engine=engine, session_maker=admin_session_maker)
    app.include_router(v1_router)
    register_error_handlers(app)
    return app


app = create_app()
