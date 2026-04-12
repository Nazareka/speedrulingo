from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from api.kana.schemas import (
    KanaContinueResponse,
    KanaLessonItemResponse,
    KanaOverviewResponse,
    KanaSubmitRequest,
    KanaSubmitResponse,
)
from dependencies import CurrentEnrollment, DBSession
from domain.kana.audio_service import get_accessible_kana_audio_asset_or_404
from domain.kana.service import continue_kana_learning, get_kana_overview, get_next_kana_item, submit_kana_lesson

router = APIRouter(tags=["kana"])


@router.get("/kana/overview", response_model=KanaOverviewResponse)
def kana_overview(enrollment: CurrentEnrollment, db: DBSession) -> KanaOverviewResponse:
    return get_kana_overview(db, enrollment)


@router.post("/kana/continue", response_model=KanaContinueResponse)
def kana_continue(enrollment: CurrentEnrollment, db: DBSession) -> KanaContinueResponse:
    return continue_kana_learning(db, enrollment)


@router.get("/kana/lessons/{lesson_id}/next-item", response_model=KanaLessonItemResponse)
def kana_next_item(
    lesson_id: str,
    enrollment: CurrentEnrollment,
    db: DBSession,
    cursor: Annotated[int, Query(ge=0)] = 0,
) -> KanaLessonItemResponse:
    return get_next_kana_item(db, enrollment, lesson_id, cursor)


@router.post("/kana/lessons/{lesson_id}/submit", response_model=KanaSubmitResponse)
def kana_submit(
    lesson_id: str,
    payload: KanaSubmitRequest,
    enrollment: CurrentEnrollment,
    db: DBSession,
) -> KanaSubmitResponse:
    return submit_kana_lesson(db, enrollment, lesson_id, payload)


@router.get("/kana/audio/{asset_id}")
def kana_audio(asset_id: str, _enrollment: CurrentEnrollment, db: DBSession) -> FileResponse:
    asset = get_accessible_kana_audio_asset_or_404(db, asset_id=asset_id)
    return FileResponse(asset.storage_path, media_type=asset.mime_type, filename=f"{asset.id}.mp3")
