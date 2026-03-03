from __future__ import annotations

import argparse
from contextlib import AbstractContextManager, nullcontext
import logging
from pathlib import Path
import sys

from langsmith import Client, tracing_context
import yaml

from app_logging import configure_logging
from course_builder.runtime.runner import (
    default_checkpoint_path,
    is_checkpoint_fully_completed,
    load_config_for_step_runner,
    resolve_next_stage_name,
    run_next_build_stage,
    write_checkpoint_attempt_log,
)
from db.engine import SessionLocal
from settings import get_settings


class _StepRunLogCaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one or all course_build build stages for a section and update its checkpoint."
    )
    parser.add_argument("--config", type=Path, required=True, help="Path to the course_build course config directory.")
    parser.add_argument("--section-code", type=str, required=False, help="Exact section code to build in this step.")
    parser.add_argument(
        "--build-version",
        type=int,
        required=True,
        help="Run number for this logical course build.",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="Optional checkpoint file path. Defaults to build_checkpoints/course_build_<code>_v<version>_build<build_version>.json",
    )
    parser.add_argument(
        "--all-stages",
        action="store_true",
        help="Run all remaining stages for the requested section until completion.",
    )
    parser.add_argument(
        "--all-sections",
        action="store_true",
        help="Run the requested stages for all declared sections in order.",
    )
    return parser


def _build_langsmith_tracing_context(*, build_version: int, section_code: str) -> AbstractContextManager[object]:
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
        tags=["course_build", "build_step_runner", f"section:{section_code}"],
        metadata={"build_version": build_version, "section_code": section_code},
    )


def _read_declared_section_codes(config_root: Path) -> list[str]:
    payload = yaml.safe_load((config_root / "course.yaml").read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"Config file must contain a mapping at root level: {config_root / 'course.yaml'}"
        raise ValueError(msg)
    section_codes = payload.get("sections")
    if not isinstance(section_codes, list) or not section_codes or not all(isinstance(code, str) for code in section_codes):
        msg = "course.yaml must declare a non-empty string sections list"
        raise ValueError(msg)
    return list(section_codes)


def main() -> int:
    configure_logging()
    args = build_parser().parse_args()
    if args.all_sections and args.checkpoint is not None:
        msg = "--checkpoint cannot be used with --all-sections because checkpoints are section-specific"
        raise ValueError(msg)
    if not args.all_sections and args.section_code is None:
        msg = "--section-code is required unless --all-sections is used"
        raise ValueError(msg)

    section_codes = _read_declared_section_codes(args.config) if args.all_sections else [args.section_code]
    if args.section_code is not None and args.all_sections and args.section_code not in section_codes:
        msg = f"Unknown section code {args.section_code!r}; expected one of {section_codes!r}"
        raise ValueError(msg)

    section_run_summaries: list[tuple[str, str, int, str]] = []
    last_result = None

    with SessionLocal() as db:
        for section_code in section_codes:
            config = load_config_for_step_runner(args.config, section_code=section_code)
            checkpoint_path = args.checkpoint or default_checkpoint_path(config=config, build_version=args.build_version)
            completed_stage_names: list[str] = []

            if args.all_sections and is_checkpoint_fully_completed(
                checkpoint_path=checkpoint_path,
                build_version=args.build_version,
                section_code=section_code,
            ):
                continue

            with _build_langsmith_tracing_context(
                build_version=args.build_version,
                section_code=section_code,
            ):
                while True:
                    next_stage_name = resolve_next_stage_name(
                        checkpoint_path=checkpoint_path,
                        build_version=args.build_version,
                        section_code=section_code,
                    )
                    log_capture_handler = _StepRunLogCaptureHandler()
                    log_capture_handler.setFormatter(
                        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
                    )
                    root_logger = logging.getLogger()
                    root_logger.addHandler(log_capture_handler)
                    try:
                        last_result = run_next_build_stage(
                            db=db,
                            config=config,
                            build_version=args.build_version,
                            checkpoint_path=checkpoint_path,
                        )
                    finally:
                        root_logger.removeHandler(log_capture_handler)
                        write_checkpoint_attempt_log(
                            checkpoint_path,
                            build_version=args.build_version,
                            section_code=section_code,
                            stage_name=next_stage_name,
                            log_lines=log_capture_handler.lines,
                        )

                    completed_stage_names.append(last_result.completed_stage_name)
                    if not args.all_stages or last_result.remaining_stage_count == 0:
                        break

            section_run_summaries.append(
                (
                    section_code,
                    last_result.course_version_id,
                    len(completed_stage_names),
                    ",".join(completed_stage_names),
                )
            )

    if last_result is None:
        msg = "No build stages were executed"
        raise ValueError(msg)

    sys.stdout.write(f"build_version={last_result.build_version}\n")
    sys.stdout.write(f"section_code={section_run_summaries[-1][0]}\n")
    sys.stdout.write(f"course_version_id={last_result.course_version_id}\n")
    sys.stdout.write(f"completed_stage={last_result.completed_stage_name}\n")
    sys.stdout.write(f"completed_stage_index={last_result.completed_stage_index}\n")
    sys.stdout.write(f"remaining_stage_count={last_result.remaining_stage_count}\n")
    sys.stdout.write(f"checkpoint_path={last_result.checkpoint_path}\n")
    sys.stdout.write(f"ran_section_count={len(section_run_summaries)}\n")
    sys.stdout.write(
        "ran_sections="
        + ";".join(
            f"{section_code}:{course_version_id}:{ran_stage_count}:{ran_stages}"
            for section_code, course_version_id, ran_stage_count, ran_stages in section_run_summaries
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
