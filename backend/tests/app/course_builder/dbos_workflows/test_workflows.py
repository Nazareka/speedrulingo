from __future__ import annotations

from typing import Any

import pytest

from course_builder.build_runs.models import (
    AllSectionsBuildSummary,
    BuildRequest,
    SectionBuildSummary,
)
from course_builder.engine.runner import BuildStageRunResult
from course_builder.workflows.audio import (
    generate_kana_audio_workflow,
    generate_section_sentence_audio_workflow,
    generate_section_word_audio_workflow,
)
from course_builder.workflows.course_build import build_all_sections_workflow, build_section_workflow


def test_build_section_workflow_uses_dbos_workflow_id_and_stage_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {}

    class FakeDBOS:
        workflow_id = "workflow-123"

    def fake_run_one_stage_step(
        *,
        config: str,
        build_version: int,
        section_code: str,
        build_run_id: str | None = None,
        stage_name: str | None = None,
    ) -> BuildStageRunResult:
        calls["stage_step"] = {
            "config": config,
            "build_version": build_version,
            "section_code": section_code,
            "build_run_id": build_run_id,
            "stage_name": stage_name,
        }
        return BuildStageRunResult(
            build_version=build_version,
            course_version_id="course-version-1",
            completed_stage_name="create_course_build",
            completed_stage_index=0,
            remaining_stage_count=7,
        )

    def fake_run_section_until_done(
        self: object,
        request: BuildRequest,
        *,
        stage_runner: Any,
        build_run_id: str | None = None,
        resume_from_build_run_id: str | None = None,
        parent_build_run_id: str | None = None,
        workflow_id: str | None = None,
    ) -> SectionBuildSummary:
        assert request.section_code is not None
        _ = resume_from_build_run_id
        calls["request"] = request
        calls["build_run_id"] = build_run_id
        calls["parent_build_run_id"] = parent_build_run_id
        calls["workflow_id"] = workflow_id
        calls["stage_result"] = stage_runner(
            config_path=request.config,
            build_version=request.build_version,
            section_code=request.section_code,
        )
        return {
            "build_run_id": "run-1",
            "build_version": request.build_version,
            "section_code": request.section_code,
            "course_version_id": "course-version-1",
            "completed_stage": "create_course_build",
            "completed_stage_index": 0,
            "remaining_stage_count": 7,
            "ran_stage_count": 1,
            "ran_stages": ["create_course_build"],
            "was_noop": False,
        }

    monkeypatch.setattr("course_builder.workflows.course_build.DBOS", FakeDBOS)
    monkeypatch.setattr("course_builder.workflows.course_build.run_one_stage_step", fake_run_one_stage_step)
    monkeypatch.setattr(
        "course_builder.workflows.course_build.CourseBuildOrchestrator.run_section_until_done",
        fake_run_section_until_done,
    )

    summary = build_section_workflow.__wrapped__(  # type: ignore[attr-defined]  # DBOS preserves the wrapped function.
        config="config/en-ja-v1",
        build_version=9,
        section_code="PRE_A1",
        all_stages=True,
        resume_from_build_run_id=None,
    )

    assert summary["section_code"] == "PRE_A1"
    assert calls["workflow_id"] == "workflow-123"
    assert calls["build_run_id"] is None
    assert calls["parent_build_run_id"] is None
    assert calls["stage_step"] == {
        "config": "config/en-ja-v1",
        "build_version": 9,
        "section_code": "PRE_A1",
        "build_run_id": None,
        "stage_name": None,
    }
    assert calls["stage_result"].completed_stage_name == "create_course_build"


def test_build_section_workflow_passes_resume_source_build_run_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {}

    class FakeDBOS:
        workflow_id = "workflow-789"

    def fake_run_section_until_done(
        self: object,
        request: BuildRequest,
        *,
        stage_runner: Any,
        build_run_id: str | None = None,
        resume_from_build_run_id: str | None = None,
        parent_build_run_id: str | None = None,
        workflow_id: str | None = None,
    ) -> SectionBuildSummary:
        _ = stage_runner
        _ = parent_build_run_id
        calls["build_run_id"] = build_run_id
        calls["resume_from_build_run_id"] = resume_from_build_run_id
        calls["workflow_id"] = workflow_id
        return {
            "build_run_id": "run-2",
            "build_version": request.build_version,
            "section_code": request.section_code or "PRE_A1",
            "course_version_id": "course-version-1",
            "completed_stage": "bootstrap_catalog",
            "completed_stage_index": 1,
            "remaining_stage_count": 6,
            "ran_stage_count": 1,
            "ran_stages": ["bootstrap_catalog"],
            "was_noop": False,
        }

    monkeypatch.setattr("course_builder.workflows.course_build.DBOS", FakeDBOS)
    monkeypatch.setattr(
        "course_builder.workflows.course_build.CourseBuildOrchestrator.run_section_until_done",
        fake_run_section_until_done,
    )

    summary = build_section_workflow.__wrapped__(  # type: ignore[attr-defined]  # DBOS preserves the wrapped function.
        config="config/en-ja-v1",
        build_version=9,
        section_code="PRE_A1",
        all_stages=True,
        resume_from_build_run_id="build-run-42",
    )

    assert summary["build_run_id"] == "run-2"
    assert calls["build_run_id"] is None
    assert calls["resume_from_build_run_id"] == "build-run-42"
    assert calls["workflow_id"] == "workflow-789"


def test_build_all_sections_workflow_passes_section_runner_and_workflow_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {}

    class FakeDBOS:
        workflow_id = "workflow-456"

    def fake_run_section_until_done(
        self: object,
        request: BuildRequest,
        *,
        stage_runner: Any,
        build_run_id: str | None = None,
        resume_from_build_run_id: str | None = None,
        parent_build_run_id: str | None = None,
        workflow_id: str | None = None,
    ) -> SectionBuildSummary:
        assert request.section_code is not None
        _ = resume_from_build_run_id
        calls["section_request"] = request
        calls["section_build_run_id"] = build_run_id
        calls["section_parent_build_run_id"] = parent_build_run_id
        calls["section_workflow_id"] = workflow_id
        return {
            "build_run_id": build_run_id or "section-run-1",
            "build_version": request.build_version,
            "section_code": request.section_code,
            "course_version_id": "course-version-1",
            "completed_stage": "bootstrap_catalog",
            "completed_stage_index": 1,
            "remaining_stage_count": 6,
            "ran_stage_count": 1,
            "ran_stages": ["bootstrap_catalog"],
            "was_noop": False,
        }

    def fake_run_all_sections_until_done(
        self: object,
        request: BuildRequest,
        *,
        section_runner: Any,
        workflow_id: str | None = None,
    ) -> AllSectionsBuildSummary:
        calls["all_sections_request"] = request
        calls["all_sections_workflow_id"] = workflow_id
        section_summary = section_runner(
            request.model_copy(update={"section_code": "PRE_A1", "all_sections": False}),
            parent_build_run_id="build-run-parent",
        )
        calls["section_summary"] = section_summary
        return {
            "build_run_id": "build-run-parent",
            "build_version": request.build_version,
            "ran_section_count": 1,
            "ran_sections": [section_summary],
            "last_section": section_summary,
            "was_noop": False,
        }

    monkeypatch.setattr("course_builder.workflows.course_build.DBOS", FakeDBOS)
    monkeypatch.setattr(
        "course_builder.workflows.course_build.CourseBuildOrchestrator.run_section_until_done",
        fake_run_section_until_done,
    )
    monkeypatch.setattr(
        "course_builder.workflows.course_build.CourseBuildOrchestrator.run_all_sections_until_done",
        fake_run_all_sections_until_done,
    )

    summary = build_all_sections_workflow.__wrapped__(  # type: ignore[attr-defined]  # DBOS preserves the wrapped function.
        config="config/en-ja-v1",
        build_version=12,
        all_stages=True,
    )

    assert summary["build_run_id"] == "build-run-parent"
    assert calls["all_sections_workflow_id"] == "workflow-456"
    assert calls["section_build_run_id"] is None
    assert calls["section_parent_build_run_id"] == "build-run-parent"
    assert calls["section_workflow_id"] is None
    assert calls["section_summary"]["section_code"] == "PRE_A1"


def test_generate_section_sentence_audio_workflow_uses_completed_section_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {"progress": [], "logs": []}

    class FakeDBOS:
        workflow_id = "audio-workflow-123"

    class FakeSession:
        def commit(self) -> None:
            calls.setdefault("commit_count", 0)
            calls["commit_count"] += 1

        def rollback(self) -> None:
            calls["rolled_back"] = True

    class FakeSessionLocal:
        def __enter__(self) -> FakeSession:
            return FakeSession()

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

    class FakeSectionRun:
        id = "section-run-42"
        course_version_id = "course-version-42"

    class FakeBuildRun:
        id = "audio-run-1"
        parent_build_run_id = None
        course_version_id: str | None = None

    def fake_create_build_run(
        db: object,
        *,
        request: BuildRequest,
        scope_kind: str,
        total_stage_count: int,
        parent_build_run_id: str | None = None,
        workflow_id: str | None = None,
        requested_by: str | None = None,
    ) -> FakeBuildRun:
        calls["create_build_run"] = {
            "section_code": request.section_code,
            "scope_kind": scope_kind,
            "total_stage_count": total_stage_count,
            "workflow_id": workflow_id,
        }
        return FakeBuildRun()

    def fake_generate_sentence_audio_step(*, sentence_id: str) -> dict[str, object]:
        calls.setdefault("sentence_ids", []).append(sentence_id)
        return {"asset_id": f"asset-{sentence_id}", "reused": sentence_id == "sentence-1"}

    def fake_log_run_message(
        *,
        build_run_id: str,
        level: str,
        message: str,
        section_code: str | None = None,
        stage_name: str | None = None,
    ) -> None:
        calls["logs"].append((build_run_id, level, message, section_code, stage_name))

    def fake_sync_run_progress(
        *,
        build_run_id: str,
        completed_stage_count: int,
        current_stage_name: str | None,
        course_version_id: str | None = None,
    ) -> None:
        calls["progress"].append((completed_stage_count, current_stage_name, course_version_id))

    monkeypatch.setattr("course_builder.workflows.audio.DBOS", FakeDBOS)
    monkeypatch.setattr("course_builder.workflows.audio.SessionLocal", FakeSessionLocal)
    monkeypatch.setattr(
        "course_builder.workflows.audio.get_settings",
        lambda: type("Settings", (), {"elevenlabs_voice_id": "voice-123"})(),
    )
    monkeypatch.setattr(
        "course_builder.workflows.audio.get_latest_completed_section_build_run",
        lambda db, build_version, config_path, section_code: FakeSectionRun(),
    )
    monkeypatch.setattr(
        "course_builder.workflows.audio.list_section_sentence_ids",
        lambda db, course_version_id, section_code: ["sentence-1", "sentence-2"],
    )
    monkeypatch.setattr("course_builder.workflows.audio.create_build_run", fake_create_build_run)
    monkeypatch.setattr("course_builder.workflows.audio.publish_build_run_event", lambda **kwargs: None)
    monkeypatch.setattr("course_builder.workflows.audio.generate_sentence_audio_step", fake_generate_sentence_audio_step)
    monkeypatch.setattr(
        "course_builder.workflows.audio.BuildRunTracking.log_message",
        staticmethod(fake_log_run_message),
    )
    monkeypatch.setattr(
        "course_builder.workflows.audio.BuildRunTracking.sync_progress",
        staticmethod(fake_sync_run_progress),
    )
    monkeypatch.setattr(
        "course_builder.workflows.audio.BuildRunTracking.mark_completed",
        staticmethod(lambda **kwargs: calls.setdefault("completed", kwargs)),
    )
    monkeypatch.setattr(
        "course_builder.workflows.audio.BuildRunTracking.mark_failed",
        staticmethod(lambda **kwargs: calls.setdefault("failed", kwargs)),
    )
    monkeypatch.setattr(
        "course_builder.workflows.audio.BuildRunTracking.is_cancelled",
        staticmethod(lambda **kwargs: False),
    )

    summary = generate_section_sentence_audio_workflow.__wrapped__(  # type: ignore[attr-defined]  # DBOS preserves the wrapped function.
        config="config/en-ja-v1",
        build_version=22,
        section_code="PRE_A1",
    )

    assert summary == {
        "build_run_id": "audio-run-1",
        "source_section_build_run_id": "section-run-42",
        "build_version": 22,
        "section_code": "PRE_A1",
        "total_sentence_count": 2,
        "generated_sentence_count": 1,
        "reused_sentence_count": 1,
        "failed_sentence_count": 0,
    }
    assert calls["create_build_run"] == {
        "section_code": "PRE_A1",
        "scope_kind": "section_audio",
        "total_stage_count": 2,
        "workflow_id": "audio-workflow-123",
    }
    assert calls["sentence_ids"] == ["sentence-1", "sentence-2"]
    assert calls["completed"]["build_run_id"] == "audio-run-1"
    assert calls["completed"]["completed_stage_count"] == 2


def test_generate_section_word_audio_workflow_uses_completed_section_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {"progress": [], "logs": []}

    class FakeDBOS:
        workflow_id = "word-audio-workflow-123"

    class FakeSession:
        def commit(self) -> None:
            calls.setdefault("commit_count", 0)
            calls["commit_count"] += 1

        def rollback(self) -> None:
            calls["rolled_back"] = True

    class FakeSessionLocal:
        def __enter__(self) -> FakeSession:
            return FakeSession()

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

    class FakeSectionRun:
        id = "section-run-99"
        course_version_id = "course-version-99"

    class FakeBuildRun:
        id = "word-audio-run-1"
        parent_build_run_id = None
        course_version_id: str | None = None

    def fake_create_build_run(
        db: object,
        *,
        request: BuildRequest,
        scope_kind: str,
        total_stage_count: int,
        parent_build_run_id: str | None = None,
        workflow_id: str | None = None,
        requested_by: str | None = None,
    ) -> FakeBuildRun:
        calls["create_build_run"] = {
            "section_code": request.section_code,
            "scope_kind": scope_kind,
            "total_stage_count": total_stage_count,
            "workflow_id": workflow_id,
        }
        return FakeBuildRun()

    def fake_generate_word_audio_step(*, word_id: str) -> dict[str, object]:
        calls.setdefault("word_ids", []).append(word_id)
        return {"asset_id": f"asset-{word_id}", "reused": word_id == "word-1"}

    def fake_log_run_message(
        *,
        build_run_id: str,
        level: str,
        message: str,
        section_code: str | None = None,
        stage_name: str | None = None,
    ) -> None:
        calls["logs"].append((build_run_id, level, message, section_code, stage_name))

    def fake_sync_run_progress(
        *,
        build_run_id: str,
        completed_stage_count: int,
        current_stage_name: str | None,
        course_version_id: str | None = None,
    ) -> None:
        calls["progress"].append((completed_stage_count, current_stage_name, course_version_id))

    monkeypatch.setattr("course_builder.workflows.audio.DBOS", FakeDBOS)
    monkeypatch.setattr("course_builder.workflows.audio.SessionLocal", FakeSessionLocal)
    monkeypatch.setattr(
        "course_builder.workflows.audio.get_settings",
        lambda: type("Settings", (), {"elevenlabs_voice_id": "voice-123"})(),
    )
    monkeypatch.setattr(
        "course_builder.workflows.audio.get_latest_completed_section_build_run",
        lambda db, build_version, config_path, section_code: FakeSectionRun(),
    )
    monkeypatch.setattr(
        "course_builder.workflows.audio.list_section_word_ids",
        lambda db, course_version_id, section_code: ["word-1", "word-2"],
    )
    monkeypatch.setattr("course_builder.workflows.audio.create_build_run", fake_create_build_run)
    monkeypatch.setattr("course_builder.workflows.audio.publish_build_run_event", lambda **kwargs: None)
    monkeypatch.setattr("course_builder.workflows.audio.generate_word_audio_step", fake_generate_word_audio_step)
    monkeypatch.setattr(
        "course_builder.workflows.audio.BuildRunTracking.log_message",
        staticmethod(fake_log_run_message),
    )
    monkeypatch.setattr(
        "course_builder.workflows.audio.BuildRunTracking.sync_progress",
        staticmethod(fake_sync_run_progress),
    )
    monkeypatch.setattr(
        "course_builder.workflows.audio.BuildRunTracking.mark_completed",
        staticmethod(lambda **kwargs: calls.setdefault("completed", kwargs)),
    )
    monkeypatch.setattr(
        "course_builder.workflows.audio.BuildRunTracking.mark_failed",
        staticmethod(lambda **kwargs: calls.setdefault("failed", kwargs)),
    )
    monkeypatch.setattr(
        "course_builder.workflows.audio.BuildRunTracking.is_cancelled",
        staticmethod(lambda **kwargs: False),
    )

    summary = generate_section_word_audio_workflow.__wrapped__(  # type: ignore[attr-defined]  # DBOS preserves the wrapped function.
        config="config/en-ja-v1",
        build_version=23,
        section_code="PRE_A1",
    )

    assert summary == {
        "build_run_id": "word-audio-run-1",
        "source_section_build_run_id": "section-run-99",
        "build_version": 23,
        "section_code": "PRE_A1",
        "total_word_count": 2,
        "generated_word_count": 1,
        "reused_word_count": 1,
        "failed_word_count": 0,
    }
    assert calls["create_build_run"] == {
        "section_code": "PRE_A1",
        "scope_kind": "section_word_audio",
        "total_stage_count": 2,
        "workflow_id": "word-audio-workflow-123",
    }
    assert calls["word_ids"] == ["word-1", "word-2"]
    assert calls["completed"]["build_run_id"] == "word-audio-run-1"
    assert calls["completed"]["completed_stage_count"] == 2


def test_generate_kana_audio_workflow_uses_script_scoped_character_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {"progress": [], "logs": []}

    class FakeDBOS:
        workflow_id = "kana-audio-workflow-123"

    class FakeSession:
        def commit(self) -> None:
            calls.setdefault("commit_count", 0)
            calls["commit_count"] += 1

        def rollback(self) -> None:
            calls["rolled_back"] = True

    class FakeSessionLocal:
        def __enter__(self) -> FakeSession:
            return FakeSession()

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

    class FakeBuildRun:
        id = "kana-audio-run-1"
        parent_build_run_id = None

    def fake_create_build_run(
        db: object,
        *,
        request: BuildRequest,
        scope_kind: str,
        total_stage_count: int,
        parent_build_run_id: str | None = None,
        workflow_id: str | None = None,
        requested_by: str | None = None,
    ) -> FakeBuildRun:
        calls["create_build_run"] = {
            "section_code": request.section_code,
            "scope_kind": scope_kind,
            "total_stage_count": total_stage_count,
            "workflow_id": workflow_id,
        }
        return FakeBuildRun()

    def fake_generate_kana_audio_step(*, character_id: str) -> dict[str, object]:
        calls.setdefault("character_ids", []).append(character_id)
        return {"asset_id": f"asset-{character_id}", "reused": character_id == "char-1"}

    def fake_log_run_message(
        *,
        build_run_id: str,
        level: str,
        message: str,
        section_code: str | None = None,
        stage_name: str | None = None,
    ) -> None:
        calls["logs"].append((build_run_id, level, message, section_code, stage_name))

    def fake_sync_run_progress(
        *,
        build_run_id: str,
        completed_stage_count: int,
        current_stage_name: str | None,
        course_version_id: str | None = None,
    ) -> None:
        calls["progress"].append((completed_stage_count, current_stage_name, course_version_id))

    monkeypatch.setattr("course_builder.workflows.audio.DBOS", FakeDBOS)
    monkeypatch.setattr("course_builder.workflows.audio.SessionLocal", FakeSessionLocal)
    monkeypatch.setattr(
        "course_builder.workflows.audio.get_settings",
        lambda: type("Settings", (), {"elevenlabs_voice_id": "voice-123"})(),
    )
    monkeypatch.setattr(
        "course_builder.workflows.audio.list_kana_character_ids",
        lambda db, script: ["char-1", "char-2"] if script == "hiragana" else [],
    )
    monkeypatch.setattr("course_builder.workflows.audio.create_build_run", fake_create_build_run)
    monkeypatch.setattr("course_builder.workflows.audio.publish_build_run_event", lambda **kwargs: None)
    monkeypatch.setattr("course_builder.workflows.audio.generate_kana_audio_step", fake_generate_kana_audio_step)
    monkeypatch.setattr(
        "course_builder.workflows.audio.BuildRunTracking.log_message",
        staticmethod(fake_log_run_message),
    )
    monkeypatch.setattr(
        "course_builder.workflows.audio.BuildRunTracking.sync_progress",
        staticmethod(fake_sync_run_progress),
    )
    monkeypatch.setattr(
        "course_builder.workflows.audio.BuildRunTracking.mark_completed",
        staticmethod(lambda **kwargs: calls.setdefault("completed", kwargs)),
    )
    monkeypatch.setattr(
        "course_builder.workflows.audio.BuildRunTracking.mark_failed",
        staticmethod(lambda **kwargs: calls.setdefault("failed", kwargs)),
    )
    monkeypatch.setattr(
        "course_builder.workflows.audio.BuildRunTracking.is_cancelled",
        staticmethod(lambda **kwargs: False),
    )

    summary = generate_kana_audio_workflow.__wrapped__(  # type: ignore[attr-defined]  # DBOS preserves the wrapped function.
        script="hiragana",
    )

    assert summary == {
        "build_run_id": "kana-audio-run-1",
        "script": "hiragana",
        "total_character_count": 2,
        "generated_character_count": 1,
        "reused_character_count": 1,
        "failed_character_count": 0,
    }
    assert calls["create_build_run"] == {
        "section_code": "hiragana",
        "scope_kind": "kana_audio",
        "total_stage_count": 2,
        "workflow_id": "kana-audio-workflow-123",
    }
    assert calls["character_ids"] == ["char-1", "char-2"]
    assert calls["completed"]["build_run_id"] == "kana-audio-run-1"
    assert calls["completed"]["completed_stage_count"] == 2
