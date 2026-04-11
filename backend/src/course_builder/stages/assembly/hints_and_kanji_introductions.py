from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from core.lexicon import extract_kanji_chars
from course_builder.engine.models import BuildContext
from course_builder.queries.assembly import AssemblyQueries
from course_builder.sentence_processing import VocabItem, build_japanese_sentence_analysis
from domain.content.models import (
    Kanji,
    KanjiIntroduction,
    WordKanjiLink,
)
from domain.explain.models import SentenceUnitHint


@dataclass(frozen=True, slots=True)
class HintableWord:
    word_id: str
    canonical_writing_ja: str
    reading_kana: str
    gloss_primary_en: str
    gloss_alternatives_en: list[str]
    usage_note_en: str | None
    pos: str
    lesson_role: str


@dataclass(frozen=True, slots=True)
class HintsAndKanjiStats:
    sentence_unit_hints_created: int
    kanji_created: int
    word_kanji_links_created: int
    kanji_introductions_created: int


def _to_vocab_item(word: HintableWord) -> VocabItem:
    return VocabItem(
        word_id=word.word_id,
        canonical_writing_ja=word.canonical_writing_ja,
        reading_kana=word.reading_kana,
        gloss_primary_en=word.gloss_primary_en,
        gloss_alternatives_en=tuple(word.gloss_alternatives_en),
        usage_note_en=word.usage_note_en,
        pos=word.pos,
    )


def _load_primary_lesson_by_sentence_id(*, q: AssemblyQueries, section_id: str) -> dict[str, str]:
    return q.map_primary_lesson_id_by_sentence_id(section_id=section_id)


def _load_lesson_word_roles(*, q: AssemblyQueries, lesson_ids: list[str]) -> dict[tuple[str, str], str]:
    return q.map_lesson_word_role(lesson_ids=lesson_ids)


def _load_hintable_words_by_sentence_id(
    *,
    q: AssemblyQueries,
    sentence_to_primary_lesson_id: dict[str, str],
    lesson_word_roles: dict[tuple[str, str], str],
) -> dict[str, list[HintableWord]]:
    words_by_sentence_id: dict[str, list[HintableWord]] = {}
    course_words = q.list_course_words()
    for sentence_id, lesson_id in sentence_to_primary_lesson_id.items():
        words_by_sentence_id[sentence_id] = [
            HintableWord(
                word_id=word.id,
                canonical_writing_ja=word.canonical_writing_ja,
                reading_kana=word.reading_kana,
                gloss_primary_en=word.gloss_primary_en,
                gloss_alternatives_en=word.gloss_alternatives_en,
                usage_note_en=word.usage_note_en,
                pos=word.pos,
                lesson_role=lesson_word_roles.get((lesson_id, word.id), "safe_allowed"),
            )
            for word in course_words
        ]
    return words_by_sentence_id


def _create_sentence_unit_hints(*, db: Session, q: AssemblyQueries, section_id: str) -> int:
    sentence_ids = q.list_section_sentence_ids(section_id=section_id)
    if not sentence_ids:
        return 0

    sentence_text_by_id = q.map_sentence_texts_by_id(sentence_ids=sentence_ids)
    sentence_to_primary_lesson_id = _load_primary_lesson_by_sentence_id(q=q, section_id=section_id)
    primary_lesson_ids = list(dict.fromkeys(sentence_to_primary_lesson_id.values()))
    lesson_word_roles = _load_lesson_word_roles(
        q=q,
        lesson_ids=primary_lesson_ids,
    )
    words_by_sentence_id = _load_hintable_words_by_sentence_id(
        q=q,
        sentence_to_primary_lesson_id=sentence_to_primary_lesson_id,
        lesson_word_roles=lesson_word_roles,
    )

    created_count = 0
    for sentence_id in sentence_ids:
        words = words_by_sentence_id.get(sentence_id, [])
        sentence_text = sentence_text_by_id.get(sentence_id, {}).get("ja")
        if sentence_text is None or not words:
            continue
        analysis = build_japanese_sentence_analysis(
            sentence_ja=sentence_text,
            vocab=[_to_vocab_item(word) for word in words],
        )
        lesson_role_by_word_id = {word.word_id: word.lesson_role for word in words}
        for unit_index, chunk in enumerate(analysis.chunks):
            if not chunk.hints:
                continue
            is_new = any(
                vocab_item.word_id is not None and lesson_role_by_word_id.get(vocab_item.word_id) == "new"
                for vocab_item in chunk.vocab_items
            )
            for hint_text in chunk.hints:
                db.add(
                    SentenceUnitHint(
                        sentence_id=sentence_id,
                        lang="ja",
                        unit_index=unit_index,
                        hint_text=hint_text,
                        hint_kind="gloss",
                        is_new=is_new,
                    )
                )
                created_count += 1
    return created_count


def _create_kanji_inventory_and_introductions(
    *, db: Session, course_version_id: str, section_code: str, section_id: str
) -> tuple[int, int, int]:
    q = AssemblyQueries(db, course_version_id, section_code)
    words = q.list_course_words()

    kanji_created = 0
    word_kanji_links_created = 0
    kanji_introductions_created = 0
    existing_kanji_chars = q.list_existing_kanji_chars()
    existing_word_kanji_link_keys = q.list_existing_word_kanji_link_keys()

    word_kanji_chars_by_word_id: dict[str, list[str]] = {}
    for word in words:
        kanji_chars = extract_kanji_chars(word.canonical_writing_ja)
        if not kanji_chars:
            continue
        word_kanji_chars_by_word_id[word.id] = kanji_chars
        for char in kanji_chars:
            if char not in existing_kanji_chars:
                db.add(Kanji(char=char, primary_meaning=None))
                existing_kanji_chars.add(char)
                kanji_created += 1
        for order_index, char in enumerate(kanji_chars):
            link_key = (word.id, char, order_index)
            if link_key in existing_word_kanji_link_keys:
                continue
            db.add(
                WordKanjiLink(
                    word_id=word.id,
                    kanji_char=char,
                    order_index=order_index,
                )
            )
            existing_word_kanji_link_keys.add(link_key)
            word_kanji_links_created += 1

    lesson_word_rows = q.list_lesson_word_introductions(section_id=section_id)

    first_lesson_by_word_id: dict[str, tuple[str, str, str]] = {}
    for row in lesson_word_rows:
        if row.word_id in first_lesson_by_word_id:
            continue
        first_lesson_by_word_id[row.word_id] = (row.lesson_id, row.reading_kana, row.gloss_primary_en)

    seen_kanji_chars: set[str] = set()
    for word in words:
        kanji_chars = word_kanji_chars_by_word_id.get(word.id, [])
        if not kanji_chars:
            continue
        lesson_payload = first_lesson_by_word_id.get(word.id)
        if lesson_payload is None:
            continue
        lesson_id, reading_kana, gloss_primary_en = lesson_payload
        example_word_ja = word.canonical_writing_ja
        for char in kanji_chars:
            if char in seen_kanji_chars:
                continue
            seen_kanji_chars.add(char)
            db.add(
                KanjiIntroduction(
                    course_version_id=course_version_id,
                    lesson_id=lesson_id,
                    kanji_char=char,
                    word_id=word.id,
                    example_word_ja=example_word_ja,
                    example_reading=reading_kana,
                    meaning_en=gloss_primary_en,
                )
            )
            kanji_introductions_created += 1

    return kanji_created, word_kanji_links_created, kanji_introductions_created


def build_hints_and_kanji_introductions(
    db: Session,
    *,
    context: BuildContext,
) -> HintsAndKanjiStats:
    q = AssemblyQueries(db, context.course_version_id, context.section_code)
    section = q.get_section()
    if section is None:
        msg = (
            "Section config must exist before hints and kanji introduction generation "
            f"for course_version_id={context.course_version_id}"
        )
        raise ValueError(msg)
    if q.count_lessons_for_section(section_id=section.id) == 0:
        msg = (
            "Lessons must exist before hints and kanji introduction generation "
            f"for course_version_id={context.course_version_id}"
        )
        raise ValueError(msg)

    if q.exists_sentence_unit_hints_for_section(section_id=section.id):
        msg = (
            "Sentence-unit hints already exist for current section "
            f"course_version_id={context.course_version_id} section_code={context.section_code}"
        )
        raise ValueError(msg)
    if q.exists_kanji_introductions_for_section(section_id=section.id):
        msg = (
            "Kanji introductions already exist for current section "
            f"course_version_id={context.course_version_id} section_code={context.section_code}"
        )
        raise ValueError(msg)

    try:
        sentence_unit_hints_created = _create_sentence_unit_hints(db=db, q=q, section_id=section.id)
        kanji_created, word_kanji_links_created, kanji_introductions_created = (
            _create_kanji_inventory_and_introductions(
                db=db,
                course_version_id=context.course_version_id,
                section_code=context.section_code,
                section_id=section.id,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return HintsAndKanjiStats(
        sentence_unit_hints_created=sentence_unit_hints_created,
        kanji_created=kanji_created,
        word_kanji_links_created=word_kanji_links_created,
        kanji_introductions_created=kanji_introductions_created,
    )
