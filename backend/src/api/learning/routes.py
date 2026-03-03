from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from api.learning.schemas import LessonItemResponse, SubmitRequest, SubmitResponse
from dependencies import CurrentEnrollment, DBSession
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
