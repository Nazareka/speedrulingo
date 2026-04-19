from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from sqlalchemy import func, select

from course_builder.engine.models import BuildContext
from course_builder.llm.core.models import ExistingWordPromptInfo
from course_builder.queries.shared import CourseVersionQueries
from domain.content.models import (
    Lesson,
    LessonSentence,
    Pattern,
    PlannedLesson,
    PlannedUnit,
    Section,
    SectionPatternLink,
    SectionWord,
    Sentence,
    SentencePatternLink,
    SentenceUnit,
    SentenceWordLink,
    ThemeTag,
    Unit,
    Word,
    WordThemeLink,
)


@dataclass(frozen=True, slots=True)
class CurriculumWord:
    word_id: str
    canonical_writing_ja: str
    reading_kana: str
    pos: str
    intro_order: int
    source_kind: str = "manual"
    generation_pipeline: str | None = None
    theme_codes: tuple[str, ...] = ()
    example_pattern_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CurriculumPatternExample:
    pattern_code: str
    ja_text: str
    en_text: str
    lexicon_used: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True, slots=True)
class CurriculumPattern:
    pattern_id: str
    code: str
    name: str
    templates: tuple[str, ...]
    short_description: str
    intro_order: int
    examples: tuple[CurriculumPatternExample, ...]
    min_extra_words: int | None = None
    max_extra_words: int | None = None


@dataclass(frozen=True, slots=True)
class CurriculumLesson:
    lesson_index_within_unit: int
    kind: str
    lesson_kind: str
    force_kana_display: bool
    target_item_count: int
    introduced_word_lemmas: tuple[str, ...]
    kanji_focus_word_lemmas: tuple[str, ...]
    target_word_lemmas: tuple[str, ...]
    target_pattern_codes: tuple[str, ...]
    target_pattern_code: str | None
    target_pattern_examples: tuple[CurriculumPatternExample, ...]
    available_word_lemmas: tuple[str, ...]
    available_pattern_codes: tuple[str, ...]
    target_pattern_sentence_count: int


@dataclass(frozen=True, slots=True)
class CurriculumUnit:
    order_index: int
    primary_theme_codes: tuple[str, ...]
    pattern_codes: tuple[str, ...]
    lessons: tuple[CurriculumLesson, ...]


@dataclass(frozen=True, slots=True)
class SectionCurriculumPlan:
    units: tuple[CurriculumUnit, ...]


@dataclass(frozen=True, slots=True)
class LessonWithPlan:
    lesson: Lesson
    unit_order_index: int
    planned_lesson: CurriculumLesson


@dataclass(frozen=True, slots=True)
class ExistingCourseSentenceData:
    sentences_by_key: dict[tuple[str, str, str | None, str | None], Sentence]
    sentence_word_link_keys: set[tuple[str, str]]
    sentence_pattern_link_keys: set[tuple[str, str]]
    sentence_unit_keys: set[tuple[str, str, int]]


@dataclass(frozen=True, slots=True)
class GeneratedWordSentenceRow:
    sentence_id: str
    target_word_id: str
    canonical_writing_ja: str


class PlanningQueries(CourseVersionQueries):
    def list_curriculum_words(self) -> list[CurriculumWord]:
        example_pattern_codes_by_word_id: dict[str, tuple[str, ...]] = {}
        for row in self.db.execute(
            select(Sentence.target_word_id, Pattern.code)
            .join(SentencePatternLink, SentencePatternLink.sentence_id == Sentence.id)
            .join(Pattern, Pattern.id == SentencePatternLink.pattern_id)
            .where(
                Sentence.course_version_id == self.course_version_id,
                Sentence.target_word_id.is_not(None),
            )
            .order_by(Sentence.target_word_id, Pattern.code)
        ).all():
            if row.target_word_id is None:
                continue
            existing_codes = example_pattern_codes_by_word_id.get(row.target_word_id, ())
            example_pattern_codes_by_word_id[row.target_word_id] = tuple(dict.fromkeys([*existing_codes, row.code]))

        theme_codes_by_word_id: dict[str, tuple[str, ...]] = {}
        for theme_row in self.db.execute(
            select(WordThemeLink.word_id, ThemeTag.code)
            .join(ThemeTag, ThemeTag.id == WordThemeLink.theme_tag_id)
            .join(Word, Word.id == WordThemeLink.word_id)
            .where(Word.course_version_id == self.course_version_id)
            .order_by(WordThemeLink.word_id, ThemeTag.code)
        ).all():
            existing_codes = theme_codes_by_word_id.get(theme_row.word_id, ())
            theme_codes_by_word_id[theme_row.word_id] = tuple(dict.fromkeys([*existing_codes, theme_row.code]))

        return [
            CurriculumWord(
                word_id=row.id,
                canonical_writing_ja=row.canonical_writing_ja,
                reading_kana=row.reading_kana,
                pos=row.pos,
                intro_order=row.intro_order,
                source_kind=row.source_kind,
                generation_pipeline=row.generation_pipeline,
                theme_codes=theme_codes_by_word_id.get(row.id, ()),
                example_pattern_codes=example_pattern_codes_by_word_id.get(row.id, ()),
            )
            for row in self.db.execute(
                select(
                    Word.id,
                    Word.canonical_writing_ja,
                    Word.reading_kana,
                    Word.pos,
                    Word.intro_order,
                    Word.source_kind,
                    Word.generation_pipeline,
                )
                .where(Word.course_version_id == self.course_version_id)
                .order_by(Word.intro_order)
            ).all()
        ]

    def list_curriculum_patterns(self, *, context: BuildContext) -> list[CurriculumPattern]:
        pattern_config_by_code = {pattern.code: pattern for pattern in context.config.patterns}
        scoped_codes = set(context.config.current_section.patterns_scope)
        return [
            CurriculumPattern(
                pattern_id=row.id,
                code=row.code,
                name=row.name,
                templates=tuple(pattern_config_by_code[row.code].templates),
                short_description=row.short_description,
                intro_order=row.intro_order,
                examples=tuple(
                    CurriculumPatternExample(
                        pattern_code=row.code,
                        ja_text=example.ja,
                        en_text=example.en,
                        lexicon_used=tuple(
                            (
                                lexeme.canonical_writing_ja,
                                lexeme.reading_kana,
                                lexeme.pos.value,
                            )
                            for lexeme in example.lexicon_used
                        ),
                    )
                    for example in pattern_config_by_code[row.code].examples
                ),
                min_extra_words=pattern_config_by_code[row.code].min_extra_words,
                max_extra_words=pattern_config_by_code[row.code].max_extra_words,
            )
            for row in self.db.execute(
                select(
                    Pattern.id,
                    Pattern.code,
                    Pattern.name,
                    Pattern.short_description,
                    Pattern.intro_order,
                )
                .where(
                    Pattern.course_version_id == context.course_version_id,
                    Pattern.code.in_(scoped_codes),
                )
                .order_by(Pattern.intro_order)
            ).all()
        ]

    def map_generated_sentence_count_by_target_lemma_for_section(self) -> dict[str, int]:
        section_id = self.get_section_id()
        if section_id is None:
            return {}
        rows = self.db.execute(
            select(Word.canonical_writing_ja, func.count(Sentence.id))
            .join(Sentence, Sentence.target_word_id == Word.id)
            .join(SectionWord, SectionWord.word_id == Word.id)
            .where(SectionWord.section_id == section_id)
            .group_by(Word.canonical_writing_ja)
        ).all()
        return {row[0]: int(row[1]) for row in rows}

    def list_generated_word_sentences_for_section(self) -> list[GeneratedWordSentenceRow]:
        section_id = self.get_section_id()
        if section_id is None:
            return []
        return [
            GeneratedWordSentenceRow(
                sentence_id=row.sentence_id,
                target_word_id=row.target_word_id,
                canonical_writing_ja=row.canonical_writing_ja,
            )
            for row in self.db.execute(
                select(
                    Sentence.id.label("sentence_id"),
                    Word.id.label("target_word_id"),
                    Word.canonical_writing_ja,
                )
                .join(Word, Word.id == Sentence.target_word_id)
                .join(SectionWord, SectionWord.word_id == Word.id)
                .where(SectionWord.section_id == section_id)
                .order_by(Word.intro_order, Sentence.id)
            ).all()
        ]

    def exists_planned_units(self) -> bool:
        section_id = self.get_section_id()
        if section_id is None:
            return False
        return self.db.scalar(select(PlannedUnit.id).where(PlannedUnit.section_id == section_id).limit(1)) is not None

    def load_section_curriculum_plan(self) -> SectionCurriculumPlan:
        section_id = self.get_section_id()
        if section_id is None:
            return SectionCurriculumPlan(units=())
        planned_units = list(
            self.db.scalars(
                select(PlannedUnit).where(PlannedUnit.section_id == section_id).order_by(PlannedUnit.order_index)
            )
        )
        if not planned_units:
            return SectionCurriculumPlan(units=())

        lessons_by_unit_id: dict[str, list[PlannedLesson]] = {}
        for planned_lesson in self.db.scalars(
            select(PlannedLesson)
            .where(PlannedLesson.planned_unit_id.in_([planned_unit.id for planned_unit in planned_units]))
            .order_by(PlannedLesson.planned_unit_id, PlannedLesson.order_index)
        ):
            lessons_by_unit_id.setdefault(planned_lesson.planned_unit_id, []).append(planned_lesson)

        def _parse_pattern_examples(examples: list[dict[str, object]]) -> tuple[CurriculumPatternExample, ...]:
            return tuple(
                CurriculumPatternExample(
                    pattern_code=cast(str, example["pattern_code"]),
                    ja_text=cast(str, example["ja_text"]),
                    en_text=cast(str, example["en_text"]),
                    lexicon_used=tuple(
                        (
                            str(lexeme[0]),
                            str(lexeme[1]),
                            str(lexeme[2]),
                        )
                        for lexeme in cast(list[list[object]], example["lexicon_used"])
                    ),
                )
                for example in examples
            )

        return SectionCurriculumPlan(
            units=tuple(
                CurriculumUnit(
                    order_index=planned_unit.order_index,
                    primary_theme_codes=tuple(planned_unit.primary_theme_codes),
                    pattern_codes=tuple(planned_unit.pattern_codes),
                    lessons=tuple(
                        CurriculumLesson(
                            lesson_index_within_unit=planned_lesson.order_index,
                            kind="normal",
                            lesson_kind=planned_lesson.kind,
                            force_kana_display=planned_lesson.force_kana_display,
                            target_item_count=planned_lesson.target_item_count,
                            introduced_word_lemmas=tuple(planned_lesson.introduced_word_lemmas),
                            kanji_focus_word_lemmas=tuple(planned_lesson.kanji_focus_word_lemmas),
                            target_word_lemmas=tuple(planned_lesson.target_word_lemmas),
                            target_pattern_codes=tuple(planned_lesson.target_pattern_codes),
                            target_pattern_code=planned_lesson.target_pattern_code,
                            target_pattern_examples=_parse_pattern_examples(planned_lesson.target_pattern_examples),
                            available_word_lemmas=tuple(planned_lesson.available_word_lemmas),
                            available_pattern_codes=tuple(planned_lesson.available_pattern_codes),
                            target_pattern_sentence_count=planned_lesson.target_pattern_sentence_count,
                        )
                        for planned_lesson in lessons_by_unit_id.get(planned_unit.id, [])
                    ),
                )
                for planned_unit in planned_units
            )
        )

    def list_normal_lessons_with_unit_order(self) -> list[tuple[Lesson, int]]:
        rows = self.db.execute(
            select(Lesson, Unit.order_index)
            .join(Unit, Unit.id == Lesson.unit_id)
            .join(Section, Section.id == Unit.section_id)
            .where(
                Section.course_version_id == self.course_version_id,
                Section.code == self.section_code,
                Lesson.kind == "normal",
            )
            .order_by(Unit.order_index, Lesson.order_index)
        )
        return [(row[0], row[1]) for row in rows]

    def list_previously_introduced_pattern_codes(self) -> list[str]:
        current_section = self.get_section()
        if current_section is None:
            return []
        return list(
            self.db.scalars(
                select(Pattern.code)
                .join(SectionPatternLink, SectionPatternLink.pattern_id == Pattern.id)
                .join(Section, Section.id == SectionPatternLink.section_id)
                .where(
                    Section.course_version_id == self.course_version_id,
                    Section.order_index < current_section.order_index,
                )
                .order_by(Pattern.intro_order)
            )
        )

    def list_previously_introduced_word_lemmas(self) -> list[str]:
        current_section = self.get_section()
        if current_section is None:
            return []
        return list(
            self.db.scalars(
                select(Word.canonical_writing_ja)
                .join(SectionWord, SectionWord.word_id == Word.id)
                .join(Section, Section.id == SectionWord.section_id)
                .where(
                    Section.course_version_id == self.course_version_id,
                    Section.order_index < current_section.order_index,
                )
                .order_by(Word.intro_order)
            )
        )

    def list_current_section_bootstrap_expression_lemmas(self) -> list[str]:
        section_id = self.get_section_id()
        if section_id is None:
            return []
        return list(
            self.db.scalars(
                select(Word.canonical_writing_ja)
                .join(SectionWord, SectionWord.word_id == Word.id)
                .where(
                    SectionWord.section_id == section_id,
                    Word.source_kind == "manual_seed",
                    Word.pos == "expression",
                )
                .order_by(Word.intro_order)
            )
        )

    def exists_normal_lessons_for_section(self, *, section_id: str) -> bool:
        return (
            self.db.scalar(
                select(Lesson.id).join(Unit, Unit.id == Lesson.unit_id).where(Unit.section_id == section_id).limit(1)
            )
            is not None
        )

    def exists_units_for_section(self, *, section_id: str) -> bool:
        return self.db.scalar(select(Unit.id).where(Unit.section_id == section_id).limit(1)) is not None

    def map_word_id_by_form(self) -> dict[tuple[str, str], str]:
        return {
            (row.canonical_writing_ja, row.reading_kana): row.id
            for row in self.db.execute(
                select(Word.id, Word.canonical_writing_ja, Word.reading_kana).where(
                    Word.course_version_id == self.course_version_id
                )
            ).all()
        }

    def map_prompt_word_line_inputs_by_lemma(self) -> dict[str, ExistingWordPromptInfo]:
        return {
            row.canonical_writing_ja: ExistingWordPromptInfo(
                canonical_writing_ja=row.canonical_writing_ja,
                reading_kana=row.reading_kana,
                gloss_primary_en=row.gloss_primary_en,
                gloss_alternatives_en=row.gloss_alternatives_en,
                usage_note_en=row.usage_note_en,
                pos=row.pos,
            )
            for row in self.db.execute(
                select(
                    Word.canonical_writing_ja,
                    Word.reading_kana,
                    Word.gloss_primary_en,
                    Word.gloss_alternatives_en,
                    Word.usage_note_en,
                    Word.pos,
                ).where(Word.course_version_id == self.course_version_id)
            ).all()
        }

    def list_existing_word_prompt_info(self) -> list[ExistingWordPromptInfo]:
        return [
            ExistingWordPromptInfo(
                canonical_writing_ja=row.canonical_writing_ja,
                reading_kana=row.reading_kana,
                gloss_primary_en=row.gloss_primary_en,
                gloss_alternatives_en=row.gloss_alternatives_en,
                usage_note_en=row.usage_note_en,
                pos=row.pos,
            )
            for row in self.db.execute(
                select(
                    Word.canonical_writing_ja,
                    Word.reading_kana,
                    Word.gloss_primary_en,
                    Word.gloss_alternatives_en,
                    Word.usage_note_en,
                    Word.pos,
                )
                .where(Word.course_version_id == self.course_version_id)
                .order_by(Word.intro_order)
            ).all()
        ]

    def list_existing_word_pos_triplets(self) -> set[tuple[str, str, str]]:
        return {
            (row.canonical_writing_ja, row.reading_kana, row.pos)
            for row in self.db.execute(
                select(Word.canonical_writing_ja, Word.reading_kana, Word.pos).where(
                    Word.course_version_id == self.course_version_id
                )
            ).all()
        }

    def list_existing_word_pairs(self) -> set[tuple[str, str]]:
        return {
            (row.canonical_writing_ja, row.reading_kana)
            for row in self.db.execute(
                select(Word.canonical_writing_ja, Word.reading_kana).where(
                    Word.course_version_id == self.course_version_id
                )
            ).all()
        }

    def get_next_word_intro_order(self) -> int:
        return (
            int(
                self.db.scalar(
                    select(Word.intro_order)
                    .where(Word.course_version_id == self.course_version_id)
                    .order_by(Word.intro_order.desc())
                    .limit(1)
                )
                or 0
            )
            + 1
        )

    def load_existing_course_sentence_data(self) -> ExistingCourseSentenceData:
        sentences_by_key = {
            (row.ja_text, row.en_text, row.target_word_id, row.target_pattern_id): row
            for row in self.db.execute(
                select(Sentence).where(Sentence.course_version_id == self.course_version_id)
            ).scalars()
        }
        sentence_ids = [row.id for row in sentences_by_key.values()]
        sentence_word_link_keys = {
            (row.sentence_id, row.word_id)
            for row in self.db.execute(
                select(SentenceWordLink.sentence_id, SentenceWordLink.word_id).where(
                    SentenceWordLink.sentence_id.in_(sentence_ids)
                )
            ).all()
        }
        sentence_pattern_link_keys = {
            (row.sentence_id, row.pattern_id)
            for row in self.db.execute(
                select(SentencePatternLink.sentence_id, SentencePatternLink.pattern_id).where(
                    SentencePatternLink.sentence_id.in_(sentence_ids)
                )
            ).all()
        }
        sentence_unit_keys = {
            (row.sentence_id, row.lang, row.unit_index)
            for row in self.db.execute(
                select(SentenceUnit.sentence_id, SentenceUnit.lang, SentenceUnit.unit_index).where(
                    SentenceUnit.sentence_id.in_(sentence_ids)
                )
            ).all()
        }
        return ExistingCourseSentenceData(
            sentences_by_key=sentences_by_key,
            sentence_word_link_keys=sentence_word_link_keys,
            sentence_pattern_link_keys=sentence_pattern_link_keys,
            sentence_unit_keys=sentence_unit_keys,
        )

    def list_lesson_sentence_keys(self, *, lesson_ids: list[str]) -> set[tuple[str, str]]:
        if not lesson_ids:
            return set()
        return {
            (row.lesson_id, row.sentence_id)
            for row in self.db.execute(
                select(LessonSentence.lesson_id, LessonSentence.sentence_id).where(
                    LessonSentence.lesson_id.in_(lesson_ids)
                )
            ).all()
        }

    def list_word_rows_for_sentence_matching(self) -> list[tuple[str, str, str, str, str, tuple[str, ...], str | None]]:
        return [
            (
                row.id,
                row.canonical_writing_ja,
                row.reading_kana,
                row.pos,
                row.gloss_primary_en,
                tuple(row.gloss_alternatives_en),
                row.usage_note_en,
            )
            for row in self.db.execute(
                select(
                    Word.id,
                    Word.canonical_writing_ja,
                    Word.reading_kana,
                    Word.pos,
                    Word.gloss_primary_en,
                    Word.gloss_alternatives_en,
                    Word.usage_note_en,
                )
                .where(Word.course_version_id == self.course_version_id)
                .order_by(Word.intro_order)
            ).all()
        ]

    def list_generated_words_by_canonical_writing(self, *, canonical_writings: list[str]) -> list[Word]:
        if not canonical_writings:
            return []
        return list(
            self.db.execute(
                select(Word).where(
                    Word.course_version_id == self.course_version_id,
                    Word.canonical_writing_ja.in_(canonical_writings),
                )
            ).scalars()
        )
