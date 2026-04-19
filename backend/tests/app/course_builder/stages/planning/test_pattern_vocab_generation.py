from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from course_builder.llm.master_pattern_vocab_generation import graph as master_pattern_vocab_generation_graph
from course_builder.llm.pattern_vocab_generation.json_schema import (
    WordBatchItemPayload,
    WordExampleSentencePayload,
)
from course_builder.stages.bootstrap.bootstrap_seed_words import (
    InsertBootstrapSeedWordsStep,
    insert_bootstrap_seed_words,
)
from course_builder.stages.bootstrap.pattern_catalog import ImportPatternCatalogStep, import_pattern_catalog
from course_builder.stages.bootstrap.sections import ImportSectionConfigStep, import_section_config
from course_builder.stages.bootstrap.theme_tags import ImportThemeTagsStep, import_theme_tags
from course_builder.stages.planning.pattern_vocab_generation import (
    PatternVocabGenerationStage,
    PatternVocabGenerationStats,
    generate_pattern_vocab,
)
from domain.content.models import (
    SectionWord,
    Sentence,
    SentencePatternLink,
    SentenceWordLink,
    Word,
    WordThemeLink,
)
from tests.helpers.builder import CourseBuildTestRunner, create_test_build_context, load_test_config
from tests.helpers.config_builder import build_test_config_yaml
from tests.helpers.fake_llms import SequentialStructuredLlm

FakeStructuredLlm = SequentialStructuredLlm


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


def test_generate_pattern_vocab_noops_when_inventory_already_complete(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = create_test_build_context(db_session, tmp_path)
    import_theme_tags(db_session, context=context)
    import_pattern_catalog(db_session, context=context)
    import_section_config(db_session, context=context)
    insert_bootstrap_seed_words(db_session, context=context)
    llm = FakeStructuredLlm(payloads=[])

    monkeypatch.setattr(
        master_pattern_vocab_generation_graph,
        "create_chat_openai",
        lambda *, model, reasoning_effort: llm,
    )
    stats = generate_pattern_vocab(db_session, context=context)

    assert stats == PatternVocabGenerationStats(
        words_created=0,
        generated_word_theme_links_created=0,
    )
    assert llm.calls == 0


def test_generate_pattern_vocab_inserts_generated_words_when_needed(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expanded_config = build_test_config_yaml(
        updates={
            ("patterns", 0, "min_extra_words"): 2,
            ("patterns", 0, "max_extra_words"): 2,
        }
    )
    context = create_test_build_context(db_session, tmp_path, content=expanded_config)
    import_theme_tags(db_session, context=context)
    import_pattern_catalog(db_session, context=context)
    import_section_config(db_session, context=context)
    insert_bootstrap_seed_words(db_session, context=context)
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
                ],
            }
        ]
    )

    monkeypatch.setattr(
        master_pattern_vocab_generation_graph,
        "create_chat_openai",
        lambda *, model, reasoning_effort: llm,
    )
    stats = generate_pattern_vocab(db_session, context=context)

    assert stats == PatternVocabGenerationStats(
        words_created=2,
        generated_word_theme_links_created=4,
    )
    persisted_words = db_session.scalars(
        select(Word).where(Word.course_version_id == context.course_version_id).order_by(Word.intro_order)
    ).all()
    assert [word.canonical_writing_ja for word in persisted_words] == [
        "は",
        "です",
        "こんにちは",
        "ありがとう",
        "私",
        "これ",
        "学生",
        "本",
        "みせ",
        "へや",
    ]
    section_roles = db_session.scalars(select(SectionWord.role).order_by(SectionWord.role)).all()
    assert section_roles.count("new") == 8
    assert section_roles.count("safe_allowed") == 0
    assert db_session.scalar(select(WordThemeLink.word_id).limit(1)) is not None
    assert db_session.query(WordThemeLink).count() == 4
    persisted_sentences = list(
        db_session.execute(
            select(Sentence.ja_text, Sentence.en_text)
            .where(Sentence.target_word_id.is_not(None))
            .order_by(Sentence.ja_text)
        ).all()
    )
    assert persisted_sentences == [
        ("これはへやです", "This is room"),
        ("これはみせです", "This is shop"),
        ("へやです", "It is room"),
        ("みせです", "It is shop"),
    ]
    assert db_session.scalar(select(SentenceWordLink.sentence_id).limit(1)) is not None
    assert db_session.scalar(select(SentencePatternLink.sentence_id).limit(1)) is None


def test_generate_pattern_vocab_rejects_duplicate_generated_lemma(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expanded_config = build_test_config_yaml(
        updates={
            ("patterns", 0, "min_extra_words"): 1,
            ("patterns", 0, "max_extra_words"): 1,
        }
    )
    context = create_test_build_context(db_session, tmp_path, content=expanded_config)
    import_theme_tags(db_session, context=context)
    import_pattern_catalog(db_session, context=context)
    import_section_config(db_session, context=context)
    insert_bootstrap_seed_words(db_session, context=context)
    llm = FakeStructuredLlm(
        payloads=[
            {
                "items": [
                    build_word_item(
                        canonical_writing_ja="私",
                        reading_kana="わたし",
                        gloss_primary_en="I",
                        pos="pronoun",
                    ).model_dump()
                ],
            }
        ]
    )

    monkeypatch.setattr(
        master_pattern_vocab_generation_graph,
        "create_chat_openai",
        lambda *, model, reasoning_effort: llm,
    )
    with pytest.raises(ValueError, match=r"already exists in inventory|existing lemma"):
        generate_pattern_vocab(db_session, context=context)
    assert llm.calls >= 1


def test_test_runner_runs_word_generation_step(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expanded_config = build_test_config_yaml(
        updates={
            ("patterns", 0, "min_extra_words"): 1,
            ("patterns", 0, "max_extra_words"): 1,
        }
    )
    config = load_test_config(tmp_path, content=expanded_config)
    llm = FakeStructuredLlm(
        payloads=[
            {
                "items": [
                    build_word_item(
                        canonical_writing_ja="みせ",
                        reading_kana="みせ",
                        gloss_primary_en="shop",
                        pos="noun",
                    ).model_dump()
                ],
            }
        ]
    )
    runner = CourseBuildTestRunner(
        steps=[
            ImportThemeTagsStep(),
            ImportPatternCatalogStep(),
            ImportSectionConfigStep(),
            InsertBootstrapSeedWordsStep(),
            PatternVocabGenerationStage(),
        ]
    )
    monkeypatch.setattr(
        master_pattern_vocab_generation_graph,
        "create_chat_openai",
        lambda *, model, reasoning_effort: llm,
    )

    context = runner.run(db=db_session, config=config)

    persisted_words = db_session.scalars(
        select(Word.canonical_writing_ja)
        .where(Word.course_version_id == context.course_version_id)
        .order_by(Word.intro_order)
    ).all()
    assert persisted_words == ["は", "です", "こんにちは", "ありがとう", "私", "これ", "学生", "本", "みせ"]


def test_generate_pattern_vocab_generates_missing_pattern_example_lexeme_before_extra_words(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expanded_config = build_test_config_yaml(
        updates={
            ("patterns", 0, "min_extra_words"): 0,
            ("patterns", 0, "max_extra_words"): 0,
        },
        appends={
            ("patterns", 0, "examples"): [
                {
                    "ja": "これはみせです。",
                    "en": "This is a shop.",
                    "lexicon_used": [
                        {"canonical_writing_ja": "これ", "reading_kana": "これ", "pos": "pronoun"},
                        {"canonical_writing_ja": "は", "reading_kana": "は", "pos": "particle"},
                        {"canonical_writing_ja": "みせ", "reading_kana": "みせ", "pos": "noun"},
                        {"canonical_writing_ja": "です", "reading_kana": "です", "pos": "copula"},
                    ],
                }
            ]
        },
    )
    context = create_test_build_context(db_session, tmp_path, content=expanded_config)
    import_theme_tags(db_session, context=context)
    import_pattern_catalog(db_session, context=context)
    import_section_config(db_session, context=context)
    insert_bootstrap_seed_words(db_session, context=context)

    llm = FakeStructuredLlm(
        payloads=[
            {
                "items": [
                    {
                        "l": "みせ",
                        "r": "みせ",
                        "o": "noun",
                        "g": "shop",
                        "ga": ["store"],
                        "u": None,
                        "x": [
                            {"j": "これはみせです。", "e": "This is a shop."},
                            {"j": "みせです。", "e": "It is a shop."},
                        ],
                    }
                ]
            }
        ]
    )
    monkeypatch.setattr(
        master_pattern_vocab_generation_graph,
        "create_chat_openai",
        lambda *, model, reasoning_effort: llm,
    )

    stats = generate_pattern_vocab(db_session, context=context)

    assert stats == PatternVocabGenerationStats(
        words_created=1,
        generated_word_theme_links_created=0,
    )
    persisted_words = db_session.scalars(
        select(Word.canonical_writing_ja)
        .where(Word.course_version_id == context.course_version_id)
        .order_by(Word.intro_order)
    ).all()
    assert persisted_words == ["は", "です", "こんにちは", "ありがとう", "私", "これ", "学生", "本", "みせ"]
    assert llm.calls == 1
