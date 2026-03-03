from __future__ import annotations

from fastapi import APIRouter

from api.explain.schemas import (
    ExplainRequest,
    ExplainResponse,
    KanjiDetailResponse,
    KanjiLessonsResponse,
    SentenceTokensResponse,
)
from dependencies import CurrentEnrollment, DBSession
from domain.explain.service import explain_token, get_kanji_detail, get_sentence_tokens, list_kanji_lessons

router = APIRouter(tags=["explain"])


@router.get("/sentences/{sentence_id}/tokens", response_model=SentenceTokensResponse)
def sentence_tokens(sentence_id: str, _: CurrentEnrollment, db: DBSession) -> SentenceTokensResponse:
    return get_sentence_tokens(db, sentence_id)


@router.post("/explain/token", response_model=ExplainResponse)
def explain_token_route(payload: ExplainRequest, _: CurrentEnrollment, db: DBSession) -> ExplainResponse:
    return explain_token(db, sentence_id=payload.sentence_id, token_surface=payload.token_surface)


@router.get("/kanji/lessons", response_model=KanjiLessonsResponse)
def kanji_lessons(enrollment: CurrentEnrollment, db: DBSession) -> KanjiLessonsResponse:
    return list_kanji_lessons(db, enrollment)


@router.get("/kanji/{kanji_char}", response_model=KanjiDetailResponse)
def kanji_detail(kanji_char: str, enrollment: CurrentEnrollment, db: DBSession) -> KanjiDetailResponse:
    return get_kanji_detail(db, enrollment, kanji_char)
