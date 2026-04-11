from __future__ import annotations

from contextlib import AbstractContextManager
import logging
from threading import local
from time import monotonic
from typing import Protocol

from sqlalchemy.orm import Session

from course_builder.build_runs.live_updates import publish_build_run_event
from course_builder.build_runs.queries import get_build_run
from course_builder.build_runs.run_state import append_build_log_event, touch_build_run_heartbeat
from db.engine import SessionLocal

_EMIT_GUARD = local()
_NOISY_LOGGER_PREFIXES = ("dbos", "httpcore", "httpx", "sqlalchemy")


class SessionFactory(Protocol):
    def __call__(self) -> AbstractContextManager[Session]: ...


class BuildRunLogHandler(logging.Handler):
    def __init__(
        self,
        *,
        build_run_id: str,
        section_code: str,
        stage_name: str,
        session_factory: SessionFactory = SessionLocal,
    ) -> None:
        super().__init__(level=logging.INFO)
        self._build_run_id = build_run_id
        self._section_code = section_code
        self._stage_name = stage_name
        self._session_factory = session_factory
        self._last_heartbeat_monotonic = 0.0

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(_EMIT_GUARD, "active", False):
            return
        if record.levelno < logging.INFO:
            return
        if record.name.startswith(_NOISY_LOGGER_PREFIXES):
            return
        message = record.getMessage()
        if not message:
            return
        try:
            _EMIT_GUARD.active = True
            try:
                with self._session_factory() as db:
                    append_build_log_event(
                        db,
                        build_run_id=self._build_run_id,
                        level=record.levelname,
                        message=message,
                        section_code=self._section_code,
                        stage_name=self._stage_name,
                    )
                    now = monotonic()
                    if now - self._last_heartbeat_monotonic >= 1.0:
                        touch_build_run_heartbeat(
                            db,
                            build_run_id=self._build_run_id,
                            current_stage_name=self._stage_name,
                        )
                        self._last_heartbeat_monotonic = now
                    db.commit()
                    build_run = get_build_run(db, build_run_id=self._build_run_id)
                    publish_build_run_event(
                        event_type="build_run.log_appended",
                        build_run_id=self._build_run_id,
                        parent_build_run_id=build_run.parent_build_run_id if build_run is not None else None,
                    )
            except Exception:  # noqa: BLE001  # logging handlers must never break the build path
                self.handleError(record)
        finally:
            _EMIT_GUARD.active = False


class FanoutHandler(logging.Handler):
    def __init__(self, *handlers: logging.Handler) -> None:
        super().__init__()
        self._handlers = handlers

    def emit(self, record: logging.LogRecord) -> None:
        for handler in self._handlers:
            try:
                handler.handle(record)
            except Exception:  # noqa: BLE001  # one handler failure must not block later handlers
                handler.handleError(record)
