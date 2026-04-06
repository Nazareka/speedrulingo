from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
import logging
from pathlib import Path

from langsmith import Client, tracing_context
from sqlalchemy.orm import Session
import yaml

from course_builder.config import CourseBuildConfig
from course_builder.runtime.runner import (
    BuildStageRunResult,
    mark_checkpoint_attempt,
    resolve_next_stage_name,
    run_next_build_stage,
)
from settings import get_settings


def build_langsmith_tracing_context(*, build_version: int, section_code: str) -> AbstractContextManager[object]:
    settings = get_settings()
    if not settings.langsmith_tracing:
        return nullcontext()
    api_key = settings.langsmith_api_key
    project_name = settings.langsmith_project
    if api_key is None or project_name is None:
        msg = "LANGSMITH_TRACING is enabled but LangSmith credentials are incomplete in settings"
        raise ValueError(msg)
    client = Client(
        api_key=api_key.get_secret_value(),
        api_url=settings.langsmith_endpoint,
    )
    return tracing_context(
        enabled=True,
        client=client,
        project_name=project_name,
        tags=["course_build", "prefect_runner", f"section:{section_code}"],
        metadata={"build_version": build_version, "section_code": section_code},
    )


def read_declared_section_codes(config_root: Path) -> list[str]:
    payload = yaml.safe_load((config_root / "course.yaml").read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"Config file must contain a mapping at root level: {config_root / 'course.yaml'}"
        raise ValueError(msg)
    section_codes = payload.get("sections")
    if not isinstance(section_codes, list) or not section_codes or not all(isinstance(code, str) for code in section_codes):
        msg = "course.yaml must declare a non-empty string sections list"
        raise ValueError(msg)
    return list(section_codes)


def run_build_stage_with_attempt_log(
    *,
    db: Session,
    config: CourseBuildConfig,
    build_version: int,
    extra_root_handler: logging.Handler | None = None,
) -> BuildStageRunResult:
    next_stage_name = resolve_next_stage_name(
        db=db,
        build_version=build_version,
        section_code=config.current_section_code,
    )
    mark_checkpoint_attempt(
        db,
        build_version=build_version,
        section_code=config.current_section_code,
        stage_name=next_stage_name,
    )
    db.commit()
    root_logger = logging.getLogger()
    if extra_root_handler is not None:
        root_logger.addHandler(extra_root_handler)
    try:
        result = run_next_build_stage(
            db=db,
            config=config,
            build_version=build_version,
        )
    finally:
        if extra_root_handler is not None:
            root_logger.removeHandler(extra_root_handler)
    return result
