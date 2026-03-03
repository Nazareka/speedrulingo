from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from course_builder.config import CourseBuildConfig, SectionPlanningConfig
from course_builder.lexicon import LexemePos
from course_builder.queries.planning import (
    CurriculumLesson,
    CurriculumPattern,
    CurriculumPatternExample,
    CurriculumUnit,
    CurriculumWord,
    LessonWithPlan,
    PlanningQueries,
    SectionCurriculumPlan,
)
from course_builder.runtime.models import BuildContext

NONPATTERN_BUNDLE_CODES = {"BOOTSTRAP_SUPPORT_ONLY", "SECTION_LEXICAL_EXPANSION"}
KANJI_TRANSITION_PATTERN_THRESHOLD = 3
MIN_NORMAL_LESSONS_PER_UNIT = 2
MAX_NORMAL_LESSONS_PER_UNIT = 3
KANJI_ACTIVATION_WORDS_PER_LESSON = 5


@dataclass(frozen=True, slots=True)
class PatternBundle:
    pattern_code: str
    support_lemmas: tuple[str, ...]
    anchor_lemmas: tuple[str, ...]
    core_lemmas: tuple[str, ...]
    extra_lemmas: tuple[str, ...]
    new_word_lemmas: tuple[str, ...]
    word_choice_intro_lemmas: tuple[str, ...]
    examples: tuple[CurriculumPatternExample, ...]
    primary_theme_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PlannedLessonWave:
    lesson_kind: str
    force_kana_display: bool
    introduced_word_lemmas: tuple[str, ...]
    kanji_focus_word_lemmas: tuple[str, ...]
    target_word_lemmas: tuple[str, ...]
    target_pattern_codes: tuple[str, ...]
    target_pattern_code: str | None
    target_pattern_examples: tuple[CurriculumPatternExample, ...]
    available_word_lemmas: tuple[str, ...]
    available_pattern_codes: tuple[str, ...]
    target_item_count: int


def _ordered_unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _origin_pattern_code(*, source_kind: str) -> str | None:
    prefix = "pattern:"
    if source_kind.startswith(prefix):
        return source_kind[len(prefix) :]
    return None


def _is_nonverb_kanji_word(*, word: CurriculumWord) -> bool:
    if word.pos == "verb":
        return False
    return word.reading_kana != word.canonical_writing_ja and any(
        "\u4e00" <= char <= "\u9fff" or "\u3400" <= char <= "\u4dbf" or "\uf900" <= char <= "\ufaff"
        for char in word.canonical_writing_ja
    )


def _bundle_theme_codes(
    *,
    bundle_words: list[CurriculumWord],
    fallback_primary_themes: list[str],
) -> tuple[str, ...]:
    theme_scores: dict[str, int] = {}
    for word in bundle_words:
        for theme_code in word.theme_codes:
            theme_scores[theme_code] = theme_scores.get(theme_code, 0) + 1
    if not theme_scores:
        return tuple(fallback_primary_themes[:1])
    return tuple(
        code for code, score in sorted(theme_scores.items(), key=lambda item: (-item[1], item[0])) if score > 0
    )[:2]


def _sentence_count_for_bundle(
    *,
    bundle: PatternBundle,
    generated_sentence_count_by_lemma: dict[str, int],
) -> int:
    return len(bundle.examples) + sum(
        generated_sentence_count_by_lemma.get(lemma, 0) for lemma in bundle.word_choice_intro_lemmas
    )


def _split_sentence_introductions(
    *,
    sentence_count: int,
    min_per_lesson: int,
    max_per_lesson: int,
) -> list[int]:
    if sentence_count <= 0:
        return [0]
    lesson_count = max(1, ceil(sentence_count / max_per_lesson))
    base = sentence_count // lesson_count
    remainder = sentence_count % lesson_count
    counts = [base + (1 if index < remainder else 0) for index in range(lesson_count)]
    if lesson_count == 1 or all(count >= min_per_lesson for count in counts):
        return counts
    return counts


def build_pattern_bundles(
    *,
    config: CourseBuildConfig,
    words: list[CurriculumWord],
    patterns: list[CurriculumPattern],
    previously_introduced_word_lemmas: list[str],
    current_section_bootstrap_expression_lemmas: list[str],
) -> list[PatternBundle]:
    words_by_lemma = {word.canonical_writing_ja: word for word in words if not LexemePos.is_support(word.pos)}
    config_patterns_by_code = {pattern.code: pattern for pattern in config.patterns}
    known_word_lemmas = set(previously_introduced_word_lemmas)
    bundles: list[PatternBundle] = []

    if (
        config.sections.is_first(config.current_section_code)
        and config.current_section.section_planning.bootstrap_mode == "support_only"
        and current_section_bootstrap_expression_lemmas
    ):
        expression_lemmas = _ordered_unique(current_section_bootstrap_expression_lemmas)
        bundles.append(
            PatternBundle(
                pattern_code="BOOTSTRAP_SUPPORT_ONLY",
                support_lemmas=(),
                anchor_lemmas=(),
                core_lemmas=expression_lemmas,
                extra_lemmas=(),
                new_word_lemmas=expression_lemmas,
                word_choice_intro_lemmas=expression_lemmas,
                examples=(),
                primary_theme_codes=tuple(config.current_section.primary_themes[:1]),
            )
        )
        known_word_lemmas.update(expression_lemmas)

    for pattern in patterns:
        config_pattern = config_patterns_by_code[pattern.code]
        support_lemmas = _ordered_unique(list(config_pattern.required_support_forms))
        anchor_lemmas = _ordered_unique(
            [
                *[ref.canonical_writing_ja for ref in config_pattern.anchor_word_refs],
                *[ref.canonical_writing_ja for ref in config_pattern.required_lexical_refs],
            ]
        )
        example_lexical_lemmas = _ordered_unique(
            [
                canonical_writing_ja
                for example in pattern.examples
                for canonical_writing_ja, _reading_kana, pos in example.lexicon_used
                if not LexemePos.is_support(pos)
            ]
        )
        generated_stage_lemmas = _ordered_unique(
            [
                word.canonical_writing_ja
                for word in words_by_lemma.values()
                if not word.is_bootstrap_seed
                and _origin_pattern_code(source_kind=word.source_kind) == pattern.code
                and word.canonical_writing_ja not in example_lexical_lemmas
            ]
        )
        core_lemmas = _ordered_unique([lemma for lemma in example_lexical_lemmas if lemma not in known_word_lemmas])
        extra_lemmas = _ordered_unique([lemma for lemma in generated_stage_lemmas if lemma not in known_word_lemmas])
        new_word_lemmas = _ordered_unique([*anchor_lemmas, *core_lemmas, *extra_lemmas])
        scored_new_words = sorted(
            [words_by_lemma[lemma] for lemma in new_word_lemmas if lemma in words_by_lemma],
            key=lambda word: (word.intro_order, word.canonical_writing_ja),
        )
        bundles.append(
            PatternBundle(
                pattern_code=pattern.code,
                support_lemmas=support_lemmas,
                anchor_lemmas=anchor_lemmas,
                core_lemmas=core_lemmas,
                extra_lemmas=extra_lemmas,
                new_word_lemmas=new_word_lemmas,
                word_choice_intro_lemmas=_ordered_unique(list(new_word_lemmas)),
                examples=pattern.examples,
                primary_theme_codes=_bundle_theme_codes(
                    bundle_words=scored_new_words,
                    fallback_primary_themes=config.current_section.primary_themes,
                ),
            )
        )
        known_word_lemmas.update(new_word_lemmas)

    residual_generated_words = sorted(
        [
            word
            for word in words_by_lemma.values()
            if not word.is_bootstrap_seed and word.canonical_writing_ja not in known_word_lemmas
        ],
        key=lambda word: (word.intro_order, word.canonical_writing_ja),
    )
    if residual_generated_words:
        residual_lemmas = _ordered_unique([word.canonical_writing_ja for word in residual_generated_words])
        bundles.append(
            PatternBundle(
                pattern_code="SECTION_LEXICAL_EXPANSION",
                support_lemmas=(),
                anchor_lemmas=(),
                core_lemmas=residual_lemmas,
                extra_lemmas=(),
                new_word_lemmas=residual_lemmas,
                word_choice_intro_lemmas=residual_lemmas,
                examples=(),
                primary_theme_codes=_bundle_theme_codes(
                    bundle_words=residual_generated_words,
                    fallback_primary_themes=config.current_section.primary_themes,
                ),
            )
        )

    return bundles


def _chunk_examples_for_lessons(
    *,
    examples: tuple[CurriculumPatternExample, ...],
    sentence_intro_counts: list[int],
) -> list[tuple[CurriculumPatternExample, ...]]:
    remaining_examples = list(examples)
    lesson_examples: list[tuple[CurriculumPatternExample, ...]] = []
    for sentence_intro_count in sentence_intro_counts:
        take_count = min(sentence_intro_count, len(remaining_examples))
        lesson_examples.append(tuple(remaining_examples[:take_count]))
        remaining_examples = remaining_examples[take_count:]
    return lesson_examples


def _allocate_intro_lemmas_by_lesson(
    *,
    bundle: PatternBundle,
    lesson_examples: list[tuple[CurriculumPatternExample, ...]],
    sentence_intro_counts: list[int],
    generated_sentence_count_by_lemma: dict[str, int],
) -> list[tuple[str, ...]]:
    remaining_intro_lemmas = list(bundle.word_choice_intro_lemmas)
    remaining_intro_lemma_set = set(remaining_intro_lemmas)
    introduced_lemmas_by_lesson: list[list[str]] = [[] for _ in sentence_intro_counts]

    for lesson_index, examples in enumerate(lesson_examples):
        lesson_intro_lemmas: list[str] = []
        for example in examples:
            for canonical_writing_ja, _reading_kana, pos in example.lexicon_used:
                if LexemePos.is_support(pos) or canonical_writing_ja not in remaining_intro_lemma_set:
                    continue
                lesson_intro_lemmas.append(canonical_writing_ja)
                remaining_intro_lemma_set.remove(canonical_writing_ja)
        introduced_lemmas_by_lesson[lesson_index].extend(_ordered_unique(lesson_intro_lemmas))
        remaining_intro_lemmas = [lemma for lemma in remaining_intro_lemmas if lemma in remaining_intro_lemma_set]

    for lesson_index, sentence_intro_count in enumerate(sentence_intro_counts):
        remaining_generated_capacity = max(0, sentence_intro_count - len(lesson_examples[lesson_index]))
        if remaining_generated_capacity == 0:
            continue
        lesson_generated_lemmas: list[str] = []
        updated_remaining_intro_lemmas: list[str] = []
        for lemma in remaining_intro_lemmas:
            generated_count = generated_sentence_count_by_lemma.get(lemma, 0)
            if generated_count <= 0 or generated_count > remaining_generated_capacity:
                updated_remaining_intro_lemmas.append(lemma)
                continue
            lesson_generated_lemmas.append(lemma)
            remaining_generated_capacity -= generated_count
            remaining_intro_lemma_set.discard(lemma)
            if remaining_generated_capacity == 0:
                updated_remaining_intro_lemmas.extend(
                    trailing_lemma for trailing_lemma in remaining_intro_lemmas if trailing_lemma not in lesson_generated_lemmas
                )
                break
        remaining_intro_lemmas = updated_remaining_intro_lemmas
        introduced_lemmas_by_lesson[lesson_index].extend(lesson_generated_lemmas)

    if remaining_intro_lemmas:
        last_lesson_index = len(introduced_lemmas_by_lesson) - 1
        introduced_lemmas_by_lesson[last_lesson_index].extend(remaining_intro_lemmas)

    return [_ordered_unique(lesson_intro_lemmas) for lesson_intro_lemmas in introduced_lemmas_by_lesson]


def _build_bundle_lessons(
    *,
    bundle: PatternBundle,
    section_planning: SectionPlanningConfig,
    generated_sentence_count_by_lemma: dict[str, int],
) -> list[PlannedLessonWave]:
    sentence_count = _sentence_count_for_bundle(
        bundle=bundle,
        generated_sentence_count_by_lemma=generated_sentence_count_by_lemma,
    )
    if sentence_count == 0 and not bundle.word_choice_intro_lemmas:
        return []

    sentence_intro_counts = _split_sentence_introductions(
        sentence_count=sentence_count,
        min_per_lesson=section_planning.min_sentence_introductions_per_normal_lesson,
        max_per_lesson=section_planning.max_sentence_introductions_per_normal_lesson,
    )
    lesson_examples = _chunk_examples_for_lessons(examples=bundle.examples, sentence_intro_counts=sentence_intro_counts)
    introduced_lemmas_by_lesson = _allocate_intro_lemmas_by_lesson(
        bundle=bundle,
        lesson_examples=lesson_examples,
        sentence_intro_counts=sentence_intro_counts,
        generated_sentence_count_by_lemma=generated_sentence_count_by_lemma,
    )
    lessons: list[PlannedLessonWave] = []
    available_word_lemmas: list[str] = []
    available_pattern_codes: list[str] = []
    for lesson_index, _sentence_intro_count in enumerate(sentence_intro_counts):
        introduced_word_lemmas = introduced_lemmas_by_lesson[lesson_index]
        target_pattern_codes = (
            ()
            if bundle.pattern_code in NONPATTERN_BUNDLE_CODES or lesson_index > 0
            else (bundle.pattern_code,)
        )
        available_word_lemmas = list(dict.fromkeys([*available_word_lemmas, *introduced_word_lemmas]))
        available_pattern_codes = list(dict.fromkeys([*available_pattern_codes, *target_pattern_codes]))
        target_item_count = (
            len(introduced_word_lemmas)
            + len(lesson_examples[lesson_index]) * 2
            + sum(generated_sentence_count_by_lemma.get(lemma, 0) for lemma in introduced_word_lemmas) * 2
        )
        if target_item_count == 0:
            continue
        lessons.append(
            PlannedLessonWave(
                lesson_kind=(
                    "bootstrap_support_only"
                    if bundle.pattern_code == "BOOTSTRAP_SUPPORT_ONLY"
                    else "unit_kernel"
                    if lesson_index == 0
                    else "unit_sentence_flow"
                ),
                force_kana_display=False,
                introduced_word_lemmas=introduced_word_lemmas,
                kanji_focus_word_lemmas=(),
                target_word_lemmas=introduced_word_lemmas,
                target_pattern_codes=target_pattern_codes,
                target_pattern_code=target_pattern_codes[0] if target_pattern_codes else None,
                target_pattern_examples=lesson_examples[lesson_index],
                available_word_lemmas=tuple(available_word_lemmas),
                available_pattern_codes=tuple(available_pattern_codes),
                target_item_count=target_item_count,
            )
        )
    return lessons


def _rebuild_availability(
    *,
    lessons: list[PlannedLessonWave],
) -> list[PlannedLessonWave]:
    available_word_lemmas: list[str] = []
    available_pattern_codes: list[str] = []
    rebuilt_lessons: list[PlannedLessonWave] = []
    for lesson in lessons:
        available_word_lemmas = list(dict.fromkeys([*available_word_lemmas, *lesson.introduced_word_lemmas]))
        available_pattern_codes = list(dict.fromkeys([*available_pattern_codes, *lesson.target_pattern_codes]))
        rebuilt_lessons.append(
            PlannedLessonWave(
                lesson_kind=lesson.lesson_kind,
                force_kana_display=lesson.force_kana_display,
                introduced_word_lemmas=lesson.introduced_word_lemmas,
                kanji_focus_word_lemmas=lesson.kanji_focus_word_lemmas,
                target_word_lemmas=lesson.target_word_lemmas,
                target_pattern_codes=lesson.target_pattern_codes,
                target_pattern_code=lesson.target_pattern_code,
                target_pattern_examples=lesson.target_pattern_examples,
                available_word_lemmas=tuple(available_word_lemmas),
                available_pattern_codes=tuple(available_pattern_codes),
                target_item_count=lesson.target_item_count,
            )
        )
    return rebuilt_lessons


def _split_counts_into_units(*, lesson_count: int) -> list[int]:
    if lesson_count <= 0:
        return []
    if lesson_count == 1:
        return [1]
    unit_count = ceil(lesson_count / MAX_NORMAL_LESSONS_PER_UNIT)
    counts = [MAX_NORMAL_LESSONS_PER_UNIT] * unit_count
    overflow = sum(counts) - lesson_count
    for index in range(unit_count - 1, -1, -1):
        reducible = counts[index] - MIN_NORMAL_LESSONS_PER_UNIT
        take = min(reducible, overflow)
        counts[index] -= take
        overflow -= take
        if overflow == 0:
            break
    return counts


def _chunk_lessons_into_units(
    *,
    flattened_lessons: list[PlannedLessonWave],
    bootstrap_unit_present: bool,
) -> list[list[PlannedLessonWave]]:
    if not flattened_lessons:
        return []
    chunks: list[list[PlannedLessonWave]] = []
    start_index = 0
    if bootstrap_unit_present:
        chunks.append([flattened_lessons[0]])
        start_index = 1
    remaining_lessons = flattened_lessons[start_index:]
    if bootstrap_unit_present and len(remaining_lessons) == 1:
        chunks[0].append(remaining_lessons[0])
        return chunks
    counts = _split_counts_into_units(lesson_count=len(remaining_lessons))
    offset = 0
    for count in counts:
        chunks.append(remaining_lessons[offset : offset + count])
        offset += count
    return chunks


def _build_kanji_activation_lessons(
    *,
    backlog_word_lemmas: list[str],
) -> list[PlannedLessonWave]:
    lessons: list[PlannedLessonWave] = []
    for start_index in range(0, len(backlog_word_lemmas), KANJI_ACTIVATION_WORDS_PER_LESSON):
        chunk = tuple(backlog_word_lemmas[start_index : start_index + KANJI_ACTIVATION_WORDS_PER_LESSON])
        lessons.append(
            PlannedLessonWave(
                lesson_kind="kanji_activation",
                force_kana_display=False,
                introduced_word_lemmas=(),
                kanji_focus_word_lemmas=chunk,
                target_word_lemmas=(),
                target_pattern_codes=(),
                target_pattern_code=None,
                target_pattern_examples=(),
                available_word_lemmas=chunk,
                available_pattern_codes=(),
                target_item_count=len(chunk) * 2,
            )
        )
    return lessons


def _apply_kana_transition_to_lessons(
    *,
    lessons: list[PlannedLessonWave],
    words_by_lemma: dict[str, CurriculumWord],
    previously_introduced_word_lemmas: list[str],
    previously_introduced_pattern_codes: list[str],
) -> list[PlannedLessonWave]:
    introduced_section_pattern_codes: set[str] = set()
    threshold_index: int | None = None
    for lesson_index, lesson in enumerate(lessons):
        introduced_section_pattern_codes.update(
            code
            for code in lesson.target_pattern_codes
            if code not in NONPATTERN_BUNDLE_CODES and code not in previously_introduced_pattern_codes
        )
        if len(introduced_section_pattern_codes) >= KANJI_TRANSITION_PATTERN_THRESHOLD:
            threshold_index = lesson_index
            break

    if threshold_index is None:
        return [
            PlannedLessonWave(
                lesson_kind=lesson.lesson_kind,
                force_kana_display=True,
                introduced_word_lemmas=lesson.introduced_word_lemmas,
                kanji_focus_word_lemmas=lesson.kanji_focus_word_lemmas,
                target_word_lemmas=lesson.target_word_lemmas,
                target_pattern_codes=lesson.target_pattern_codes,
                target_pattern_code=lesson.target_pattern_code,
                target_pattern_examples=lesson.target_pattern_examples,
                available_word_lemmas=lesson.available_word_lemmas,
                available_pattern_codes=lesson.available_pattern_codes,
                target_item_count=lesson.target_item_count,
            )
            for lesson in lessons
        ]

    seen_lemmas: set[str] = set(previously_introduced_word_lemmas)
    backlog_kanji_word_lemmas: list[str] = []
    for lesson in lessons[: threshold_index + 1]:
        for lemma in lesson.introduced_word_lemmas:
            if lemma in seen_lemmas:
                continue
            seen_lemmas.add(lemma)
            word = words_by_lemma.get(lemma)
            if word is not None and _is_nonverb_kanji_word(word=word):
                backlog_kanji_word_lemmas.append(lemma)

    activation_lessons = _build_kanji_activation_lessons(backlog_word_lemmas=backlog_kanji_word_lemmas)
    rebuilt_lessons: list[PlannedLessonWave] = []
    for lesson_index, lesson in enumerate(lessons):
        rebuilt_lessons.append(
            PlannedLessonWave(
                lesson_kind=lesson.lesson_kind,
                force_kana_display=lesson_index <= threshold_index,
                introduced_word_lemmas=lesson.introduced_word_lemmas,
                kanji_focus_word_lemmas=lesson.kanji_focus_word_lemmas,
                target_word_lemmas=lesson.target_word_lemmas,
                target_pattern_codes=lesson.target_pattern_codes,
                target_pattern_code=lesson.target_pattern_code,
                target_pattern_examples=lesson.target_pattern_examples,
                available_word_lemmas=lesson.available_word_lemmas,
                available_pattern_codes=lesson.available_pattern_codes,
                target_item_count=lesson.target_item_count,
            )
        )
        if lesson_index == threshold_index:
            rebuilt_lessons.extend(activation_lessons)
    return _rebuild_availability(lessons=rebuilt_lessons)


def _to_curriculum_units(
    *,
    lesson_chunks: list[list[PlannedLessonWave]],
    fallback_primary_theme_codes: tuple[str, ...],
) -> list[CurriculumUnit]:
    units: list[CurriculumUnit] = []
    for unit_index, lesson_chunk in enumerate(lesson_chunks, start=1):
        chunk_pattern_codes = _ordered_unique(
            [
                pattern_code
                for lesson in lesson_chunk
                for pattern_code in lesson.target_pattern_codes
                if pattern_code not in NONPATTERN_BUNDLE_CODES
            ]
        )
        units.append(
            CurriculumUnit(
                order_index=unit_index,
                primary_theme_codes=fallback_primary_theme_codes,
                pattern_codes=chunk_pattern_codes,
                lessons=tuple(
                    CurriculumLesson(
                        lesson_index_within_unit=lesson_index,
                        kind="normal",
                        lesson_kind=lesson.lesson_kind,
                        force_kana_display=lesson.force_kana_display,
                        target_item_count=lesson.target_item_count,
                        introduced_word_lemmas=lesson.introduced_word_lemmas,
                        kanji_focus_word_lemmas=lesson.kanji_focus_word_lemmas,
                        target_word_lemmas=lesson.target_word_lemmas,
                        target_pattern_codes=lesson.target_pattern_codes,
                        target_pattern_code=lesson.target_pattern_code,
                        target_pattern_examples=lesson.target_pattern_examples,
                        available_word_lemmas=lesson.available_word_lemmas,
                        available_pattern_codes=lesson.available_pattern_codes,
                        target_pattern_sentence_count=len(lesson.target_pattern_examples),
                    )
                    for lesson_index, lesson in enumerate(lesson_chunk, start=1)
                ),
            )
        )
    return units


def build_section_curriculum(
    *,
    config: CourseBuildConfig,
    words: list[CurriculumWord],
    patterns: list[CurriculumPattern],
    previously_introduced_word_lemmas: list[str],
    previously_introduced_pattern_codes: list[str],
    current_section_bootstrap_expression_lemmas: list[str],
    generated_sentence_count_by_lemma: dict[str, int],
) -> SectionCurriculumPlan:
    bundles = build_pattern_bundles(
        config=config,
        words=words,
        patterns=patterns,
        previously_introduced_word_lemmas=previously_introduced_word_lemmas,
        current_section_bootstrap_expression_lemmas=current_section_bootstrap_expression_lemmas,
    )
    bundle_lessons = [
        lesson
        for bundle in bundles
        for lesson in _build_bundle_lessons(
            bundle=bundle,
            section_planning=config.current_section.section_planning,
            generated_sentence_count_by_lemma=generated_sentence_count_by_lemma,
        )
    ]
    bundle_lessons = _rebuild_availability(lessons=bundle_lessons)
    bundle_lessons = _apply_kana_transition_to_lessons(
        lessons=bundle_lessons,
        words_by_lemma={word.canonical_writing_ja: word for word in words},
        previously_introduced_word_lemmas=previously_introduced_word_lemmas,
        previously_introduced_pattern_codes=previously_introduced_pattern_codes,
    )
    lesson_chunks = _chunk_lessons_into_units(
        flattened_lessons=bundle_lessons,
        bootstrap_unit_present=bool(bundles and bundles[0].pattern_code == "BOOTSTRAP_SUPPORT_ONLY"),
    )
    return SectionCurriculumPlan(
        units=tuple(
            _to_curriculum_units(
                lesson_chunks=lesson_chunks,
                fallback_primary_theme_codes=tuple(config.current_section.primary_themes[:1]),
            )
        )
    )


def load_section_curriculum(
    *,
    context: BuildContext,
    q: PlanningQueries,
) -> SectionCurriculumPlan:
    section_curriculum = q.load_section_curriculum_plan()
    if not section_curriculum.units:
        msg = f"Section curriculum must be planned before it can be loaded for course_version_id={context.course_version_id}"
        raise ValueError(msg)
    return section_curriculum


def list_lessons_with_plan(
    *,
    context: BuildContext,
    q: PlanningQueries,
) -> list[LessonWithPlan]:
    section_curriculum = load_section_curriculum(context=context, q=q)
    planned_lessons_by_order = {
        (planned_unit.order_index, planned_lesson.lesson_index_within_unit): planned_lesson
        for planned_unit in section_curriculum.units
        for planned_lesson in planned_unit.lessons
    }
    return [
        LessonWithPlan(
            lesson=lesson,
            unit_order_index=unit_order_index,
            planned_lesson=planned_lessons_by_order[unit_order_index, lesson.order_index],
        )
        for lesson, unit_order_index in q.list_normal_lessons_with_unit_order()
    ]
