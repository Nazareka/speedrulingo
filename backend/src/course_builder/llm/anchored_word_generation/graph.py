from __future__ import annotations

from functools import lru_cache
from typing import Final, Literal, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from typing_extensions import TypedDict

from course_builder.config import CourseBuildConfig
from course_builder.lexicon import is_kana_text
from course_builder.llm.anchored_word_generation.json_schema import (
    AnchoredWordBatchPayload,
    AnchoredWordPayload,
    build_anchored_word_generation_response_format,
)
from course_builder.llm.anchored_word_generation.models import (
    AnchoredWordGenerationResult,
    PreparedAnchoredWordGenerationInput,
)
from course_builder.llm.anchored_word_generation.prompts import ANCHORED_WORD_GENERATION_PROMPT
from course_builder.llm.core.formatting import (
    format_existing_word_lines,
    format_pattern_scope_lines,
    format_target_lexeme_lines,
)
from course_builder.llm.core.types import StructuredOutputRunnable
from course_builder.sentence_processing import VocabItem, build_japanese_sentence_analysis
from course_builder.sentence_processing.errors import UnsupportedSentenceStructureError

GENERATE: Final[Literal["generate_anchored_words"]] = "generate_anchored_words"


class InputState(TypedDict):
    prepared_input: PreparedAnchoredWordGenerationInput


class OutputState(TypedDict):
    result: AnchoredWordGenerationResult


class Context(TypedDict):
    config: CourseBuildConfig
    llm: BaseChatModel


class State(TypedDict):
    prepared_input: PreparedAnchoredWordGenerationInput
    result: AnchoredWordGenerationResult


Graph = CompiledStateGraph[
    State,
    Context,
    InputState,
    OutputState,
]


async def generate_anchored_words(state: State, runtime: Runtime[Context]) -> OutputState:
    prepared_input = state["prepared_input"]
    config = runtime.context["config"]
    response_format = build_anchored_word_generation_response_format(item_count=len(prepared_input.targets))
    llm = cast(
        StructuredOutputRunnable,
        runtime.context["llm"].with_structured_output(response_format, method="json_schema"),
    )
    target_lines = format_target_lexeme_lines(
        (target.canonical_writing_ja, target.reading_kana, target.pos.value) for target in prepared_input.targets
    )
    current_word_lines = format_existing_word_lines(prepared_input.existing_words)
    payload = AnchoredWordBatchPayload.model_validate(
        await llm.ainvoke(
            ANCHORED_WORD_GENERATION_PROMPT.format_messages(
                current_words=current_word_lines,
                patterns_scope=format_pattern_scope_lines(
                    pattern_templates_by_code={pattern.code: pattern.templates for pattern in config.patterns},
                    allowed_pattern_codes=prepared_input.allowed_pattern_codes,
                ),
                targets=target_lines,
            )
        )
    )
    validated_items: list[AnchoredWordPayload] = []
    batch_validation_vocab = [
        *[
            VocabItem(
                word_id=None,
                canonical_writing_ja=word.canonical_writing_ja,
                reading_kana=word.reading_kana,
                gloss_primary_en=word.gloss_primary_en,
                gloss_alternatives_en=tuple(word.gloss_alternatives_en),
                usage_note_en=word.usage_note_en,
                pos=word.pos,
            )
            for word in prepared_input.existing_words
        ],
        *[
            VocabItem(
                word_id=None,
                canonical_writing_ja=item.canonical_writing_ja,
                reading_kana=item.reading_kana,
                gloss_primary_en=item.gloss_primary_en,
                gloss_alternatives_en=tuple(item.gloss_alternatives_en),
                usage_note_en=item.usage_note_en,
                pos=item.pos.value,
            )
            for item in payload.items
        ],
    ]
    for payload_item, expected in zip(payload.items, prepared_input.targets, strict=True):
        if (
            payload_item.canonical_writing_ja != expected.canonical_writing_ja
            or payload_item.reading_kana != expected.reading_kana
            or payload_item.pos != expected.pos.value
        ):
            msg = (
                "Anchored word generation changed requested lexeme identity: "
                f"expected={expected.canonical_writing_ja}|{expected.reading_kana}|{expected.pos.value} "
                f"actual={payload_item.canonical_writing_ja}|{payload_item.reading_kana}|{payload_item.pos}"
            )
            raise ValueError(msg)
        if not payload_item.gloss_primary_en.strip():
            raise ValueError(f"{payload_item.canonical_writing_ja}: gloss_primary_en must not be empty")
        if "/" in payload_item.gloss_primary_en or ";" in payload_item.gloss_primary_en:
            raise ValueError(
                f"{payload_item.canonical_writing_ja}: gloss_primary_en must use one clean gloss without '/' or ';'"
            )
        if not payload_item.reading_kana.strip():
            raise ValueError(f"{payload_item.canonical_writing_ja}: reading_kana must not be empty")
        if any(char.isspace() for char in payload_item.reading_kana):
            raise ValueError(f"{payload_item.canonical_writing_ja}: reading_kana must not contain spaces")
        if not is_kana_text(payload_item.reading_kana):
            raise ValueError(f"{payload_item.canonical_writing_ja}: reading_kana must contain kana only")
        for sentence in payload_item.example_sentences:
            if sentence.ja_text != sentence.ja_text.strip():
                raise ValueError(
                    f"{payload_item.canonical_writing_ja}: example sentence ja_text must not have outer whitespace"
                )
            if sentence.en_text != sentence.en_text.strip():
                raise ValueError(
                    f"{payload_item.canonical_writing_ja}: example sentence en_text must not have outer whitespace"
                )
            try:
                build_japanese_sentence_analysis(
                    sentence_ja=sentence.ja_text,
                    vocab=batch_validation_vocab,
                )
            except UnsupportedSentenceStructureError as exc:
                raise ValueError(
                    f"{payload_item.canonical_writing_ja}: example sentence must use only current available vocab; {exc}"
                ) from exc
        validated_items.append(payload_item)
    return {"result": AnchoredWordGenerationResult(words=validated_items, iterations=1)}


@lru_cache(maxsize=1)
def get_anchored_word_generation_graph() -> Graph:
    builder = StateGraph(
        State,
        context_schema=Context,
        input_schema=InputState,
        output_schema=OutputState,
    )
    builder.add_node(GENERATE, generate_anchored_words)
    builder.add_edge(START, GENERATE)
    builder.add_edge(GENERATE, END)
    return builder.compile()
