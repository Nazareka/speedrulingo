from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, field_serializer

from domain.content.models import CourseBuildLogEvent, CourseBuildRun, CourseBuildStageRun


def _format_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def _prettify_log_message(
    message: str,
    *,
    section_code: str | None = None,
    stage_name: str | None = None,
) -> str:
    replacements = {
        "section_code=": "",
        "stage_name=": "",
        "stage_index=": "stage ",
        "remaining_stages=": "remaining ",
        "course_version_id=": "course version ",
        "build_version=": "build ",
        "config=": "",
        "section=": "",
    }
    pretty_message = message
    for source, target in replacements.items():
        pretty_message = pretty_message.replace(source, target)
    pretty_message = " ".join(pretty_message.split()).strip()

    if stage_name is not None:
        if pretty_message in {f"Running {stage_name}", f"Running stage {stage_name}"}:
            return "Running"
        if pretty_message in {f"Completed {stage_name}", f"Completed stage {stage_name}"}:
            return "Completed"

    if section_code is not None:
        pretty_message = pretty_message.replace(f"for section {section_code}", "")
        pretty_message = pretty_message.replace(f" section {section_code}", "")
        pretty_message = pretty_message.replace(f" {section_code}", "")

    if stage_name is not None:
        pretty_message = pretty_message.replace(f" stage_name={stage_name}", "")

    pretty_message = pretty_message.replace("course version course version", "course version")
    return " ".join(pretty_message.split()).strip()


class BuildRunView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    parent_build_run_id: str | None = None
    workflow_id: str | None = None
    build_version: int
    config_path: str
    scope_kind: str
    section_code: str | None = None
    status: str
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    requested_by: str | None = None
    course_version_id: str | None = None
    all_stages: bool
    completed_stage_count: int
    total_stage_count: int
    current_stage_name: str | None = None
    last_heartbeat_at: datetime | None = None

    @field_serializer(
        "created_at",
        "started_at",
        "finished_at",
        "last_heartbeat_at",
        when_used="json",
    )
    @staticmethod
    def serialize_dt(value: datetime | None) -> str | None:
        return _format_timestamp(value)


class StageRunView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    section_code: str
    stage_name: str
    stage_index: int
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None

    @field_serializer("started_at", "finished_at", when_used="json")
    @staticmethod
    def serialize_dt(value: datetime | None) -> str | None:
        return _format_timestamp(value)


class LogEventView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sequence_number: int
    section_code: str | None = None
    stage_name: str | None = None
    level: str
    message: str
    created_at: datetime | None = None

    @field_serializer("created_at", when_used="json")
    @staticmethod
    def serialize_dt(value: datetime | None) -> str | None:
        return _format_timestamp(value)


def serialize_build_run(build_run: CourseBuildRun) -> dict[str, object]:
    return BuildRunView.model_validate(build_run).model_dump(mode="json")


def serialize_stage_run(stage_run: CourseBuildStageRun) -> dict[str, object]:
    return StageRunView.model_validate(stage_run).model_dump(mode="json")


def serialize_log_event(event: CourseBuildLogEvent) -> dict[str, object]:
    return LogEventView.model_validate(event).model_dump(mode="json")


def format_serialized_log_event_line(event: dict[str, object]) -> str:
    timestamp_value = event.get("created_at")
    timestamp = timestamp_value if isinstance(timestamp_value, str) and timestamp_value else "unknown-time"
    level_value = event.get("level")
    level = level_value if isinstance(level_value, str) and level_value else "INFO"
    scope_parts = [
        part
        for part in [event.get("section_code"), event.get("stage_name")]
        if isinstance(part, str) and part
    ]
    scope = f" [{' / '.join(scope_parts)}]" if scope_parts else ""
    message_value = event.get("message")
    message = message_value if isinstance(message_value, str) else ""
    return f"{timestamp} {level}{scope} {message}"


def build_pretty_log_tree_rows(events: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    current_section: str | None = None
    current_stage_scope: str | None = None
    previous_timestamp: str | None = None

    for event in events:
        section_code_value = event.get("section_code")
        stage_name_value = event.get("stage_name")
        message_value = event.get("message")
        created_at_value = event.get("created_at")
        level_value = event.get("level")

        section_code = section_code_value if isinstance(section_code_value, str) and section_code_value else None
        stage_name = stage_name_value if isinstance(stage_name_value, str) and stage_name_value else None
        message = message_value if isinstance(message_value, str) else ""
        created_at = created_at_value if isinstance(created_at_value, str) and created_at_value else ""
        level = level_value if isinstance(level_value, str) and level_value else "INFO"

        if section_code is not None and section_code != current_section:
            rows.append(
                {
                    "kind": "section",
                    "label": section_code,
                }
            )
            current_section = section_code
            current_stage_scope = None

        stage_scope = stage_name if stage_name is not None else None
        if stage_scope is not None and stage_scope != current_stage_scope:
            rows.append(
                {
                    "kind": "stage",
                    "label": stage_scope,
                }
            )
            current_stage_scope = stage_scope

        pretty_message = _prettify_log_message(
            message,
            section_code=section_code,
            stage_name=stage_name,
        )
        if pretty_message == "":
            continue

        rows.append(
            {
                "kind": "event",
                "message": pretty_message,
                "timestamp": created_at,
                "show_timestamp": created_at != previous_timestamp,
                "level": level,
            }
        )
        previous_timestamp = created_at

    return rows
