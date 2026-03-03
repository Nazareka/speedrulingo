from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from course_builder.lexicon import extract_kanji_chars, is_kana_text
from domain.content.models import Lesson, LessonSentence, Section, Sentence, SentenceUnit, Unit, Word


def lesson_uses_kana_display(db: Session, *, lesson_id: str) -> bool:
    row = db.execute(select(Lesson.force_kana_display).where(Lesson.id == lesson_id).limit(1)).first()
    if row is None:
        return False
    return bool(row[0])


def sentence_uses_kana_display(db: Session, *, sentence_id: str) -> bool:
    row = db.execute(
        select(Lesson.force_kana_display)
        .join(LessonSentence, LessonSentence.lesson_id == Lesson.id)
        .join(Unit, Unit.id == Lesson.unit_id)
        .join(Section, Section.id == Unit.section_id)
        .where(LessonSentence.sentence_id == sentence_id)
        .order_by(Section.order_index.asc(), Unit.order_index.asc(), Lesson.order_index.asc())
        .limit(1)
    ).first()
    if row is None:
        return False
    return bool(row[0])


def display_word_ja(word: Word, *, use_kana: bool) -> str:
    return word.reading_kana if use_kana and word.reading_kana else word.canonical_writing_ja


def display_sentence_text_ja(*, sentence: Sentence, units: list[SentenceUnit], use_kana: bool) -> str:
    if not use_kana:
        return sentence.ja_text
    return "".join(display_sentence_unit_surface(unit, use_kana=use_kana) for unit in units)


def display_sentence_unit_surface(unit: SentenceUnit, *, use_kana: bool) -> str:
    return unit.reading if use_kana and unit.reading else unit.surface


def append_alternate_script_hint(
    hints: list[str],
    *,
    displayed_surface: str,
    lemma: str | None,
    reading: str | None,
    use_kana: bool,
) -> list[str]:
    if not lemma or not reading or not extract_kanji_chars(lemma):
        return hints

    alternate_hint: str | None = None
    if use_kana and is_kana_text(displayed_surface):
        alternate_hint = lemma
    elif not use_kana and displayed_surface == lemma and reading != displayed_surface:
        alternate_hint = reading

    if alternate_hint is None or alternate_hint in hints:
        return hints
    return [*hints, alternate_hint]
