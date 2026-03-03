from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from course_builder.stages.assembly.hints_and_kanji_introductions import (
    build_hints_and_kanji_introductions,
)
from domain.content.models import (
    Kanji,
    KanjiIntroduction,
    Lesson,
    Sentence,
    SentenceWordLink,
    Word,
    WordKanjiLink,
)
from domain.explain.models import SentenceUnitHint
from tests.helpers.builder import create_test_build_context
from tests.helpers.config_builder import build_test_config_yaml
from tests.helpers.pipeline import build_review_ready_course
from tests.helpers.scenarios import single_intro_unit_plan_payload

build_context = create_test_build_context


def hints_test_config() -> str:
    return build_test_config_yaml(
        updates={
            ("items", "review_previous_units", "item_count"): 2,
            ("items", "exam", "item_count"): 2,
        }
    )


def test_build_hints_and_kanji_introductions_persists_sentence_unit_hints_and_first_seen_kanji(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = create_test_build_context(db_session, tmp_path, content=hints_test_config())
    build_review_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )

    stats = build_hints_and_kanji_introductions(db_session, context=context)

    assert stats.sentence_unit_hints_created > 0
    assert stats.kanji_created >= 1
    assert stats.word_kanji_links_created >= 1
    assert stats.kanji_introductions_created >= 1

    unit_hints = db_session.scalars(
        select(SentenceUnitHint).order_by(SentenceUnitHint.sentence_id, SentenceUnitHint.hint_kind)
    ).all()
    assert unit_hints
    assert {hint.hint_kind for hint in unit_hints} == {"gloss"}
    assert all(hint.lang == "ja" for hint in unit_hints)
    assert any(hint.hint_kind == "gloss" and hint.hint_text for hint in unit_hints)

    kanji_links = db_session.scalars(select(WordKanjiLink)).all()
    assert len(kanji_links) >= 1
    assert any(link.kanji_char == "私" for link in kanji_links)

    kanji_introduction = db_session.scalar(select(KanjiIntroduction).limit(1))
    assert kanji_introduction is not None
    assert kanji_introduction.kanji_char == "私"
    assert kanji_introduction.example_word_ja == "私"
    assert kanji_introduction.example_reading == "わたし"
    assert kanji_introduction.meaning_en == "I"

    introduction_lesson = db_session.get(Lesson, kanji_introduction.lesson_id)
    assert introduction_lesson is not None


def test_build_hints_and_kanji_introductions_skips_existing_word_kanji_links(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = create_test_build_context(db_session, tmp_path, content=hints_test_config())
    build_review_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )

    word = db_session.scalar(select(Word).where(Word.canonical_writing_ja == "私"))
    assert word is not None
    db_session.add(Kanji(char="私", primary_meaning=None))
    db_session.add(WordKanjiLink(word_id=word.id, kanji_char="私", order_index=0))
    db_session.commit()

    stats = build_hints_and_kanji_introductions(db_session, context=context)

    assert stats.word_kanji_links_created >= 0
    assert (
        db_session.scalar(
            select(WordKanjiLink)
            .where(
                WordKanjiLink.word_id == word.id,
                WordKanjiLink.kanji_char == "私",
                WordKanjiLink.order_index == 0,
            )
            .limit(2)
        )
        is not None
    )
    assert (
        len(
            db_session.scalars(
                select(WordKanjiLink).where(
                    WordKanjiLink.word_id == word.id,
                    WordKanjiLink.kanji_char == "私",
                    WordKanjiLink.order_index == 0,
                )
            ).all()
        )
        == 1
    )


def test_build_hints_and_kanji_introductions_uses_primary_lesson_vocab_not_only_sentence_links(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = create_test_build_context(db_session, tmp_path, content=hints_test_config())
    build_review_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )

    sentence = db_session.scalar(select(Sentence).where(Sentence.ja_text == "私は学生です"))
    assert sentence is not None
    student_word = db_session.scalar(select(Word).where(Word.canonical_writing_ja == "学生"))
    assert student_word is not None

    db_session.execute(
        delete(SentenceWordLink).where(
            SentenceWordLink.sentence_id == sentence.id,
            SentenceWordLink.word_id != student_word.id,
        )
    )
    db_session.commit()

    stats = build_hints_and_kanji_introductions(db_session, context=context)

    assert stats.sentence_unit_hints_created > 0
    sentence_hints = db_session.scalars(
        select(SentenceUnitHint)
        .where(SentenceUnitHint.sentence_id == sentence.id)
        .order_by(SentenceUnitHint.unit_index, SentenceUnitHint.hint_text)
    ).all()
    assert sentence_hints
