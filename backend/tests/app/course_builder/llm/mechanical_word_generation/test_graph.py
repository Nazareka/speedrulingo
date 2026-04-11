from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

from langchain_core.language_models.chat_models import BaseChatModel
import pytest
from sqlalchemy.orm import Session

from core.lexicon import LexemePos
from course_builder.config import CourseBuildConfig
from course_builder.llm.mechanical_word_generation import (
    get_mechanical_word_generation_graph,
)
from course_builder.llm.mechanical_word_generation.graph import Context as GraphContext, InputState as GraphInputState
from course_builder.llm.mechanical_word_generation.models import (
    MechanicalLexemePromptInfo,
    MechanicalWordGenerationResult,
    PreparedMechanicalWordGenerationInput,
)
from tests.helpers.builder import create_test_build_context
from tests.helpers.fake_llms import SequentialStructuredLlm


def _prepared_input() -> PreparedMechanicalWordGenerationInput:
    return PreparedMechanicalWordGenerationInput(
        lexemes=[
            MechanicalLexemePromptInfo(
                canonical_writing_ja="さん",
                reading_kana="さん",
                pos=LexemePos.SUFFIX,
            )
        ]
    )


def _run_graph(
    *,
    llm: SequentialStructuredLlm,
    prepared_input: PreparedMechanicalWordGenerationInput,
    context_config: CourseBuildConfig,
) -> MechanicalWordGenerationResult:
    graph = get_mechanical_word_generation_graph()
    input_state: GraphInputState = {"prepared_input": prepared_input}
    context: GraphContext = {"config": context_config, "llm": cast(BaseChatModel, llm)}
    result = asyncio.run(
        graph.ainvoke(
            input_state,
            context=context,
        )
    )
    return result["result"]


def test_mechanical_word_generation_graph_returns_metadata_for_requested_lexeme(
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
                        "l": "さん",
                        "r": "さん",
                        "o": "suffix",
                        "g": "honorific suffix",
                        "ga": ["honorific"],
                        "u": "polite name suffix",
                    }
                ]
            }
        ]
    )
    result = _run_graph(llm=llm, prepared_input=_prepared_input(), context_config=context.config)

    assert result.iterations == 1
    assert len(result.words) == 1
    assert result.words[0].canonical_writing_ja == "さん"
    assert result.words[0].pos == LexemePos.SUFFIX


def test_mechanical_word_generation_graph_rejects_changed_requested_identity(
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
                        "l": "さま",
                        "r": "さま",
                        "o": "suffix",
                        "g": "honorific suffix",
                        "ga": [],
                        "u": "polite suffix",
                    }
                ]
            }
        ]
    )
    with pytest.raises(ValueError, match="changed requested lexeme identity"):
        _run_graph(llm=llm, prepared_input=_prepared_input(), context_config=context.config)


def test_mechanical_word_generation_graph_trims_overlong_alternate_glosses(
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
                        "l": "さん",
                        "r": "さん",
                        "o": "suffix",
                        "g": "honorific suffix",
                        "ga": ["honorific", "title", "name ending"],
                        "u": "polite name suffix",
                    }
                ]
            }
        ]
    )

    result = _run_graph(llm=llm, prepared_input=_prepared_input(), context_config=context.config)

    assert result.words[0].gloss_alternatives_en == ["honorific", "title"]
