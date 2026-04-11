from __future__ import annotations

from dataclasses import dataclass
from typing import override

from sqlalchemy.orm import Session

from course_builder.engine.models import BuildContext, BuildStep
from course_builder.stages.assembly.hints_and_kanji_introductions import build_hints_and_kanji_introductions
from course_builder.stages.assembly.lesson_item_generation import generate_lesson_items
from course_builder.stages.assembly.pattern_example_sentences import persist_pattern_example_sentences
from course_builder.stages.assembly.review_exam_lesson_creation import create_algorithmic_review_exam_lessons
from course_builder.stages.assembly.tile_generation import build_tile_sets


@dataclass(frozen=True, slots=True)
class ContentAssemblyStageStats:
    pattern_example_sentences_created: int
    pattern_example_attachments_created: int
    pattern_example_sentence_units_created: int
    tile_sets_created: int
    tiles_created: int
    lessons_created: int
    review_lessons_created: int
    exam_lessons_created: int
    lesson_words_created: int
    lesson_pattern_links_created: int
    review_exam_sentence_attachments_created: int
    items_created: int
    word_choice_items_created: int
    sentence_tiles_items_created: int
    kanji_kana_match_items_created: int
    sentence_unit_hints_created: int
    kanji_created: int
    word_kanji_links_created: int
    kanji_introductions_created: int


def run_content_assembly_stage(db: Session, *, context: BuildContext) -> ContentAssemblyStageStats:
    pattern_example_stats = persist_pattern_example_sentences(db, context=context)
    review_exam_stats = create_algorithmic_review_exam_lessons(db, context=context)
    tile_stats = build_tile_sets(db, context=context)
    item_stats = generate_lesson_items(db, context=context)
    hint_stats = build_hints_and_kanji_introductions(db, context=context)
    return ContentAssemblyStageStats(
        pattern_example_sentences_created=pattern_example_stats.sentences_created,
        pattern_example_attachments_created=pattern_example_stats.lesson_attachments_created,
        pattern_example_sentence_units_created=pattern_example_stats.sentence_units_created,
        tile_sets_created=tile_stats.tile_sets_created,
        tiles_created=tile_stats.tiles_created,
        lessons_created=review_exam_stats.lessons_created,
        review_lessons_created=review_exam_stats.review_lessons_created,
        exam_lessons_created=review_exam_stats.exam_lessons_created,
        lesson_words_created=review_exam_stats.lesson_words_created,
        lesson_pattern_links_created=review_exam_stats.lesson_pattern_links_created,
        review_exam_sentence_attachments_created=review_exam_stats.lesson_sentences_created,
        items_created=item_stats.items_created,
        word_choice_items_created=item_stats.word_choice_items_created,
        sentence_tiles_items_created=item_stats.sentence_tiles_items_created,
        kanji_kana_match_items_created=item_stats.kanji_kana_match_items_created,
        sentence_unit_hints_created=hint_stats.sentence_unit_hints_created,
        kanji_created=hint_stats.kanji_created,
        word_kanji_links_created=hint_stats.word_kanji_links_created,
        kanji_introductions_created=hint_stats.kanji_introductions_created,
    )


class ContentAssemblyStage(BuildStep):
    name = "content_assembly"

    @override
    def run(self, *, db: Session, context: BuildContext) -> ContentAssemblyStageStats:
        return run_content_assembly_stage(db, context=context)
