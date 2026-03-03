from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, func, select
from sqlalchemy.orm import aliased

from course_builder.queries.shared import CourseVersionQueries
from domain.content.models import (
    Item,
    ItemWordChoice,
    Kanji,
    KanjiIntroduction,
    Lesson,
    LessonSentence,
    LessonWord,
    Pattern,
    PlannedLesson,
    PlannedUnit,
    Section,
    Sentence,
    SentenceTileSet,
    SentenceUnit,
    SentenceWordLink,
    Unit,
    UnitPatternLink,
    Word,
)
from domain.explain.models import SentenceUnitHint


@dataclass(frozen=True, slots=True)
class LessonWordIntroductionRow:
    lesson_id: str
    word_id: str
    reading_kana: str
    gloss_primary_en: str


@dataclass(frozen=True, slots=True)
class SentenceSelectionRow:
    sentence_id: str
    source_unit_order_index: int
    source_lesson_order_index: int
    source_sentence_order_index: int


@dataclass(frozen=True, slots=True)
class WordPoolRow:
    word_id: str
    canonical_writing_ja: str
    intro_order: int
    is_safe_pool: bool


@dataclass(frozen=True, slots=True)
class PatternPoolRow:
    pattern_id: str
    code: str
    intro_order: int


class AssemblyQueries(CourseVersionQueries):
    def list_previously_introduced_word_ids(self) -> list[str]:
        section = self.get_section()
        if section is None:
            return []
        return list(
            self.db.scalars(
                select(ItemWordChoice.word_id)
                .join(Item, Item.id == ItemWordChoice.item_id)
                .join(Lesson, Lesson.id == Item.lesson_id)
                .join(Unit, Unit.id == Lesson.unit_id)
                .join(Section, Section.id == Unit.section_id)
                .where(
                    Section.course_version_id == self.course_version_id,
                    Section.order_index < section.order_index,
                )
                .distinct()
            )
        )

    def count_lessons_for_section(self, *, section_id: str) -> int:
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(Lesson)
                .join(Unit, Unit.id == Lesson.unit_id)
                .where(Unit.section_id == section_id)
            )
            or 0
        )

    def list_section_lessons(self, *, section_id: str) -> list[Lesson]:
        return list(
            self.db.scalars(
                select(Lesson)
                .join(Unit, Unit.id == Lesson.unit_id)
                .where(Unit.section_id == section_id)
                .order_by(Unit.order_index, Lesson.order_index)
            ).all()
        )

    def list_word_ids_for_lesson(self, *, lesson_id: str) -> list[str]:
        return list(
            self.db.scalars(
                select(Word.id)
                .join(LessonWord, LessonWord.word_id == Word.id)
                .where(LessonWord.lesson_id == lesson_id)
                .order_by(Word.intro_order)
            )
        )

    def list_word_rows_for_lesson(self, *, lesson_id: str) -> list[Word]:
        return list(
            self.db.scalars(
                select(Word)
                .join(LessonWord, LessonWord.word_id == Word.id)
                .where(LessonWord.lesson_id == lesson_id)
                .order_by(Word.intro_order)
            )
        )

    def list_new_word_ids_for_lesson(self, *, lesson_id: str) -> list[str]:
        return list(
            self.db.scalars(
                select(Word.id)
                .join(LessonWord, LessonWord.word_id == Word.id)
                .where(LessonWord.lesson_id == lesson_id, LessonWord.role == "new")
                .order_by(Word.intro_order)
            )
        )

    def list_sentence_ids_for_lesson(self, *, lesson_id: str) -> list[str]:
        return list(
            self.db.scalars(
                select(LessonSentence.sentence_id)
                .where(LessonSentence.lesson_id == lesson_id)
                .order_by(LessonSentence.order_index)
            )
        )

    def map_tile_set_id_by_sentence_id(self, *, sentence_ids: list[str], answer_lang: str) -> dict[str, str]:
        if not sentence_ids:
            return {}
        return {
            row.sentence_id: row.id
            for row in self.db.execute(
                select(SentenceTileSet.id, SentenceTileSet.sentence_id).where(
                    SentenceTileSet.sentence_id.in_(sentence_ids),
                    SentenceTileSet.answer_lang == answer_lang,
                )
            ).all()
        }

    def list_tile_set_ids_for_sentences(self, *, sentence_ids: list[str]) -> list[str]:
        if not sentence_ids:
            return []
        return list(self.db.scalars(select(SentenceTileSet.id).where(SentenceTileSet.sentence_id.in_(sentence_ids))))

    def map_sentence_texts_by_id(self, *, sentence_ids: list[str]) -> dict[str, dict[str, str]]:
        return {
            row.id: {"ja": row.ja_text, "en": row.en_text}
            for row in self.db.execute(
                select(Sentence.id, Sentence.ja_text, Sentence.en_text).where(Sentence.id.in_(sentence_ids))
            ).all()
        }

    def list_sentence_units(self, *, sentence_ids: list[str], lang: str | None = None) -> list[SentenceUnit]:
        statement = select(SentenceUnit).where(SentenceUnit.sentence_id.in_(sentence_ids))
        if lang is not None:
            statement = statement.where(SentenceUnit.lang == lang)
        statement = statement.order_by(
            SentenceUnit.sentence_id.asc(), SentenceUnit.lang.asc(), SentenceUnit.unit_index.asc()
        )
        return list(self.db.scalars(statement).all())

    def map_word_ids_by_sentence_id(self, *, sentence_ids: list[str]) -> dict[str, set[str]]:
        rows = self.db.execute(
            select(SentenceWordLink.sentence_id, SentenceWordLink.word_id).where(
                SentenceWordLink.sentence_id.in_(sentence_ids)
            )
        ).all()
        sentence_word_ids_by_sentence_id: dict[str, set[str]] = {}
        for row in rows:
            sentence_word_ids_by_sentence_id.setdefault(row.sentence_id, set()).add(row.word_id)
        return sentence_word_ids_by_sentence_id

    def exists_sentence_unit_hints_for_section(self, *, section_id: str) -> bool:
        return (
            self.db.scalar(
                select(SentenceUnitHint.id)
                .join(Sentence, Sentence.id == SentenceUnitHint.sentence_id)
                .join(LessonSentence, LessonSentence.sentence_id == Sentence.id)
                .join(Lesson, Lesson.id == LessonSentence.lesson_id)
                .join(Unit, Unit.id == Lesson.unit_id)
                .where(Unit.section_id == section_id)
                .limit(1)
            )
            is not None
        )

    def exists_kanji_introductions_for_section(self, *, section_id: str) -> bool:
        return (
            self.db.scalar(
                select(KanjiIntroduction.id)
                .join(Lesson, Lesson.id == KanjiIntroduction.lesson_id)
                .join(Unit, Unit.id == Lesson.unit_id)
                .where(Unit.section_id == section_id)
                .limit(1)
            )
            is not None
        )

    def list_section_sentence_ids(self, *, section_id: str) -> list[str]:
        return list(
            self.db.scalars(
                select(Sentence.id)
                .join(LessonSentence, LessonSentence.sentence_id == Sentence.id)
                .join(Lesson, Lesson.id == LessonSentence.lesson_id)
                .join(Unit, Unit.id == Lesson.unit_id)
                .where(Unit.section_id == section_id)
                .distinct()
            )
        )

    def map_primary_lesson_id_by_sentence_id(self, *, section_id: str) -> dict[str, str]:
        rows = self.db.execute(
            select(
                LessonSentence.sentence_id.label("sentence_id"),
                Lesson.id.label("lesson_id"),
            )
            .join(Lesson, Lesson.id == LessonSentence.lesson_id)
            .join(Unit, Unit.id == Lesson.unit_id)
            .where(Unit.section_id == section_id)
            .order_by(LessonSentence.sentence_id, Unit.order_index, Lesson.order_index, LessonSentence.order_index)
        ).all()
        sentence_to_lesson_id: dict[str, str] = {}
        for row in rows:
            sentence_to_lesson_id.setdefault(row.sentence_id, row.lesson_id)
        return sentence_to_lesson_id

    def map_lesson_word_role(self, *, lesson_ids: list[str]) -> dict[tuple[str, str], str]:
        rows = self.db.execute(
            select(LessonWord.lesson_id, LessonWord.word_id, LessonWord.role).where(
                LessonWord.lesson_id.in_(lesson_ids)
            )
        ).all()
        return {(row.lesson_id, row.word_id): row.role for row in rows}

    def list_course_words(self) -> list[Word]:
        return list(
            self.db.scalars(
                select(Word)
                .where(Word.course_version_id == self.course_version_id)
                .order_by(Word.intro_order, Word.canonical_writing_ja)
            ).all()
        )

    def list_existing_kanji_chars(self) -> set[str]:
        return set(self.db.scalars(select(Kanji.char)))

    def list_existing_word_kanji_link_keys(self) -> set[tuple[str, str, int]]:
        from domain.content.models import WordKanjiLink

        return {
            (row.word_id, row.kanji_char, row.order_index)
            for row in self.db.execute(
                select(
                    WordKanjiLink.word_id,
                    WordKanjiLink.kanji_char,
                    WordKanjiLink.order_index,
                )
                .join(Word, Word.id == WordKanjiLink.word_id)
                .where(Word.course_version_id == self.course_version_id)
            ).all()
        }

    def list_lesson_word_introductions(self, *, section_id: str) -> list[LessonWordIntroductionRow]:
        return [
            LessonWordIntroductionRow(
                lesson_id=row.lesson_id,
                word_id=row.word_id,
                reading_kana=row.reading_kana,
                gloss_primary_en=row.gloss_primary_en,
            )
            for row in self.db.execute(
                select(
                    Lesson.id.label("lesson_id"),
                    Word.id.label("word_id"),
                    Word.reading_kana,
                    Word.gloss_primary_en,
                )
                .join(LessonWord, LessonWord.lesson_id == Lesson.id)
                .join(Word, Word.id == LessonWord.word_id)
                .join(Unit, Unit.id == Lesson.unit_id)
                .where(Unit.section_id == section_id)
                .order_by(Unit.order_index, Lesson.order_index, Word.intro_order, Word.canonical_writing_ja)
            ).all()
        ]

    def exists_non_normal_lessons_for_section(self, *, section_id: str) -> bool:
        return (
            self.db.scalar(
                select(Lesson.id)
                .join(Unit, Unit.id == Lesson.unit_id)
                .where(Unit.section_id == section_id, Lesson.kind.in_(("review_previous_units", "exam")))
                .limit(1)
            )
            is not None
        )

    def list_normal_lesson_order_indices_for_unit(self, *, unit_id: str) -> list[int]:
        return list(
            self.db.scalars(
                select(Lesson.order_index)
                .where(Lesson.unit_id == unit_id, Lesson.kind == "normal")
                .order_by(Lesson.order_index)
            )
        )

    @staticmethod
    def _sentence_pool_query(*, unit_ids: list[str]) -> Select[tuple[str, int, int, int]]:
        source_lesson = aliased(Lesson)
        source_unit = aliased(Unit)
        earlier_source_lesson = aliased(Lesson)
        earlier_source_unit = aliased(Unit)
        source_lesson_sentence = aliased(LessonSentence)
        earlier_source_lesson_sentence = aliased(LessonSentence)
        return (
            select(
                Sentence.id.label("sentence_id"),
                Unit.order_index.label("unit_order_index"),
                Lesson.order_index.label("lesson_order_index"),
                LessonSentence.order_index.label("sentence_order_index"),
            )
            .join(LessonSentence, LessonSentence.sentence_id == Sentence.id)
            .join(Lesson, Lesson.id == LessonSentence.lesson_id)
            .join(Unit, Unit.id == Lesson.unit_id)
            .where(
                Unit.id.in_(unit_ids),
                Lesson.kind == "normal",
                ~select(earlier_source_lesson_sentence.sentence_id)
                .join(earlier_source_lesson, earlier_source_lesson.id == earlier_source_lesson_sentence.lesson_id)
                .join(earlier_source_unit, earlier_source_unit.id == earlier_source_lesson.unit_id)
                .join(source_lesson_sentence, source_lesson_sentence.sentence_id == Sentence.id)
                .join(source_lesson, source_lesson.id == source_lesson_sentence.lesson_id)
                .join(source_unit, source_unit.id == source_lesson.unit_id)
                .where(
                    source_unit.id == Unit.id,
                    source_lesson.id == Lesson.id,
                    earlier_source_unit.section_id == source_unit.section_id,
                    earlier_source_unit.order_index < source_unit.order_index,
                    earlier_source_lesson.kind == "normal",
                    earlier_source_lesson_sentence.sentence_id == Sentence.id,
                )
                .exists(),
            )
            .order_by(Unit.order_index, Lesson.order_index, LessonSentence.order_index, Sentence.id)
        )

    def list_sentence_pool(self, *, unit_ids: list[str]) -> list[SentenceSelectionRow]:
        return [
            SentenceSelectionRow(
                sentence_id=row.sentence_id,
                source_unit_order_index=row.unit_order_index,
                source_lesson_order_index=row.lesson_order_index,
                source_sentence_order_index=row.sentence_order_index,
            )
            for row in self.db.execute(self._sentence_pool_query(unit_ids=unit_ids)).all()
        ]

    def list_word_pool(self, *, unit_ids: list[str]) -> list[WordPoolRow]:
        source_unit = aliased(Unit)
        earlier_source_unit = aliased(Unit)
        source_lesson = aliased(Lesson)
        earlier_source_lesson = aliased(Lesson)
        source_lesson_word = aliased(LessonWord)
        earlier_source_lesson_word = aliased(LessonWord)
        rows = self.db.execute(
            select(
                Word.id,
                Word.canonical_writing_ja,
                Word.intro_order,
                Word.is_safe_pool,
            )
            .join(source_lesson_word, source_lesson_word.word_id == Word.id)
            .join(source_lesson, source_lesson.id == source_lesson_word.lesson_id)
            .join(source_unit, source_unit.id == source_lesson.unit_id)
            .where(
                source_unit.id.in_(unit_ids),
                source_lesson.kind == "normal",
                source_lesson_word.role == "new",
                ~select(earlier_source_lesson_word.word_id)
                .join(earlier_source_lesson, earlier_source_lesson.id == earlier_source_lesson_word.lesson_id)
                .join(earlier_source_unit, earlier_source_unit.id == earlier_source_lesson.unit_id)
                .where(
                    earlier_source_unit.section_id == source_unit.section_id,
                    earlier_source_unit.order_index < source_unit.order_index,
                    earlier_source_lesson.kind == "normal",
                    earlier_source_lesson_word.role == "new",
                    earlier_source_lesson_word.word_id == source_lesson_word.word_id,
                )
                .exists(),
            )
            .order_by(Word.intro_order, Word.canonical_writing_ja)
        ).all()
        seen_word_ids: set[str] = set()
        pool: list[WordPoolRow] = []
        for row in rows:
            if row.id in seen_word_ids:
                continue
            seen_word_ids.add(row.id)
            pool.append(
                WordPoolRow(
                    word_id=row.id,
                    canonical_writing_ja=row.canonical_writing_ja,
                    intro_order=row.intro_order,
                    is_safe_pool=row.is_safe_pool,
                )
            )
        activation_word_rows = self.db.execute(
            select(Word.id, Word.canonical_writing_ja, Word.intro_order, Word.is_safe_pool)
            .join(LessonWord, LessonWord.word_id == Word.id)
            .join(Lesson, Lesson.id == LessonWord.lesson_id)
            .join(Unit, Unit.id == Lesson.unit_id)
            .join(PlannedUnit, (PlannedUnit.section_id == Unit.section_id) & (PlannedUnit.order_index == Unit.order_index))
            .join(PlannedLesson, (PlannedLesson.planned_unit_id == PlannedUnit.id) & (PlannedLesson.order_index == Lesson.order_index))
            .where(
                Unit.id.in_(unit_ids),
                Lesson.kind == "normal",
                PlannedLesson.kind == "kanji_activation",
            )
        ).all()
        for row in activation_word_rows:
            if row.id in seen_word_ids:
                continue
            seen_word_ids.add(row.id)
            pool.append(
                WordPoolRow(
                    word_id=row.id,
                    canonical_writing_ja=row.canonical_writing_ja,
                    intro_order=row.intro_order,
                    is_safe_pool=row.is_safe_pool,
                )
            )
        pool.sort(key=lambda row: (row.intro_order, row.canonical_writing_ja))
        return pool

    def list_pattern_pool(self, *, unit_ids: list[str]) -> list[PatternPoolRow]:
        source_unit = aliased(Unit)
        earlier_source_unit = aliased(Unit)
        source_unit_pattern_link = aliased(UnitPatternLink)
        earlier_source_unit_pattern_link = aliased(UnitPatternLink)
        rows = self.db.execute(
            select(
                Pattern.id,
                Pattern.code,
                Pattern.intro_order,
            )
            .join(source_unit_pattern_link, source_unit_pattern_link.pattern_id == Pattern.id)
            .join(source_unit, source_unit.id == source_unit_pattern_link.unit_id)
            .where(
                source_unit.id.in_(unit_ids),
                source_unit_pattern_link.role == "introduce",
                ~select(earlier_source_unit_pattern_link.pattern_id)
                .join(earlier_source_unit, earlier_source_unit.id == earlier_source_unit_pattern_link.unit_id)
                .where(
                    earlier_source_unit.section_id == source_unit.section_id,
                    earlier_source_unit.order_index < source_unit.order_index,
                    earlier_source_unit_pattern_link.role == "introduce",
                    earlier_source_unit_pattern_link.pattern_id == source_unit_pattern_link.pattern_id,
                )
                .exists(),
            )
            .order_by(Pattern.intro_order, Pattern.code)
        ).all()
        seen_pattern_ids: set[str] = set()
        pool: list[PatternPoolRow] = []
        for row in rows:
            if row.id in seen_pattern_ids:
                continue
            seen_pattern_ids.add(row.id)
            pool.append(
                PatternPoolRow(
                    pattern_id=row.id,
                    code=row.code,
                    intro_order=row.intro_order,
                )
            )
        return pool
