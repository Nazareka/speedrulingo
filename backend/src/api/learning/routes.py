from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from api.learning.schemas import LessonItemResponse, SubmitRequest, SubmitResponse
from dependencies import CurrentEnrollment, DBSession
from domain.content.audio_service import (
    get_accessible_sentence_audio_asset_or_404,
    get_accessible_word_audio_asset_or_404,
)
from domain.learning.service import get_next_item, submit_lesson

router = APIRouter(tags=["learning"])


@router.get("/lessons/{lesson_id}/next-item", response_model=LessonItemResponse)
def next_item(
    lesson_id: str,
    enrollment: CurrentEnrollment,
    db: DBSession,
    cursor: Annotated[int, Query(ge=0)] = 0,
) -> LessonItemResponse:
    return get_next_item(db, enrollment, lesson_id, cursor)


@router.post("/lessons/{lesson_id}/submit", response_model=SubmitResponse)
def submit(
    lesson_id: str,
    payload: SubmitRequest,
    enrollment: CurrentEnrollment,
    db: DBSession,
) -> SubmitResponse:
    return submit_lesson(db, enrollment=enrollment, lesson_id=lesson_id, payload=payload)


@router.get("/sentence-audio/{asset_id}")
def sentence_audio(
    asset_id: str,
    enrollment: CurrentEnrollment,
    db: DBSession,
) -> FileResponse:
    asset = get_accessible_sentence_audio_asset_or_404(
        db,
        asset_id=asset_id,
        course_version_id=enrollment.course_version_id,
    )
    return FileResponse(asset.storage_path, media_type=asset.mime_type, filename=f"{asset.id}.mp3")


@router.get("/word-audio/{asset_id}")
def word_audio(
    asset_id: str,
    enrollment: CurrentEnrollment,
    db: DBSession,
) -> FileResponse:
    asset = get_accessible_word_audio_asset_or_404(
        db,
        asset_id=asset_id,
        course_version_id=enrollment.course_version_id,
    )
    return FileResponse(asset.storage_path, media_type=asset.mime_type, filename=f"{asset.id}.mp3")
