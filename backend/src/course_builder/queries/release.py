from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from course_builder.queries.shared import CourseVersionQueries
from domain.content.models import (
    CourseVersion,
    Item,
    ItemKanjiKanaMatch,
    ItemSentenceTiles,
    ItemWordChoice,
    Lesson,
    LessonPatternLink,
    LessonSentence,
    LessonWord,
    PlannedLesson,
    PlannedUnit,
    SectionPatternLink,
    SectionWord,
    Sentence,
    Unit,
    UnitPatternLink,
    Word,
)

EXPECTED_BIDIRECTIONAL_SENTENCE_ITEM_COUNT = 2


class ReleaseQueries(CourseVersionQueries):
    def list_lessons_for_unit(self, *, unit_id: str) -> list[Lesson]:
        return list(self.db.scalars(select(Lesson).where(Lesson.unit_id == unit_id).order_by(Lesson.order_index)).all())

    def count_items_for_lesson(self, *, lesson_id: str) -> int:
        return int(self.db.scalar(select(func.count()).select_from(Item).where(Item.lesson_id == lesson_id)) or 0)

    def count_items_missing_payloads_for_section(self, *, section_id: str) -> int:
        word_choice_missing = int(
            self.db.scalar(
                select(func.count())
                .select_from(Item)
                .join(Lesson, Lesson.id == Item.lesson_id)
                .join(Unit, Unit.id == Lesson.unit_id)
                .outerjoin(ItemWordChoice, ItemWordChoice.item_id == Item.id)
                .where(Unit.section_id == section_id, Item.type == "word_choice", ItemWordChoice.item_id.is_(None))
            )
            or 0
        )
        sentence_tiles_missing = int(
            self.db.scalar(
                select(func.count())
                .select_from(Item)
                .join(Lesson, Lesson.id == Item.lesson_id)
                .join(Unit, Unit.id == Lesson.unit_id)
                .outerjoin(ItemSentenceTiles, ItemSentenceTiles.item_id == Item.id)
                .where(
                    Unit.section_id == section_id, Item.type == "sentence_tiles", ItemSentenceTiles.item_id.is_(None)
                )
            )
            or 0
        )
        kanji_kana_missing = int(
            self.db.scalar(
                select(func.count())
                .select_from(Item)
                .join(Lesson, Lesson.id == Item.lesson_id)
                .join(Unit, Unit.id == Lesson.unit_id)
                .outerjoin(ItemKanjiKanaMatch, ItemKanjiKanaMatch.item_id == Item.id)
                .where(
                    Unit.section_id == section_id,
                    Item.type == "kanji_kana_match",
                    ItemKanjiKanaMatch.item_id.is_(None),
                )
            )
            or 0
        )
        return word_choice_missing + sentence_tiles_missing + kanji_kana_missing

    def list_active_course_versions_for_code(
        self,
        *,
        code: str,
        exclude_course_version_id: str,
    ) -> list[CourseVersion]:
        return list(
            self.db.scalars(
                select(CourseVersion).where(
                    CourseVersion.code == code,
                    CourseVersion.status == "active",
                    CourseVersion.id != exclude_course_version_id,
                )
            ).all()
        )

    def count_new_words_missing_word_choice_intro_for_section(self, *, section_id: str) -> int:
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(SectionWord)
                .join(Word, Word.id == SectionWord.word_id)
                .where(
                    SectionWord.section_id == section_id,
                    select(LessonWord.word_id)
                    .join(Lesson, Lesson.id == LessonWord.lesson_id)
                    .join(Unit, Unit.id == Lesson.unit_id)
                    .where(
                        Unit.section_id == section_id,
                        LessonWord.word_id == SectionWord.word_id,
                        LessonWord.role == "new",
                    )
                    .exists(),
                    ~select(ItemWordChoice.word_id)
                    .join(Item, Item.id == ItemWordChoice.item_id)
                    .join(Lesson, Lesson.id == Item.lesson_id)
                    .join(Unit, Unit.id == Lesson.unit_id)
                    .where(Unit.section_id == section_id, ItemWordChoice.word_id == SectionWord.word_id)
                    .exists(),
                )
            )
            or 0
        )

    def count_normal_lesson_sentences_never_surfaced_for_section(self, *, section_id: str) -> int:
        surfaced_sentence_exists = (
            select(ItemSentenceTiles.sentence_id)
            .join(Item, Item.id == ItemSentenceTiles.item_id)
            .join(Lesson, Lesson.id == Item.lesson_id)
            .join(Unit, Unit.id == Lesson.unit_id)
            .where(Unit.section_id == section_id, ItemSentenceTiles.sentence_id == Sentence.id)
            .exists()
        )
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(Sentence)
                .join(LessonSentence, LessonSentence.sentence_id == Sentence.id)
                .join(Lesson, Lesson.id == LessonSentence.lesson_id)
                .join(Unit, Unit.id == Lesson.unit_id)
                .where(Unit.section_id == section_id, Lesson.kind == "normal", ~surfaced_sentence_exists)
            )
            or 0
        )

    def count_words_with_multiple_normal_word_choice_intros_for_section(self, *, section_id: str) -> int:
        duplicate_word_ids = self.db.execute(
            select(ItemWordChoice.word_id)
            .join(Item, Item.id == ItemWordChoice.item_id)
            .join(Lesson, Lesson.id == Item.lesson_id)
            .join(Unit, Unit.id == Lesson.unit_id)
            .join(
                LessonWord,
                (
                    (LessonWord.lesson_id == Lesson.id)
                    & (LessonWord.word_id == ItemWordChoice.word_id)
                    & (LessonWord.role == "new")
                ),
            )
            .where(Unit.section_id == section_id, Lesson.kind == "normal", Item.type == "word_choice")
            .group_by(ItemWordChoice.word_id)
            .having(func.count() > 1)
        ).all()
        return len(duplicate_word_ids)

    def count_sentences_with_multiple_normal_intro_lessons_for_section(self, *, section_id: str) -> int:
        duplicate_sentence_ids = self.db.execute(
            select(ItemSentenceTiles.sentence_id)
            .join(Item, Item.id == ItemSentenceTiles.item_id)
            .join(Lesson, Lesson.id == Item.lesson_id)
            .join(Unit, Unit.id == Lesson.unit_id)
            .where(Unit.section_id == section_id, Lesson.kind == "normal", Item.type == "sentence_tiles")
            .group_by(ItemSentenceTiles.sentence_id)
            .having(func.count(func.distinct(Lesson.id)) > 1)
        ).all()
        return len(duplicate_sentence_ids)

    def count_normal_sentence_intros_missing_bidirectional_items_for_section(self, *, section_id: str) -> int:
        invalid_sentence_ids = self.db.execute(
            select(ItemSentenceTiles.sentence_id)
            .join(Item, Item.id == ItemSentenceTiles.item_id)
            .join(Lesson, Lesson.id == Item.lesson_id)
            .join(Unit, Unit.id == Lesson.unit_id)
            .where(Unit.section_id == section_id, Lesson.kind == "normal", Item.type == "sentence_tiles")
            .group_by(ItemSentenceTiles.sentence_id)
            .having(
                func.count() != EXPECTED_BIDIRECTIONAL_SENTENCE_ITEM_COUNT,
            )
        ).all()
        language_invalid_sentence_ids = self.db.execute(
            select(ItemSentenceTiles.sentence_id)
            .join(Item, Item.id == ItemSentenceTiles.item_id)
            .join(Lesson, Lesson.id == Item.lesson_id)
            .join(Unit, Unit.id == Lesson.unit_id)
            .where(Unit.section_id == section_id, Lesson.kind == "normal", Item.type == "sentence_tiles")
            .group_by(ItemSentenceTiles.sentence_id)
            .having(
                func.count(
                    func.distinct(
                        func.concat(Item.prompt_lang, "->", Item.answer_lang)
                    )
                )
                != EXPECTED_BIDIRECTIONAL_SENTENCE_ITEM_COUNT
            )
        ).all()
        invalid_sentence_id_set = {row[0] for row in invalid_sentence_ids}.union({row[0] for row in language_invalid_sentence_ids})
        return len(invalid_sentence_id_set)

    def count_section_sentences_missing_normal_lesson_intro(self, *, section_id: str) -> int:
        normal_lesson_intro_exists = (
            select(LessonSentence.sentence_id)
            .join(Lesson, Lesson.id == LessonSentence.lesson_id)
            .join(Unit, Unit.id == Lesson.unit_id)
            .where(Unit.section_id == section_id, Lesson.kind == "normal", LessonSentence.sentence_id == Sentence.id)
            .exists()
        )
        belongs_to_section = (
            select(SectionWord.word_id)
            .where(SectionWord.section_id == section_id, SectionWord.word_id == Sentence.target_word_id)
            .exists()
            | select(SectionPatternLink.pattern_id)
            .where(
                SectionPatternLink.section_id == section_id,
                SectionPatternLink.pattern_id == Sentence.target_pattern_id,
            )
            .exists()
        )
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(Sentence)
                .where(
                    Sentence.course_version_id == self.course_version_id,
                    belongs_to_section,
                    ~normal_lesson_intro_exists,
                )
            )
            or 0
        )

    def count_review_lessons_with_current_unit_content(self, *, section_id: str) -> int:
        normal_intro_lesson_word = aliased(LessonWord)
        earlier_normal_intro_lesson_word = aliased(LessonWord)
        intro_unit_pattern_link = aliased(UnitPatternLink)
        earlier_intro_unit_pattern_link = aliased(UnitPatternLink)
        normal_intro_lesson = aliased(Lesson)
        normal_intro_unit = aliased(Unit)
        earlier_normal_intro_lesson = aliased(Lesson)
        earlier_normal_intro_unit = aliased(Unit)
        intro_pattern_unit = aliased(Unit)
        earlier_intro_pattern_unit = aliased(Unit)
        source_lesson = aliased(Lesson)
        source_unit = aliased(Unit)
        current_unit_word_is_first_intro = (
            select(normal_intro_lesson_word.word_id)
            .join(normal_intro_lesson, normal_intro_lesson.id == normal_intro_lesson_word.lesson_id)
            .join(normal_intro_unit, normal_intro_unit.id == normal_intro_lesson.unit_id)
            .where(
                normal_intro_unit.section_id == section_id,
                normal_intro_unit.id == Lesson.unit_id,
                normal_intro_lesson.kind == "normal",
                normal_intro_lesson_word.role == "new",
                normal_intro_lesson_word.word_id == LessonWord.word_id,
                ~select(earlier_normal_intro_lesson_word.word_id)
                .join(earlier_normal_intro_lesson, earlier_normal_intro_lesson.id == earlier_normal_intro_lesson_word.lesson_id)
                .join(earlier_normal_intro_unit, earlier_normal_intro_unit.id == earlier_normal_intro_lesson.unit_id)
                .where(
                    earlier_normal_intro_unit.section_id == section_id,
                    earlier_normal_intro_unit.order_index < normal_intro_unit.order_index,
                    earlier_normal_intro_lesson.kind == "normal",
                    earlier_normal_intro_lesson_word.role == "new",
                    earlier_normal_intro_lesson_word.word_id == normal_intro_lesson_word.word_id,
                )
                .exists(),
            )
            .exists()
        )
        current_unit_pattern_is_first_intro = (
            select(intro_unit_pattern_link.pattern_id)
            .join(intro_pattern_unit, intro_pattern_unit.id == intro_unit_pattern_link.unit_id)
            .where(
                intro_pattern_unit.section_id == section_id,
                intro_pattern_unit.id == Lesson.unit_id,
                intro_unit_pattern_link.role == "introduce",
                intro_unit_pattern_link.pattern_id == LessonPatternLink.pattern_id,
                ~select(earlier_intro_unit_pattern_link.pattern_id)
                .join(earlier_intro_pattern_unit, earlier_intro_pattern_unit.id == earlier_intro_unit_pattern_link.unit_id)
                .where(
                    earlier_intro_pattern_unit.section_id == section_id,
                    earlier_intro_pattern_unit.order_index < intro_pattern_unit.order_index,
                    earlier_intro_unit_pattern_link.role == "introduce",
                    earlier_intro_unit_pattern_link.pattern_id == intro_unit_pattern_link.pattern_id,
                )
                .exists(),
            )
            .exists()
        )
        first_sentence_intro_unit_order = (
            select(source_unit.order_index)
            .select_from(LessonSentence)
            .join(source_lesson, source_lesson.id == LessonSentence.lesson_id)
            .join(source_unit, source_unit.id == source_lesson.unit_id)
            .where(
                source_unit.section_id == section_id,
                source_lesson.kind == "normal",
                LessonSentence.sentence_id == Sentence.id,
            )
            .order_by(source_unit.order_index, source_lesson.order_index, LessonSentence.order_index)
            .limit(1)
            .scalar_subquery()
        )
        review_word_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(LessonWord)
                .join(Lesson, Lesson.id == LessonWord.lesson_id)
                .join(Unit, Unit.id == Lesson.unit_id)
                .where(
                    Unit.section_id == section_id,
                    Unit.order_index > 1,
                    Lesson.kind == "review_previous_units",
                    current_unit_word_is_first_intro,
                )
            )
            or 0
        )
        review_pattern_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(LessonPatternLink)
                .join(Lesson, Lesson.id == LessonPatternLink.lesson_id)
                .join(Unit, Unit.id == Lesson.unit_id)
                .where(
                    Unit.section_id == section_id,
                    Unit.order_index > 1,
                    Lesson.kind == "review_previous_units",
                    current_unit_pattern_is_first_intro,
                )
            )
            or 0
        )
        review_sentence_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(LessonSentence)
                .join(Lesson, Lesson.id == LessonSentence.lesson_id)
                .join(Unit, Unit.id == Lesson.unit_id)
                .join(Sentence, Sentence.id == LessonSentence.sentence_id)
                .where(
                    Unit.section_id == section_id,
                    Unit.order_index > 1,
                    Lesson.kind == "review_previous_units",
                    first_sentence_intro_unit_order == Unit.order_index,
                )
            )
            or 0
        )
        return review_word_count + review_pattern_count + review_sentence_count

    def count_exam_lessons_with_previous_unit_content(self, *, section_id: str) -> int:
        normal_intro_lesson_word = aliased(LessonWord)
        earlier_normal_intro_lesson_word = aliased(LessonWord)
        activation_lesson_word = aliased(LessonWord)
        intro_unit_pattern_link = aliased(UnitPatternLink)
        earlier_intro_unit_pattern_link = aliased(UnitPatternLink)
        normal_intro_lesson = aliased(Lesson)
        normal_intro_unit = aliased(Unit)
        earlier_normal_intro_lesson = aliased(Lesson)
        earlier_normal_intro_unit = aliased(Unit)
        activation_lesson = aliased(Lesson)
        activation_unit = aliased(Unit)
        activation_planned_unit = aliased(PlannedUnit)
        activation_planned_lesson = aliased(PlannedLesson)
        intro_pattern_unit = aliased(Unit)
        earlier_intro_pattern_unit = aliased(Unit)
        source_lesson = aliased(Lesson)
        source_unit = aliased(Unit)
        current_unit_word_is_first_intro = (
            select(normal_intro_lesson_word.word_id)
            .join(normal_intro_lesson, normal_intro_lesson.id == normal_intro_lesson_word.lesson_id)
            .join(normal_intro_unit, normal_intro_unit.id == normal_intro_lesson.unit_id)
            .where(
                normal_intro_unit.section_id == section_id,
                normal_intro_unit.id == Lesson.unit_id,
                normal_intro_lesson.kind == "normal",
                normal_intro_lesson_word.role == "new",
                normal_intro_lesson_word.word_id == LessonWord.word_id,
                ~select(earlier_normal_intro_lesson_word.word_id)
                .join(earlier_normal_intro_lesson, earlier_normal_intro_lesson.id == earlier_normal_intro_lesson_word.lesson_id)
                .join(earlier_normal_intro_unit, earlier_normal_intro_unit.id == earlier_normal_intro_lesson.unit_id)
                .where(
                    earlier_normal_intro_unit.section_id == section_id,
                    earlier_normal_intro_unit.order_index < normal_intro_unit.order_index,
                    earlier_normal_intro_lesson.kind == "normal",
                    earlier_normal_intro_lesson_word.role == "new",
                    earlier_normal_intro_lesson_word.word_id == normal_intro_lesson_word.word_id,
                )
                .exists(),
            )
            .exists()
        )
        current_unit_word_is_kanji_activation = (
            select(activation_lesson_word.word_id)
            .join(activation_lesson, activation_lesson.id == activation_lesson_word.lesson_id)
            .join(activation_unit, activation_unit.id == activation_lesson.unit_id)
            .join(
                activation_planned_unit,
                (activation_planned_unit.section_id == activation_unit.section_id)
                & (activation_planned_unit.order_index == activation_unit.order_index),
            )
            .join(
                activation_planned_lesson,
                (activation_planned_lesson.planned_unit_id == activation_planned_unit.id)
                & (activation_planned_lesson.order_index == activation_lesson.order_index),
            )
            .where(
                activation_unit.section_id == section_id,
                activation_unit.id == Lesson.unit_id,
                activation_lesson.kind == "normal",
                activation_planned_lesson.kind == "kanji_activation",
                activation_lesson_word.word_id == LessonWord.word_id,
            )
            .exists()
        )
        current_unit_pattern_is_first_intro = (
            select(intro_unit_pattern_link.pattern_id)
            .join(intro_pattern_unit, intro_pattern_unit.id == intro_unit_pattern_link.unit_id)
            .where(
                intro_pattern_unit.section_id == section_id,
                intro_pattern_unit.id == Lesson.unit_id,
                intro_unit_pattern_link.role == "introduce",
                intro_unit_pattern_link.pattern_id == LessonPatternLink.pattern_id,
                ~select(earlier_intro_unit_pattern_link.pattern_id)
                .join(earlier_intro_pattern_unit, earlier_intro_pattern_unit.id == earlier_intro_unit_pattern_link.unit_id)
                .where(
                    earlier_intro_pattern_unit.section_id == section_id,
                    earlier_intro_pattern_unit.order_index < intro_pattern_unit.order_index,
                    earlier_intro_unit_pattern_link.role == "introduce",
                    earlier_intro_unit_pattern_link.pattern_id == intro_unit_pattern_link.pattern_id,
                )
                .exists(),
            )
            .exists()
        )
        first_sentence_intro_unit_order = (
            select(source_unit.order_index)
            .select_from(LessonSentence)
            .join(source_lesson, source_lesson.id == LessonSentence.lesson_id)
            .join(source_unit, source_unit.id == source_lesson.unit_id)
            .where(
                source_unit.section_id == section_id,
                source_lesson.kind == "normal",
                LessonSentence.sentence_id == Sentence.id,
            )
            .order_by(source_unit.order_index, source_lesson.order_index, LessonSentence.order_index)
            .limit(1)
            .scalar_subquery()
        )
        exam_word_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(LessonWord)
                .join(Lesson, Lesson.id == LessonWord.lesson_id)
                .join(Unit, Unit.id == Lesson.unit_id)
                .where(
                    Unit.section_id == section_id,
                    Lesson.kind == "exam",
                    ~(current_unit_word_is_first_intro | current_unit_word_is_kanji_activation),
                )
            )
            or 0
        )
        exam_pattern_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(LessonPatternLink)
                .join(Lesson, Lesson.id == LessonPatternLink.lesson_id)
                .join(Unit, Unit.id == Lesson.unit_id)
                .where(Unit.section_id == section_id, Lesson.kind == "exam", ~current_unit_pattern_is_first_intro)
            )
            or 0
        )
        exam_sentence_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(LessonSentence)
                .join(Lesson, Lesson.id == LessonSentence.lesson_id)
                .join(Unit, Unit.id == Lesson.unit_id)
                .join(Sentence, Sentence.id == LessonSentence.sentence_id)
                .where(
                    Unit.section_id == section_id,
                    Lesson.kind == "exam",
                    first_sentence_intro_unit_order != Unit.order_index,
                )
            )
            or 0
        )
        return exam_word_count + exam_pattern_count + exam_sentence_count
