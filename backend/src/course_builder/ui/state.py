from __future__ import annotations

from pathlib import Path
from typing import Any

from dbos import DBOS
from pydantic import Field
import reflex as rx

from app_logging import configure_logging
from course_builder.runtime.dbos import (
    build_all_sections_workflow,
    build_section_workflow,
    cancel_dbos_workflow_async,
    generate_section_sentence_audio_workflow,
    generate_section_word_audio_workflow,
    launch_dbos,
)
from course_builder.runtime.orchestration import CourseBuildOrchestrator, read_declared_section_codes
from course_builder.runtime.queries import (
    get_build_run,
    get_build_run_by_workflow_id,
    list_build_runs,
    list_child_section_build_runs,
    list_log_events,
    list_log_events_for_build_run_ids,
    list_stage_runs,
)
from course_builder.runtime.workflow_models import BuildRequest, build_request
from course_builder.ui.models import (
    build_pretty_log_tree_rows,
    format_serialized_log_event_line,
    serialize_build_run,
    serialize_log_event,
    serialize_stage_run,
)
from db.engine import SessionLocal

_RUNTIME_READY = False


def _ensure_ui_runtime() -> None:
    global _RUNTIME_READY
    if _RUNTIME_READY:
        return
    configure_logging()
    launch_dbos()
    _RUNTIME_READY = True


def _list_len(value: object) -> int:
    # Reflex may expose FieldInfo placeholders during compile-time state
    # introspection, so plain len(self.some_list_field) is not always safe here.
    if isinstance(value, list):
        return len(value)
    return 0


def _format_log_line(event: dict[str, object]) -> str:
    return format_serialized_log_event_line(event)


def _dict_value(mapping: object, key: str) -> object | None:
    # Reflex may expose FieldInfo placeholders during compile-time state
    # introspection, so computed vars cannot assume dict-like state fields are
    # real mappings yet.
    if isinstance(mapping, dict):
        return mapping.get(key)
    return None


class CourseBuilderUIState(rx.State):
    config_path: str = "config/en-ja-v1"
    build_version_input: str = ""
    section_code: str = "PRE_A1"
    all_stages: bool = True
    all_sections: bool = False
    available_section_codes: list[str] = Field(default_factory=list)

    build_runs: list[dict[str, object]] = Field(default_factory=list)
    selected_run_id: str = ""
    selected_run: dict[str, object] = Field(default_factory=dict)
    child_section_runs: list[dict[str, object]] = Field(default_factory=list)
    stage_runs: list[dict[str, object]] = Field(default_factory=list)
    log_events: list[dict[str, object]] = Field(default_factory=list)
    pretty_log_rows: list[dict[str, object]] = Field(default_factory=list)
    log_text: str = ""
    log_view_mode: str = "pretty"

    launched_workflow_id: str = ""
    launch_message: str = ""
    error_message: str = ""
    cancel_message: str = ""
    sentence_audio_message: str = ""
    word_audio_message: str = ""

    @rx.var
    def build_runs_count(self) -> int:
        return _list_len(self.build_runs)

    @rx.var
    def child_section_runs_count(self) -> int:
        return _list_len(self.child_section_runs)

    @rx.var
    def log_events_count(self) -> int:
        return _list_len(self.log_events)

    @rx.var
    def has_selected_run(self) -> bool:
        return bool(self.selected_run)

    @rx.var
    def can_cancel_selected_run(self) -> bool:
        if not isinstance(self.selected_run, dict) or not self.selected_run:
            return False
        workflow_id = _dict_value(self.selected_run, "workflow_id")
        status = _dict_value(self.selected_run, "status")
        return isinstance(workflow_id, str) and bool(workflow_id) and status in {"queued", "running"}

    @rx.var
    def can_generate_selected_run_audio(self) -> bool:
        if not isinstance(self.selected_run, dict) or not self.selected_run:
            return False
        return (
            _dict_value(self.selected_run, "scope_kind") == "section"
            and _dict_value(self.selected_run, "status") == "completed"
            and isinstance(_dict_value(self.selected_run, "section_code"), str)
            and bool(_dict_value(self.selected_run, "section_code"))
        )

    @rx.var
    def can_generate_selected_run_word_audio(self) -> bool:
        return self.can_generate_selected_run_audio

    def set_config_path_value(self, value: str) -> None:
        self.config_path = value
        self._reload_available_section_codes()

    def set_build_version_input_value(self, value: str) -> None:
        self.build_version_input = value

    def set_section_code_value(self, value: str) -> None:
        self.section_code = value

    def set_all_stages_value(self, checked: bool) -> None:
        self.all_stages = checked

    def set_log_view_mode(self, mode: str) -> None:
        if mode in {"pretty", "raw"}:
            self.log_view_mode = mode

    def load_dashboard(self) -> Any:
        _ensure_ui_runtime()
        self._reload_available_section_codes()
        self._reload_dashboard_data()
        return

    def refresh_now(self) -> None:
        _ensure_ui_runtime()
        self._reload_dashboard_data()

    def select_run(self, build_run_id: str) -> None:
        self.selected_run_id = build_run_id
        self._reload_dashboard_data()

    def refresh_for_live_update(self) -> None:
        self._reload_dashboard_data()

    def toggle_all_sections(self, checked: bool) -> None:
        self.all_sections = checked
        if checked:
            self.section_code = ""
        elif self.available_section_codes and not self.section_code:
            self.section_code = self.available_section_codes[0]

    def start_build(self) -> Any:
        _ensure_ui_runtime()
        self.error_message = ""
        self.launch_message = ""
        self.cancel_message = ""
        self.sentence_audio_message = ""
        self.word_audio_message = ""
        try:
            request = self._build_request_from_form()
        except ValueError as exc:
            self.error_message = str(exc)
            return

        if request.all_sections:
            handle = DBOS.start_workflow(
                build_all_sections_workflow,
                str(request.config),
                request.build_version,
                request.all_stages,
            )
        else:
            handle = DBOS.start_workflow(
                build_section_workflow,  # type: ignore[arg-type]  # DBOS.start_workflow typing does not model overloads well.
                str(request.config),
                request.build_version,
                request.section_code or "",
                request.all_stages,
            )
        self.launched_workflow_id = handle.get_workflow_id()
        self.launch_message = f"Started workflow {self.launched_workflow_id}"
        self._reload_dashboard_data()
        return

    async def cancel_selected_run(self) -> None:
        _ensure_ui_runtime()
        self.error_message = ""
        self.launch_message = ""
        self.cancel_message = ""
        self.sentence_audio_message = ""
        self.word_audio_message = ""
        if not self.selected_run:
            self.error_message = "No build run selected"
            return
        build_run_id = self.selected_run.get("id")
        workflow_id = self.selected_run.get("workflow_id")
        if not isinstance(build_run_id, str) or not build_run_id:
            self.error_message = "Selected build run is missing its identifier"
            return
        if not isinstance(workflow_id, str) or not workflow_id:
            self.error_message = "Selected build run cannot be cancelled"
            return
        CourseBuildOrchestrator.cancel_build_run(build_run_id=build_run_id)
        self._reload_dashboard_data()
        await cancel_dbos_workflow_async(workflow_id=workflow_id)
        self.cancel_message = f"Cancelled workflow {workflow_id}"
        self._reload_dashboard_data()

    def start_sentence_audio_generation(self) -> None:
        _ensure_ui_runtime()
        self.error_message = ""
        self.launch_message = ""
        self.cancel_message = ""
        self.sentence_audio_message = ""
        self.word_audio_message = ""
        if not self.can_generate_selected_run_audio:
            self.error_message = "Sentence audio generation requires a completed section run"
            return
        config_path = self.selected_run.get("config_path")
        build_version = self.selected_run.get("build_version")
        section_code = self.selected_run.get("section_code")
        if not isinstance(config_path, str) or not isinstance(build_version, int) or not isinstance(section_code, str):
            self.error_message = "Selected run is missing build context for sentence audio generation"
            return
        handle = DBOS.start_workflow(
            generate_section_sentence_audio_workflow,
            config_path,
            build_version,
            section_code,
        )
        self.launched_workflow_id = handle.get_workflow_id()
        self.sentence_audio_message = f"Started sentence audio workflow {self.launched_workflow_id}"
        self._reload_dashboard_data()

    def start_word_audio_generation(self) -> None:
        _ensure_ui_runtime()
        self.error_message = ""
        self.launch_message = ""
        self.cancel_message = ""
        self.sentence_audio_message = ""
        self.word_audio_message = ""
        if not self.can_generate_selected_run_word_audio:
            self.error_message = "Word audio generation requires a completed section run"
            return
        config_path = self.selected_run.get("config_path")
        build_version = self.selected_run.get("build_version")
        section_code = self.selected_run.get("section_code")
        if not isinstance(config_path, str) or not isinstance(build_version, int) or not isinstance(section_code, str):
            self.error_message = "Selected run is missing build context for word audio generation"
            return
        handle = DBOS.start_workflow(
            generate_section_word_audio_workflow,
            config_path,
            build_version,
            section_code,
        )
        self.launched_workflow_id = handle.get_workflow_id()
        self.word_audio_message = f"Started word audio workflow {self.launched_workflow_id}"
        self._reload_dashboard_data()

    def _build_request_from_form(self) -> BuildRequest:
        build_version_raw = self.build_version_input.strip()
        if not build_version_raw:
            msg = "Build version is required"
            raise ValueError(msg)
        try:
            build_version = int(build_version_raw)
        except ValueError as exc:
            msg = "Build version must be an integer"
            raise ValueError(msg) from exc
        return build_request(
            config=Path(self.config_path.strip()),
            build_version=build_version,
            section_code=None if self.all_sections else self.section_code.strip() or None,
            all_stages=self.all_stages,
            all_sections=self.all_sections,
        )

    def _reload_available_section_codes(self) -> None:
        config_path = self.config_path.strip()
        if not config_path:
            self.available_section_codes = []
            self.section_code = ""
            return
        try:
            section_codes = read_declared_section_codes(Path(config_path))
        except (FileNotFoundError, ValueError, TypeError):
            self.available_section_codes = []
            self.section_code = ""
            return
        self.available_section_codes = section_codes
        if self.all_sections:
            self.section_code = ""
            return
        if self.section_code not in section_codes:
            self.section_code = section_codes[0]

    def _reload_dashboard_data(self) -> None:
        with SessionLocal() as db:
            runs = list_build_runs(db, limit=100)
            self.build_runs = [serialize_build_run(build_run) for build_run in runs]

            if self.launched_workflow_id:
                workflow_run = get_build_run_by_workflow_id(db, workflow_id=self.launched_workflow_id)
                if workflow_run is not None:
                    self.selected_run_id = workflow_run.id
                    self.launched_workflow_id = ""

            if not self.selected_run_id and runs:
                self.selected_run_id = runs[0].id

            selected_run = get_build_run(db, build_run_id=self.selected_run_id) if self.selected_run_id else None
            if selected_run is None:
                self.selected_run_id = ""
                self.selected_run = {}
                self.child_section_runs = []
                self.stage_runs = []
                self.log_events = []
                self.pretty_log_rows = []
                self.log_text = ""
                self._sync_live_subscription()
                return

            self.selected_run = serialize_build_run(selected_run)
            child_runs = list_child_section_build_runs(db, parent_build_run_id=selected_run.id)
            self.child_section_runs = [serialize_build_run(build_run) for build_run in child_runs]
            self.stage_runs = [serialize_stage_run(stage_run) for stage_run in list_stage_runs(db, build_run_id=selected_run.id)]
            if selected_run.scope_kind == "all_sections":
                log_events = list_log_events_for_build_run_ids(
                    db,
                    build_run_ids=[selected_run.id, *[build_run.id for build_run in child_runs]],
                )
            else:
                log_events = list_log_events(db, build_run_id=selected_run.id)
            self.log_events = [serialize_log_event(event) for event in log_events]
            self.pretty_log_rows = build_pretty_log_tree_rows(self.log_events)
            self.log_text = "\n".join(_format_log_line(event) for event in self.log_events)
            self._sync_live_subscription()

    def _sync_live_subscription(self) -> None:
        from course_builder.ui.live_updates import BUILD_RUN_SUBSCRIPTIONS

        BUILD_RUN_SUBSCRIPTIONS.register(
            client_token=self.router.session.client_token,
            build_run_id=self.selected_run_id or None,
        )
