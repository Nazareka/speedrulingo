from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

from langchain_core.language_models.chat_models import BaseChatModel
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from course_builder.config import CourseBuildConfig
from course_builder.engine.models import BuildContext
from course_builder.llm.core.models import ExistingWordPromptInfo
from course_builder.llm.pattern_vocab_generation import (
    get_pattern_vocab_graph,
)
from course_builder.llm.pattern_vocab_generation.graph import (
    Context as GraphContext,
    InputState as GraphInputState,
)
from course_builder.llm.pattern_vocab_generation.json_schema import (
    WordBatchItemPayload,
    WordExampleSentencePayload,
)
from course_builder.llm.pattern_vocab_generation.models import (
    PatternVocabGenerationResult,
    PreparedPatternVocabGenerationInput,
)
from course_builder.llm.pattern_vocab_generation.utils import sentence_uses_generated_lemma
from course_builder.stages.bootstrap.bootstrap_seed_words import insert_bootstrap_seed_words
from course_builder.stages.bootstrap.pattern_catalog import import_pattern_catalog
from course_builder.stages.bootstrap.sections import import_section_config
from course_builder.stages.bootstrap.theme_tags import import_theme_tags
from domain.content.models import Section, Word
from tests.helpers.builder import create_test_build_context, load_test_config
from tests.helpers.config_builder import build_test_config_yaml
from tests.helpers.fake_llms import SequentialStructuredLlm

build_context = create_test_build_context
load_config = load_test_config

FakeStructuredLlm = SequentialStructuredLlm


def test_sentence_uses_generated_lemma_accepts_i_adjective_inflections() -> None:
    candidate = WordBatchItemPayload(
        canonical_writing_ja="忙しい",
        reading_kana="いそがしい",
        gloss_primary_en="busy",
        pos="adjective_i",
        example_sentences=[
            WordExampleSentencePayload(
                ja_text="今日は忙しいです。",
                en_text="I am busy today.",
            ),
            WordExampleSentencePayload(
                ja_text="昨日は忙しかったです。",
                en_text="I was busy yesterday.",
            ),
        ],
    )

    assert sentence_uses_generated_lemma(candidate=candidate, sentence_ja_text="今日は忙しいです。")
    assert sentence_uses_generated_lemma(candidate=candidate, sentence_ja_text="昨日は忙しかったです。")
    assert sentence_uses_generated_lemma(candidate=candidate, sentence_ja_text="今日は忙しくないです。")
    assert sentence_uses_generated_lemma(candidate=candidate, sentence_ja_text="昨日は忙しくなかったです。")


def build_word_item(
    *,
    canonical_writing_ja: str,
    reading_kana: str,
    gloss_primary_en: str,
    pos: str,
) -> WordBatchItemPayload:
    return WordBatchItemPayload(
        canonical_writing_ja=canonical_writing_ja,
        reading_kana=reading_kana,
        gloss_primary_en=gloss_primary_en,
        pos=pos,
        example_sentences=[
            WordExampleSentencePayload(
                ja_text=f"{canonical_writing_ja}です。",
                en_text=f"It is {gloss_primary_en}.",
            ),
            WordExampleSentencePayload(
                ja_text=f"これは{canonical_writing_ja}です。",
                en_text=f"This is {gloss_primary_en}.",
            ),
        ],
    )


def _prepared_input(
    db_session: Session,
    *,
    course_version_id: str,
    min_words: int,
    max_words: int,
) -> PreparedPatternVocabGenerationInput:
    section_id = db_session.scalar(
        select(Section.id).where(Section.course_version_id == course_version_id, Section.order_index == 1).limit(1)
    )
    assert section_id is not None
    existing_word_rows = db_session.execute(
        select(
            Word.canonical_writing_ja,
            Word.reading_kana,
            Word.gloss_primary_en,
            Word.gloss_alternatives_en,
            Word.usage_note_en,
            Word.pos,
        )
        .where(Word.course_version_id == course_version_id)
        .order_by(Word.intro_order)
    ).all()
    return PreparedPatternVocabGenerationInput(
        course_version_id=course_version_id,
        min_words=min_words,
        max_words=max_words,
        existing_words=[
            ExistingWordPromptInfo(
                canonical_writing_ja=row.canonical_writing_ja,
                reading_kana=row.reading_kana,
                gloss_primary_en=row.gloss_primary_en,
                gloss_alternatives_en=row.gloss_alternatives_en,
                usage_note_en=row.usage_note_en,
                pos=row.pos,
            )
            for row in existing_word_rows
        ],
        allowed_pattern_codes=["WA_DESU_STATEMENT"],
    )


def _build_context(db_session: Session, tmp_path: Path) -> BuildContext:
    expanded_config = build_test_config_yaml()
    context = build_context(db_session, tmp_path, content=expanded_config)
    import_theme_tags(db_session, context=context)
    import_pattern_catalog(db_session, context=context)
    import_section_config(db_session, context=context)
    insert_bootstrap_seed_words(db_session, context=context)
    return context


def _run_graph(
    *,
    llm: SequentialStructuredLlm,
    prepared_input: PreparedPatternVocabGenerationInput,
    context_config: CourseBuildConfig,
) -> PatternVocabGenerationResult:
    graph = get_pattern_vocab_graph()
    input_state: GraphInputState = {"prepared_input": prepared_input}
    context: GraphContext = {"config": context_config, "llm": cast(BaseChatModel, llm)}
    result = asyncio.run(
        graph.ainvoke(
            input_state,
            context=context,
        )
    )
    return result["result"]


def test_pattern_vocab_generation_graph_accepts_single_bounded_batch(
    db_session: Session,
    tmp_path: Path,
) -> None:
    context = _build_context(db_session, tmp_path)
    llm = FakeStructuredLlm(
        payloads=[
            {
                "items": [
                    build_word_item(
                        canonical_writing_ja="くるま",
                        reading_kana="くるま",
                        gloss_primary_en="car",
                        pos="noun",
                    ).model_dump(),
                    build_word_item(
                        canonical_writing_ja="まち",
                        reading_kana="まち",
                        gloss_primary_en="town",
                        pos="noun",
                    ).model_dump(),
                ]
            }
        ],
        record_messages=True,
    )
    result = _run_graph(
        llm=llm,
        context_config=context.config,
        prepared_input=_prepared_input(
            db_session,
            course_version_id=context.course_version_id,
            min_words=2,
            max_words=2,
        ),
    )

    assert result.words_created == 2
    assert result.iterations == 1
    assert result.inventory_complete is True
    assert [word.canonical_writing_ja for word in result.generated_words] == ["くるま", "まち"]
    message_text = "\n".join(getattr(message, "content", "") for message in llm.messages[0])
    assert "<existing_words>" in message_text
    assert "<validation_feedback>" not in message_text
    assert "<min_words>" not in message_text
    assert "<max_words>" not in message_text


def test_pattern_vocab_generation_graph_enforces_exact_structured_count(
    db_session: Session,
    tmp_path: Path,
) -> None:
    context = _build_context(db_session, tmp_path)
    llm = FakeStructuredLlm(
        payloads=[
            {
                "items": [
                    build_word_item(
                        canonical_writing_ja="みせ",
                        reading_kana="みせ",
                        gloss_primary_en="shop",
                        pos="noun",
                    ).model_dump(),
                    build_word_item(
                        canonical_writing_ja="へや",
                        reading_kana="へや",
                        gloss_primary_en="room",
                        pos="noun",
                    ).model_dump(),
                ]
            }
        ],
        record_messages=True,
    )

    with pytest.raises(Exception, match="items"):
        _run_graph(
            llm=llm,
            context_config=context.config,
            prepared_input=_prepared_input(
                db_session,
                course_version_id=context.course_version_id,
                min_words=1,
                max_words=1,
            ),
        )


def test_pattern_vocab_generation_graph_rejects_too_short_batch(
    db_session: Session,
    tmp_path: Path,
) -> None:
    context = _build_context(db_session, tmp_path)
    llm = FakeStructuredLlm(
        payloads=[
            {
                "items": [
                    build_word_item(
                        canonical_writing_ja="そら",
                        reading_kana="そら",
                        gloss_primary_en="sky",
                        pos="noun",
                    ).model_dump(),
                ]
            }
        ],
        record_messages=True,
    )

    with pytest.raises(RuntimeError, match="fewer items than required: 1 < 2"):
        _run_graph(
            llm=llm,
            context_config=context.config,
            prepared_input=_prepared_input(
                db_session,
                course_version_id=context.course_version_id,
                min_words=2,
                max_words=2,
            ),
        )
    assert llm.calls == 1


def test_pattern_vocab_generation_graph_rejects_duplicate_lemma_reading_pair(
    db_session: Session,
    tmp_path: Path,
) -> None:
    context = _build_context(db_session, tmp_path)
    llm = FakeStructuredLlm(
        payloads=[
            {
                "items": [
                    build_word_item(
                        canonical_writing_ja="くるま",
                        reading_kana="くるま",
                        gloss_primary_en="car",
                        pos="noun",
                    ).model_dump(),
                    build_word_item(
                        canonical_writing_ja="くるま",
                        reading_kana="くるま",
                        gloss_primary_en="car",
                        pos="noun",
                    ).model_dump(),
                ]
            }
        ],
    )

    with pytest.raises(ValueError, match="duplicate lemma/reading pair in generated batch"):
        _run_graph(
            llm=llm,
            context_config=context.config,
            prepared_input=_prepared_input(
                db_session,
                course_version_id=context.course_version_id,
                min_words=2,
                max_words=2,
            ),
        )
    assert llm.calls == 1


def test_pattern_vocab_generation_graph_rejects_non_kana_reading(
    db_session: Session,
    tmp_path: Path,
) -> None:
    context = _build_context(db_session, tmp_path)
    llm = FakeStructuredLlm(
        payloads=[
            {
                "items": [
                    build_word_item(
                        canonical_writing_ja="くるま",
                        reading_kana="kuruma",
                        gloss_primary_en="car",
                        pos="noun",
                    ).model_dump()
                ]
            }
        ],
    )

    with pytest.raises(ValueError, match="reading_kana must contain kana only"):
        _run_graph(
            llm=llm,
            context_config=context.config,
            prepared_input=_prepared_input(
                db_session,
                course_version_id=context.course_version_id,
                min_words=1,
                max_words=1,
            ),
        )
    assert llm.calls == 1


def test_pattern_vocab_generation_graph_allows_empty_batch_when_optional(
    db_session: Session,
    tmp_path: Path,
) -> None:
    context = _build_context(db_session, tmp_path)
    llm = FakeStructuredLlm(payloads=[{"items": []}], record_messages=True)

    result = _run_graph(
        llm=llm,
        context_config=context.config,
        prepared_input=_prepared_input(
            db_session,
            course_version_id=context.course_version_id,
            min_words=0,
            max_words=2,
        ),
    )

    assert result.words_created == 0
    assert result.iterations == 1
    assert result.inventory_complete is True
    assert result.generated_words == []


def test_pattern_vocab_generation_graph_allows_inflected_verb_examples(
    db_session: Session,
    tmp_path: Path,
) -> None:
    context = _build_context(db_session, tmp_path)
    llm = FakeStructuredLlm(
        payloads=[
            {
                "items": [
                    {
                        "l": "買う",
                        "r": "かう",
                        "g": "buy",
                        "o": "verb",
                        "ga": [],
                        "u": None,
                        "x": [
                            {"j": "私は買います。", "e": "I buy."},
                            {"j": "私は買います。", "e": "I buy."},
                        ],
                    }
                ]
            }
        ]
    )

    result = _run_graph(
        llm=llm,
        context_config=context.config,
        prepared_input=_prepared_input(
            db_session,
            course_version_id=context.course_version_id,
            min_words=1,
            max_words=1,
        ),
    )

    assert result.words_created == 1
    assert result.generated_words[0].canonical_writing_ja == "買う"


def test_pattern_vocab_generation_graph_rejects_example_using_unavailable_suru_support(
    db_session: Session,
    tmp_path: Path,
) -> None:
    context = _build_context(db_session, tmp_path)
    llm = FakeStructuredLlm(
        payloads=[
            {
                "items": [
                    {
                        "l": "サッカー",
                        "r": "さっかー",
                        "g": "soccer",
                        "o": "noun",
                        "ga": [],
                        "u": None,
                        "x": [
                            {"j": "ケンさんはサッカーをします。", "e": "Ken plays soccer."},
                            {"j": "これはサッカーです。", "e": "This is soccer."},
                        ],
                    }
                ]
            }
        ]
    )

    with pytest.raises(ValueError, match="example sentence must use only current available vocab"):
        _run_graph(
            llm=llm,
            context_config=context.config,
            prepared_input=_prepared_input(
                db_session,
                course_version_id=context.course_version_id,
                min_words=1,
                max_words=1,
            ),
        )


def test_pattern_vocab_generation_graph_allows_statement_suffix_for_in_scope_pattern(
    db_session: Session,
    tmp_path: Path,
) -> None:
    context = _build_context(db_session, tmp_path)
    llm = FakeStructuredLlm(
        payloads=[
            {
                "items": [
                    {
                        "l": "しゅみ",
                        "r": "しゅみ",
                        "g": "hobby",
                        "o": "noun",
                        "ga": [],
                        "u": None,
                        "x": [
                            {"j": "しゅみです。", "e": "It is a hobby."},
                            {"j": "これはしゅみです。", "e": "This is a hobby."},
                        ],
                    }
                ]
            }
        ]
    )

    result = _run_graph(
        llm=llm,
        context_config=context.config,
        prepared_input=PreparedPatternVocabGenerationInput(
            course_version_id=context.course_version_id,
            min_words=1,
            max_words=1,
            existing_words=[
                ExistingWordPromptInfo(
                    canonical_writing_ja="これ",
                    reading_kana="これ",
                    gloss_primary_en="this",
                    gloss_alternatives_en=[],
                    usage_note_en=None,
                    pos="pronoun",
                ),
                ExistingWordPromptInfo(
                    canonical_writing_ja="は",
                    reading_kana="は",
                    gloss_primary_en="topic particle",
                    gloss_alternatives_en=[],
                    usage_note_en=None,
                    pos="particle",
                ),
                ExistingWordPromptInfo(
                    canonical_writing_ja="です",
                    reading_kana="です",
                    gloss_primary_en="is",
                    gloss_alternatives_en=[],
                    usage_note_en=None,
                    pos="copula",
                ),
            ],
            allowed_pattern_codes=["SUKINA_WA_DESU", "WA_DESU_STATEMENT"],
        ),
    )

    assert result.words_created == 1


def test_pattern_vocab_generation_graph_allows_same_batch_vocab_in_examples(
    db_session: Session,
    tmp_path: Path,
) -> None:
    context = _build_context(db_session, tmp_path)
    llm = FakeStructuredLlm(
        payloads=[
            {
                "items": [
                    {
                        "l": "雨",
                        "r": "あめ",
                        "g": "rain",
                        "o": "noun",
                        "ga": ["rainfall"],
                        "u": None,
                        "x": [
                            {"j": "これは雨です。", "e": "This is rain."},
                            {"j": "明日は雨です。", "e": "Tomorrow it is rain."},
                        ],
                    },
                    {
                        "l": "明日",
                        "r": "あした",
                        "g": "tomorrow",
                        "o": "noun",
                        "ga": ["the next day"],
                        "u": None,
                        "x": [
                            {"j": "明日です。", "e": "It is tomorrow."},
                            {"j": "明日は雨です。", "e": "Tomorrow it is rain."},
                        ],
                    },
                ]
            }
        ]
    )

    result = _run_graph(
        llm=llm,
        context_config=context.config,
        prepared_input=_prepared_input(
            db_session,
            course_version_id=context.course_version_id,
            min_words=2,
            max_words=2,
        ),
    )

    assert result.words_created == 2
    assert [word.canonical_writing_ja for word in result.generated_words] == ["雨", "明日"]
