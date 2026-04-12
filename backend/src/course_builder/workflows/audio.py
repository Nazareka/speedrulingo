from __future__ import annotations

from typing import TypedDict

from dbos import DBOS

from course_builder.build_runs.live_updates import publish_build_run_event
from course_builder.build_runs.models import (
    BuildRequest,
    KanaAudioSummary,
    SectionSentenceAudioSummary,
    SectionWordAudioSummary,
)
from course_builder.build_runs.queries import get_latest_completed_section_build_run
from course_builder.build_runs.run_state import create_build_run
from course_builder.build_runs.tracking import BuildRunTracking
from course_builder.workflows.audio_generation import (
    ensure_sentence_audio_asset,
    ensure_word_audio_asset,
    list_section_sentence_ids,
    list_section_word_ids,
    mark_sentence_audio_asset_failed,
    mark_word_audio_asset_failed,
)
from db.engine import SessionLocal
from domain.kana.audio_service import (
    ensure_kana_audio_asset,
    list_kana_character_ids,
    mark_kana_audio_asset_failed,
)
from settings import get_settings


class SentenceAudioStepResult(TypedDict):
    asset_id: str
    reused: bool


class WordAudioStepResult(TypedDict):
    asset_id: str
    reused: bool


class KanaAudioStepResult(TypedDict):
    asset_id: str
    reused: bool


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


@DBOS.step()
def generate_kana_audio_step(*, character_id: str) -> KanaAudioStepResult:
    with SessionLocal() as db:
        try:
            asset, reused = ensure_kana_audio_asset(db, character_id=character_id)
        except Exception as exc:
            db.rollback()
            mark_kana_audio_asset_failed(
                db,
                character_id=character_id,
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

    BuildRunTracking.log_message(  # DBOS workflows reuse orchestrator persistence helpers.
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
        if BuildRunTracking.is_cancelled(build_run_id=build_run_id):  # DBOS workflows reuse orchestrator helpers.
            break
        BuildRunTracking.sync_progress(
            build_run_id=build_run_id,
            completed_stage_count=sentence_index - 1,
            current_stage_name=f"sentence {sentence_index}/{len(sentence_ids)}",
            course_version_id=course_version_id,
        )
        try:
            step_result = generate_sentence_audio_step(sentence_id=sentence_id)
        except Exception as exc:
            failed_count += 1
            BuildRunTracking.log_message(
                build_run_id=build_run_id,
                level="ERROR",
                message=f"Sentence audio generation failed sentence_id={sentence_id} error={exc}",
                section_code=section_code,
            )
            BuildRunTracking.mark_failed(
                build_run_id=build_run_id,
                error_message=str(exc),
                current_stage_name=f"sentence {sentence_index}/{len(sentence_ids)}",
            )
            raise
        if step_result["reused"]:
            reused_count += 1
            BuildRunTracking.log_message(
                build_run_id=build_run_id,
                level="INFO",
                message=f"Reused sentence audio sentence_id={sentence_id} voice_id={voice_id}",
                section_code=section_code,
            )
        else:
            generated_count += 1
            BuildRunTracking.log_message(
                build_run_id=build_run_id,
                level="INFO",
                message=f"Generated sentence audio sentence_id={sentence_id} voice_id={voice_id}",
                section_code=section_code,
            )
        if BuildRunTracking.is_cancelled(build_run_id=build_run_id):
            break
        BuildRunTracking.sync_progress(
            build_run_id=build_run_id,
            completed_stage_count=sentence_index,
            current_stage_name=None if sentence_index == len(sentence_ids) else f"sentence {sentence_index + 1}/{len(sentence_ids)}",
            course_version_id=course_version_id,
        )

    if not BuildRunTracking.is_cancelled(build_run_id=build_run_id):
        BuildRunTracking.mark_completed(
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

    BuildRunTracking.log_message(
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
        if BuildRunTracking.is_cancelled(build_run_id=build_run_id):
            break
        BuildRunTracking.sync_progress(
            build_run_id=build_run_id,
            completed_stage_count=word_index - 1,
            current_stage_name=f"word {word_index}/{len(word_ids)}",
            course_version_id=course_version_id,
        )
        try:
            step_result = generate_word_audio_step(word_id=word_id)
        except Exception as exc:
            failed_count += 1
            BuildRunTracking.log_message(
                build_run_id=build_run_id,
                level="ERROR",
                message=f"Word audio generation failed word_id={word_id} error={exc}",
                section_code=section_code,
            )
            BuildRunTracking.mark_failed(
                build_run_id=build_run_id,
                error_message=str(exc),
                current_stage_name=f"word {word_index}/{len(word_ids)}",
            )
            raise
        if step_result["reused"]:
            reused_count += 1
            BuildRunTracking.log_message(
                build_run_id=build_run_id,
                level="INFO",
                message=f"Reused word audio word_id={word_id} voice_id={voice_id}",
                section_code=section_code,
            )
        else:
            generated_count += 1
            BuildRunTracking.log_message(
                build_run_id=build_run_id,
                level="INFO",
                message=f"Generated word audio word_id={word_id} voice_id={voice_id}",
                section_code=section_code,
            )
        if BuildRunTracking.is_cancelled(build_run_id=build_run_id):
            break
        BuildRunTracking.sync_progress(
            build_run_id=build_run_id,
            completed_stage_count=word_index,
            current_stage_name=None if word_index == len(word_ids) else f"word {word_index + 1}/{len(word_ids)}",
            course_version_id=course_version_id,
        )

    if not BuildRunTracking.is_cancelled(build_run_id=build_run_id):
        BuildRunTracking.mark_completed(
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


@DBOS.workflow()
def generate_kana_audio_workflow(script: str) -> KanaAudioSummary:
    if script not in {"hiragana", "katakana"}:
        msg = f"Unsupported kana script: {script}"
        raise ValueError(msg)

    request = BuildRequest(
        config="kana",
        build_version=1,
        section_code=script,
        all_stages=False,
        all_sections=False,
    )

    with SessionLocal() as db:
        character_ids = list_kana_character_ids(db, script=script)

    with SessionLocal() as db:
        build_run = create_build_run(
            db,
            request=request,
            scope_kind="kana_audio",
            total_stage_count=len(character_ids),
            workflow_id=DBOS.workflow_id,
        )
        db.commit()
        publish_build_run_event(
            event_type="build_run.created",
            build_run_id=build_run.id,
            parent_build_run_id=build_run.parent_build_run_id,
        )
        build_run_id = build_run.id

    BuildRunTracking.log_message(
        build_run_id=build_run_id,
        level="INFO",
        message=f"Starting kana audio generation script={script} character_count={len(character_ids)}",
        section_code=script,
    )

    generated_count = 0
    reused_count = 0
    failed_count = 0
    settings = get_settings()
    voice_id = settings.elevenlabs_voice_id
    if voice_id is None:
        msg = "ElevenLabs voice is not configured"
        raise ValueError(msg)

    for character_index, character_id in enumerate(character_ids, start=1):
        if BuildRunTracking.is_cancelled(build_run_id=build_run_id):
            break
        BuildRunTracking.sync_progress(
            build_run_id=build_run_id,
            completed_stage_count=character_index - 1,
            current_stage_name=f"{script} {character_index}/{len(character_ids)}",
            course_version_id=None,
        )
        try:
            step_result = generate_kana_audio_step(character_id=character_id)
        except Exception as exc:
            failed_count += 1
            BuildRunTracking.log_message(
                build_run_id=build_run_id,
                level="ERROR",
                message=f"Kana audio generation failed character_id={character_id} error={exc}",
                section_code=script,
            )
            BuildRunTracking.mark_failed(
                build_run_id=build_run_id,
                error_message=str(exc),
                current_stage_name=f"{script} {character_index}/{len(character_ids)}",
            )
            raise
        if step_result["reused"]:
            reused_count += 1
            BuildRunTracking.log_message(
                build_run_id=build_run_id,
                level="INFO",
                message=f"Reused kana audio character_id={character_id} voice_id={voice_id}",
                section_code=script,
            )
        else:
            generated_count += 1
            BuildRunTracking.log_message(
                build_run_id=build_run_id,
                level="INFO",
                message=f"Generated kana audio character_id={character_id} voice_id={voice_id}",
                section_code=script,
            )
        if BuildRunTracking.is_cancelled(build_run_id=build_run_id):
            break
        BuildRunTracking.sync_progress(
            build_run_id=build_run_id,
            completed_stage_count=character_index,
            current_stage_name=(
                None
                if character_index == len(character_ids)
                else f"{script} {character_index + 1}/{len(character_ids)}"
            ),
            course_version_id=None,
        )

    if not BuildRunTracking.is_cancelled(build_run_id=build_run_id):
        BuildRunTracking.mark_completed(
            build_run_id=build_run_id,
            course_version_id=None,
            completed_stage_count=generated_count + reused_count,
        )
    return {
        "build_run_id": build_run_id,
        "script": script,
        "total_character_count": len(character_ids),
        "generated_character_count": generated_count,
        "reused_character_count": reused_count,
        "failed_character_count": failed_count,
    }
