from __future__ import annotations

from collections import defaultdict

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.explain.schemas import (
    ExplainResponse,
    KanjiDetailResponse,
    KanjiLessonsResponse,
    KanjiLessonSummary,
    KanjiUsageRow,
    SentenceTokenDTO,
    SentenceTokensResponse,
)
from domain.auth.models import UserCourseEnrollment
from domain.content.display import (
    append_alternate_script_hint,
    display_sentence_text_ja,
    display_sentence_unit_surface,
    sentence_uses_kana_display,
)
from domain.content.models import Kanji, KanjiIntroduction, Lesson, Section, Sentence, SentenceUnit, Unit
from domain.explain.models import SentenceUnitHint
from domain.learning.models import UserLessonProgress


def _load_sentence_or_404(db: Session, sentence_id: str) -> Sentence:
    sentence = db.get(Sentence, sentence_id)
    if sentence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sentence not found")
    return sentence


def _load_tokens(db: Session, sentence_id: str) -> list[SentenceUnit]:
    return list(
        db.scalars(
            select(SentenceUnit)
            .where(SentenceUnit.sentence_id == sentence_id, SentenceUnit.lang == "ja")
            .order_by(SentenceUnit.unit_index.asc())
        )
    )


def _load_hints_by_token(db: Session, sentence_id: str) -> dict[int, list[str]]:
    hints = list(
        db.scalars(
            select(SentenceUnitHint)
            .where(SentenceUnitHint.sentence_id == sentence_id, SentenceUnitHint.lang == "ja")
            .order_by(SentenceUnitHint.unit_index.asc())
        )
    )
    hints_by_token: dict[int, list[str]] = defaultdict(list)
    for hint in hints:
        hints_by_token[hint.unit_index].append(hint.hint_text)
    return hints_by_token


def _serialize_tokens(
    tokens: list[SentenceUnit], hints_by_token: dict[int, list[str]], *, use_kana: bool
) -> list[SentenceTokenDTO]:
    return [
        SentenceTokenDTO(
            token_index=token.unit_index,
            surface=display_sentence_unit_surface(token, use_kana=use_kana),
            lemma=token.lemma,
            reading=token.reading,
            pos=token.pos,
            hints=append_alternate_script_hint(
                list(hints_by_token.get(token.unit_index, [])),
                displayed_surface=display_sentence_unit_surface(token, use_kana=use_kana),
                lemma=token.lemma,
                reading=token.reading,
                use_kana=use_kana,
            ),
        )
        for token in tokens
    ]


def get_sentence_tokens(db: Session, sentence_id: str) -> SentenceTokensResponse:
    sentence = _load_sentence_or_404(db, sentence_id)
    tokens = _load_tokens(db, sentence_id)
    hints_by_token = _load_hints_by_token(db, sentence_id)
    use_kana = sentence_uses_kana_display(db, sentence_id=sentence_id)
    return SentenceTokensResponse(
        sentence_id=sentence.id,
        sentence_ja=display_sentence_text_ja(sentence=sentence, units=tokens, use_kana=use_kana),
        sentence_en=sentence.en_text,
        tokens=_serialize_tokens(tokens, hints_by_token, use_kana=use_kana),
    )


def explain_token(db: Session, *, sentence_id: str, token_surface: str) -> ExplainResponse:
    sentence = _load_sentence_or_404(db, sentence_id)
    tokens = _load_tokens(db, sentence_id)
    hints_by_token = _load_hints_by_token(db, sentence_id)
    use_kana = sentence_uses_kana_display(db, sentence_id=sentence_id)
    token_dtos = _serialize_tokens(tokens, hints_by_token, use_kana=use_kana)
    matching = [token for token in token_dtos if token.surface == token_surface]
    if not matching:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found in sentence")
    return ExplainResponse(
        sentence_id=sentence.id,
        sentence_ja=display_sentence_text_ja(sentence=sentence, units=tokens, use_kana=use_kana),
        sentence_en=sentence.en_text,
        tokens=token_dtos,
        matching_tokens=matching,
    )


def list_kanji_lessons(db: Session, enrollment: UserCourseEnrollment) -> KanjiLessonsResponse:
    rows = list(
        db.execute(
            select(KanjiIntroduction, Lesson, Unit)
            .join(Lesson, Lesson.id == KanjiIntroduction.lesson_id)
            .join(Unit, Unit.id == Lesson.unit_id)
            .join(Section, Section.id == Unit.section_id)
            .where(KanjiIntroduction.course_version_id == enrollment.course_version_id)
            .order_by(Unit.order_index.asc(), Lesson.order_index.asc(), KanjiIntroduction.kanji_char.asc())
        )
    )
    progress_by_lesson = {
        progress.lesson_id: progress.state
        for progress in db.scalars(select(UserLessonProgress).where(UserLessonProgress.enrollment_id == enrollment.id))
    }
    by_lesson: dict[str, KanjiLessonSummary] = {}
    for intro, lesson, unit in rows:
        summary = by_lesson.get(lesson.id)
        if summary is None:
            summary = KanjiLessonSummary(
                lesson_id=lesson.id,
                unit_id=unit.id,
                unit_order_index=unit.order_index,
                lesson_order_index=lesson.order_index,
                state=progress_by_lesson.get(lesson.id, "not_started"),
                kanji_chars=[],
            )
            by_lesson[lesson.id] = summary
        if intro.kanji_char not in summary.kanji_chars:
            summary.kanji_chars.append(intro.kanji_char)
    return KanjiLessonsResponse(lessons=list(by_lesson.values()))


def get_kanji_detail(db: Session, enrollment: UserCourseEnrollment, kanji_char: str) -> KanjiDetailResponse:
    kanji = db.get(Kanji, kanji_char)
    if kanji is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kanji not found")
    rows = list(
        db.execute(
            select(KanjiIntroduction, Lesson, Unit)
            .join(Lesson, Lesson.id == KanjiIntroduction.lesson_id)
            .join(Unit, Unit.id == Lesson.unit_id)
            .join(Section, Section.id == Unit.section_id)
            .where(
                KanjiIntroduction.course_version_id == enrollment.course_version_id,
                KanjiIntroduction.kanji_char == kanji_char,
            )
            .order_by(Unit.order_index.asc(), Lesson.order_index.asc(), KanjiIntroduction.example_word_ja.asc())
        )
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kanji not found in active course")
    progress_by_lesson = {
        progress.lesson_id: progress.state
        for progress in db.scalars(select(UserLessonProgress).where(UserLessonProgress.enrollment_id == enrollment.id))
    }
    return KanjiDetailResponse(
        kanji_char=kanji.char,
        primary_meaning=kanji.primary_meaning,
        usages=[
            KanjiUsageRow(
                lesson_id=lesson.id,
                unit_id=unit.id,
                unit_order_index=unit.order_index,
                lesson_order_index=lesson.order_index,
                example_word_ja=intro.example_word_ja,
                example_reading=intro.example_reading,
                meaning_en=intro.meaning_en,
                is_learned=progress_by_lesson.get(lesson.id) == "completed",
            )
            for intro, lesson, unit in rows
        ],
    )
