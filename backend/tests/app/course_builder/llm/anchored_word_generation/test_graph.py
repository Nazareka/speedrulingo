from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

from langchain_core.language_models.chat_models import BaseChatModel
import pytest
from sqlalchemy.orm import Session

from course_builder.config import AnchorWordRefConfig, CourseBuildConfig
from course_builder.lexicon import LexemePos
from course_builder.llm.anchored_word_generation import (
    get_anchored_word_generation_graph,
)
from course_builder.llm.anchored_word_generation.graph import Context as GraphContext, InputState as GraphInputState
from course_builder.llm.anchored_word_generation.models import (
    AnchoredWordGenerationResult,
    PreparedAnchoredWordGenerationInput,
)
from course_builder.llm.core.models import ExistingWordPromptInfo
from tests.helpers.builder import create_test_build_context
from tests.helpers.fake_llms import SequentialStructuredLlm


def _prepared_input() -> PreparedAnchoredWordGenerationInput:
    return PreparedAnchoredWordGenerationInput(
        targets=[
            AnchorWordRefConfig(
                canonical_writing_ja="みせ",
                reading_kana="みせ",
                pos=LexemePos.NOUN,
            )
        ],
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
        allowed_pattern_codes=["WA_DESU_STATEMENT"],
    )


def _run_graph(
    *,
    llm: SequentialStructuredLlm,
    prepared_input: PreparedAnchoredWordGenerationInput,
    context_config: CourseBuildConfig,
) -> AnchoredWordGenerationResult:
    graph = get_anchored_word_generation_graph()
    input_state: GraphInputState = {"prepared_input": prepared_input}
    context: GraphContext = {"config": context_config, "llm": cast(BaseChatModel, llm)}
    result = asyncio.run(
        graph.ainvoke(
            input_state,
            context=context,
        )
    )
    return result["result"]


def test_anchored_word_generation_graph_returns_metadata_for_requested_lexeme(
    tmp_path: Path,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = create_test_build_context(db_session, tmp_path)
    llm = SequentialStructuredLlm(
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
        ],
        record_messages=True,
    )
    result = _run_graph(llm=llm, prepared_input=_prepared_input(), context_config=context.config)

    assert result.iterations == 1
    assert len(result.words) == 1
    assert result.words[0].canonical_writing_ja == "みせ"
    assert result.words[0].pos == LexemePos.NOUN
    prompt_text = "\n".join(getattr(message, "content", "") for message in llm.messages[0])
    assert "<patterns_scope>WA_DESU_STATEMENT | templates=X は Y です</patterns_scope>" in prompt_text
    assert prompt_text.index("<patterns_scope>") < prompt_text.index("<targets>")


def test_anchored_word_generation_graph_rejects_changed_requested_identity(
    tmp_path: Path,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = create_test_build_context(db_session, tmp_path)
    llm = SequentialStructuredLlm(
        payloads=[
            {
                "items": [
                    {
                        "l": "うち",
                        "r": "うち",
                        "o": "noun",
                        "g": "home",
                        "ga": [],
                        "u": None,
                        "x": [
                            {"j": "これはうちです。", "e": "This is a home."},
                            {"j": "うちです。", "e": "It is a home."},
                        ],
                    }
                ]
            }
        ]
    )
    with pytest.raises(ValueError, match="changed requested lexeme identity"):
        _run_graph(llm=llm, prepared_input=_prepared_input(), context_config=context.config)


def test_anchored_word_generation_graph_rejects_example_using_unavailable_support_vocab(
    tmp_path: Path,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = create_test_build_context(db_session, tmp_path)
    llm = SequentialStructuredLlm(
        payloads=[
            {
                "items": [
                    {
                        "l": "サッカー",
                        "r": "さっかー",
                        "o": "noun",
                        "g": "soccer",
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
            prepared_input=PreparedAnchoredWordGenerationInput(
                targets=[
                    AnchorWordRefConfig(
                        canonical_writing_ja="サッカー",
                        reading_kana="さっかー",
                        pos=LexemePos.NOUN,
                    )
                ],
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
                        canonical_writing_ja="ケン",
                        reading_kana="けん",
                        gloss_primary_en="Ken",
                        gloss_alternatives_en=[],
                        usage_note_en=None,
                        pos="proper_noun",
                    ),
                    ExistingWordPromptInfo(
                        canonical_writing_ja="さん",
                        reading_kana="さん",
                        gloss_primary_en="Mr./Ms.",
                        gloss_alternatives_en=[],
                        usage_note_en=None,
                        pos="suffix",
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
                        canonical_writing_ja="を",
                        reading_kana="を",
                        gloss_primary_en="object particle",
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
                allowed_pattern_codes=["WA_DESU_STATEMENT"],
            ),
        )
