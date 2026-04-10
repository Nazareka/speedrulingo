from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import TypedDict, cast

from dbos import DBOS, DBOSConfig

from course_builder.runtime.live_updates import publish_build_run_event
from course_builder.runtime.orchestration import CourseBuildOrchestrator, SectionRunner
from course_builder.runtime.queries import get_latest_completed_section_build_run
from course_builder.runtime.run_state import create_build_run
from course_builder.runtime.runner import BuildStageRunResult
from course_builder.runtime.workflow_models import (
    AllSectionsBuildSummary,
    BuildRequest,
    SectionBuildSummary,
    SectionSentenceAudioSummary,
    SectionWordAudioSummary,
)
from db.engine import SessionLocal
from domain.content.audio_service import (
    ensure_sentence_audio_asset,
    ensure_word_audio_asset,
    list_section_sentence_ids,
    list_section_word_ids,
    mark_sentence_audio_asset_failed,
    mark_word_audio_asset_failed,
)
from settings import get_settings

_LAUNCH_LOCK = Lock()
_DBOS_INITIALIZED = False


class SentenceAudioStepResult(TypedDict):
    asset_id: str
    reused: bool


class WordAudioStepResult(TypedDict):
    asset_id: str
    reused: bool


def build_dbos_config() -> DBOSConfig:
    settings = get_settings()
    return {
        "name": "speedrulingo-course-builder",
        "system_database_url": settings.dbos_system_database_url,
    }


def launch_dbos() -> None:
    global _DBOS_INITIALIZED
    with _LAUNCH_LOCK:
        if _DBOS_INITIALIZED:
            return
        DBOS(config=build_dbos_config())
        DBOS.launch()
        _DBOS_INITIALIZED = True


def cancel_dbos_workflow(*, workflow_id: str) -> None:
    launch_dbos()
    DBOS.cancel_workflow(workflow_id)


async def cancel_dbos_workflow_async(*, workflow_id: str) -> None:
    launch_dbos()
    await DBOS.cancel_workflow_async(workflow_id)


@DBOS.step()
def run_one_stage_step(
    *,
    config: str,
    build_version: int,
    section_code: str,
    build_run_id: str | None = None,
    stage_name: str | None = None,
) -> BuildStageRunResult:
    orchestrator = CourseBuildOrchestrator()
    return orchestrator.run_one_stage(
        config_path=Path(config),
        section_code=section_code,
        build_version=build_version,
        build_run_id=build_run_id,
        stage_name=stage_name,
    )


def _run_section_with_dbos_steps(
    request: BuildRequest,
    *,
    build_run_id: str | None = None,
    parent_build_run_id: str | None = None,
    workflow_id: str | None = None,
) -> SectionBuildSummary:
    def dbos_stage_runner(
        *,
        config_path: Path,
        build_version: int,
        section_code: str,
        build_run_id: str | None = None,
        stage_name: str | None = None,
    ) -> BuildStageRunResult:
        return run_one_stage_step(
            config=str(config_path),
            build_version=build_version,
            section_code=section_code,
            build_run_id=build_run_id,
            stage_name=stage_name,
        )

    orchestrator = CourseBuildOrchestrator()
    return orchestrator.run_section_until_done(
        request,
        stage_runner=dbos_stage_runner,
        build_run_id=build_run_id,
        parent_build_run_id=parent_build_run_id,
        workflow_id=workflow_id,
    )


@DBOS.workflow()
def build_section_workflow(
    config: str,
    build_version: int,
    section_code: str,
    all_stages: bool = True,
) -> SectionBuildSummary:
    return _run_section_with_dbos_steps(
        BuildRequest(
            config=config,
            build_version=build_version,
            section_code=section_code,
            all_stages=all_stages,
            all_sections=False,
        ),
        workflow_id=DBOS.workflow_id,
    )


@DBOS.workflow()
def build_all_sections_workflow(
    config: str,
    build_version: int,
    all_stages: bool = True,
) -> AllSectionsBuildSummary:
    orchestrator = CourseBuildOrchestrator()
    request = BuildRequest(
        config=config,
        build_version=build_version,
        all_stages=all_stages,
        all_sections=True,
    )

    def section_runner(
        section_request: BuildRequest,
        *,
        build_run_id: str | None = None,
        parent_build_run_id: str | None = None,
    ) -> SectionBuildSummary:
        return _run_section_with_dbos_steps(
            section_request,
            build_run_id=build_run_id,
            parent_build_run_id=parent_build_run_id,
            workflow_id=None,
        )

    return orchestrator.run_all_sections_until_done(
        request,
        section_runner=cast(SectionRunner, section_runner),
        workflow_id=DBOS.workflow_id,
    )


@DBOS.step()
def generate_sentence_audio_step(*, sentence_id: str) -> SentenceAudioStepResult:
    with SessionLocal() as db:
        try:
            asset, reused = ensure_sentence_audio_asset(db, sentence_id=sentence_id)
        except Exception as exc:
            db.rollback()
            mark_sentence_audio_asset_failed(
                db,
                sentence_id=sentence_id,
                error_message=str(exc),
            )
            db.commit()
            raise
        db.commit()
        return {
            "asset_id": asset.id,
            "reused": reused,
        }


@DBOS.step()
def generate_word_audio_step(*, word_id: str) -> WordAudioStepResult:
    with SessionLocal() as db:
        try:
            asset, reused = ensure_word_audio_asset(db, word_id=word_id)
        except Exception as exc:
            db.rollback()
            mark_word_audio_asset_failed(
                db,
                word_id=word_id,
                error_message=str(exc),
            )
            db.commit()
            raise
        db.commit()
        return {
            "asset_id": asset.id,
            "reused": reused,
        }


@DBOS.workflow()
def generate_section_sentence_audio_workflow(
    config: str,
    build_version: int,
    section_code: str,
) -> SectionSentenceAudioSummary:
    orchestrator = CourseBuildOrchestrator()
    request = BuildRequest(
        config=config,
        build_version=build_version,
        section_code=section_code,
        all_stages=False,
        all_sections=False,
    )
    with SessionLocal() as db:
        section_run = get_latest_completed_section_build_run(
            db,
            build_version=build_version,
            config_path=config,
            section_code=section_code,
        )
        if section_run is None or section_run.course_version_id is None:
            msg = "Section audio generation requires a completed section build run"
            raise ValueError(msg)
        source_section_build_run_id = section_run.id
        course_version_id = section_run.course_version_id
        sentence_ids = list_section_sentence_ids(
            db,
            course_version_id=course_version_id,
            section_code=section_code,
        )

    with SessionLocal() as db:
        build_run = create_build_run(
            db,
            request=request,
            scope_kind="section_audio",
            total_stage_count=len(sentence_ids),
            workflow_id=DBOS.workflow_id,
        )
        build_run.course_version_id = course_version_id
        db.commit()
        publish_build_run_event(
            event_type="build_run.created",
            build_run_id=build_run.id,
            parent_build_run_id=build_run.parent_build_run_id,
        )
        build_run_id = build_run.id

    orchestrator._log_run_message(  # runtime workflows intentionally reuse orchestrator persistence helpers.
        build_run_id=build_run_id,
        level="INFO",
        message=(
            f"Starting section sentence audio generation config={config} section={section_code} "
            f"build_version={build_version} sentence_count={len(sentence_ids)}"
        ),
        section_code=section_code,
    )

    generated_count = 0
    reused_count = 0
    failed_count = 0
    settings = get_settings()
    voice_id = settings.elevenlabs_voice_id
    if voice_id is None:
        msg = "ElevenLabs voice is not configured"
        raise ValueError(msg)

    for sentence_index, sentence_id in enumerate(sentence_ids, start=1):
        if orchestrator._is_run_cancelled(build_run_id=build_run_id):  # runtime workflows intentionally reuse orchestrator persistence helpers.
            break
        orchestrator._sync_run_progress(  # runtime workflows intentionally reuse orchestrator persistence helpers.
            build_run_id=build_run_id,
            completed_stage_count=sentence_index - 1,
            current_stage_name=f"sentence {sentence_index}/{len(sentence_ids)}",
            course_version_id=course_version_id,
        )
        try:
            step_result = generate_sentence_audio_step(sentence_id=sentence_id)
        except Exception as exc:
            failed_count += 1
            orchestrator._log_run_message(  # runtime workflows intentionally reuse orchestrator persistence helpers.
                build_run_id=build_run_id,
                level="ERROR",
                message=f"Sentence audio generation failed sentence_id={sentence_id} error={exc}",
                section_code=section_code,
            )
            orchestrator._mark_run_failed(  # runtime workflows intentionally reuse orchestrator persistence helpers.
                build_run_id=build_run_id,
                error_message=str(exc),
                current_stage_name=f"sentence {sentence_index}/{len(sentence_ids)}",
            )
            raise
        if step_result["reused"]:
            reused_count += 1
            orchestrator._log_run_message(  # runtime workflows intentionally reuse orchestrator persistence helpers.
                build_run_id=build_run_id,
                level="INFO",
                message=f"Reused sentence audio sentence_id={sentence_id} voice_id={voice_id}",
                section_code=section_code,
            )
        else:
            generated_count += 1
            orchestrator._log_run_message(  # runtime workflows intentionally reuse orchestrator persistence helpers.
                build_run_id=build_run_id,
                level="INFO",
                message=f"Generated sentence audio sentence_id={sentence_id} voice_id={voice_id}",
                section_code=section_code,
            )
        if orchestrator._is_run_cancelled(build_run_id=build_run_id):  # runtime workflows intentionally reuse orchestrator persistence helpers.
            break
        orchestrator._sync_run_progress(  # runtime workflows intentionally reuse orchestrator persistence helpers.
            build_run_id=build_run_id,
            completed_stage_count=sentence_index,
            current_stage_name=None if sentence_index == len(sentence_ids) else f"sentence {sentence_index + 1}/{len(sentence_ids)}",
            course_version_id=course_version_id,
        )

    if not orchestrator._is_run_cancelled(build_run_id=build_run_id):  # runtime workflows intentionally reuse orchestrator persistence helpers.
        orchestrator._mark_run_completed(  # runtime workflows intentionally reuse orchestrator persistence helpers.
            build_run_id=build_run_id,
            course_version_id=course_version_id,
            completed_stage_count=generated_count + reused_count,
        )
    return {
        "build_run_id": build_run_id,
        "source_section_build_run_id": source_section_build_run_id,
        "build_version": build_version,
        "section_code": section_code,
        "total_sentence_count": len(sentence_ids),
        "generated_sentence_count": generated_count,
        "reused_sentence_count": reused_count,
        "failed_sentence_count": failed_count,
    }


@DBOS.workflow()
def generate_section_word_audio_workflow(
    config: str,
    build_version: int,
    section_code: str,
) -> SectionWordAudioSummary:
    orchestrator = CourseBuildOrchestrator()
    request = BuildRequest(
        config=config,
        build_version=build_version,
        section_code=section_code,
        all_stages=False,
        all_sections=False,
    )
    with SessionLocal() as db:
        section_run = get_latest_completed_section_build_run(
            db,
            build_version=build_version,
            config_path=config,
            section_code=section_code,
        )
        if section_run is None or section_run.course_version_id is None:
            msg = "Section word audio generation requires a completed section build run"
            raise ValueError(msg)
        source_section_build_run_id = section_run.id
        course_version_id = section_run.course_version_id
        word_ids = list_section_word_ids(
            db,
            course_version_id=course_version_id,
            section_code=section_code,
        )

    with SessionLocal() as db:
        build_run = create_build_run(
            db,
            request=request,
            scope_kind="section_word_audio",
            total_stage_count=len(word_ids),
            workflow_id=DBOS.workflow_id,
        )
        build_run.course_version_id = course_version_id
        db.commit()
        publish_build_run_event(
            event_type="build_run.created",
            build_run_id=build_run.id,
            parent_build_run_id=build_run.parent_build_run_id,
        )
        build_run_id = build_run.id

    orchestrator._log_run_message(
        build_run_id=build_run_id,
        level="INFO",
        message=(
            f"Starting section word audio generation config={config} section={section_code} "
            f"build_version={build_version} word_count={len(word_ids)}"
        ),
        section_code=section_code,
    )

    generated_count = 0
    reused_count = 0
    failed_count = 0
    settings = get_settings()
    voice_id = settings.elevenlabs_voice_id
    if voice_id is None:
        msg = "ElevenLabs voice is not configured"
        raise ValueError(msg)

    for word_index, word_id in enumerate(word_ids, start=1):
        if orchestrator._is_run_cancelled(build_run_id=build_run_id):
            break
        orchestrator._sync_run_progress(
            build_run_id=build_run_id,
            completed_stage_count=word_index - 1,
            current_stage_name=f"word {word_index}/{len(word_ids)}",
            course_version_id=course_version_id,
        )
        try:
            step_result = generate_word_audio_step(word_id=word_id)
        except Exception as exc:
            failed_count += 1
            orchestrator._log_run_message(
                build_run_id=build_run_id,
                level="ERROR",
                message=f"Word audio generation failed word_id={word_id} error={exc}",
                section_code=section_code,
            )
            orchestrator._mark_run_failed(
                build_run_id=build_run_id,
                error_message=str(exc),
                current_stage_name=f"word {word_index}/{len(word_ids)}",
            )
            raise
        if step_result["reused"]:
            reused_count += 1
            orchestrator._log_run_message(
                build_run_id=build_run_id,
                level="INFO",
                message=f"Reused word audio word_id={word_id} voice_id={voice_id}",
                section_code=section_code,
            )
        else:
            generated_count += 1
            orchestrator._log_run_message(
                build_run_id=build_run_id,
                level="INFO",
                message=f"Generated word audio word_id={word_id} voice_id={voice_id}",
                section_code=section_code,
            )
        if orchestrator._is_run_cancelled(build_run_id=build_run_id):
            break
        orchestrator._sync_run_progress(
            build_run_id=build_run_id,
            completed_stage_count=word_index,
            current_stage_name=None if word_index == len(word_ids) else f"word {word_index + 1}/{len(word_ids)}",
            course_version_id=course_version_id,
        )

    if not orchestrator._is_run_cancelled(build_run_id=build_run_id):
        orchestrator._mark_run_completed(
            build_run_id=build_run_id,
            course_version_id=course_version_id,
            completed_stage_count=generated_count + reused_count,
        )
    return {
        "build_run_id": build_run_id,
        "source_section_build_run_id": source_section_build_run_id,
        "build_version": build_version,
        "section_code": section_code,
        "total_word_count": len(word_ids),
        "generated_word_count": generated_count,
        "reused_word_count": reused_count,
        "failed_word_count": failed_count,
    }
