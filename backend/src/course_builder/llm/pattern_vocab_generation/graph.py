from __future__ import annotations

from functools import lru_cache
import logging
from typing import Final, Literal, NotRequired, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import RetryPolicy
from typing_extensions import TypedDict

from course_builder.config import CourseBuildConfig
from course_builder.lexicon import LexemePos, is_kana_text
from course_builder.llm.core.formatting import (
    format_existing_word_lines,
    format_pattern_scope_lines,
)
from course_builder.llm.core.models import ExistingWordPromptInfo
from course_builder.llm.core.types import StructuredOutputRunnable
from course_builder.llm.pattern_vocab_generation.json_schema import (
    WordBatchItemPayload,
    WordBatchPayload,
    build_pattern_vocab_response_format,
)
from course_builder.llm.pattern_vocab_generation.models import (
    PatternVocabGenerationResult,
    PreparedPatternVocabGenerationInput,
)
from course_builder.llm.pattern_vocab_generation.prompts import PATTERN_VOCAB_GENERATION_PROMPT
from course_builder.llm.pattern_vocab_generation.utils import sentence_uses_generated_lemma
from course_builder.sentence_processing import VocabItem, build_japanese_sentence_analysis
from course_builder.sentence_processing.errors import UnsupportedSentenceStructureError

LOAD_GENERATION_STATE: Final[Literal["load_generation_state"]] = "load_generation_state"
GENERATE_PATTERN_VOCAB_WITH_MODEL: Final[Literal["generate_pattern_vocab_with_model"]] = (
    "generate_pattern_vocab_with_model"
)
VALIDATE_GENERATED_WORD_BATCH: Final[Literal["validate_generated_word_batch"]] = "validate_generated_word_batch"
REQUIRED_EXAMPLE_SENTENCE_COUNT = 2
END_NODE: Final[Literal["__end__"]] = "__end__"
RouteAfterStateLoad = Literal["generate_pattern_vocab_with_model", "__end__"]
LOGGER = logging.getLogger(__name__)


class InputState(TypedDict):
    prepared_input: PreparedPatternVocabGenerationInput


class OutputState(TypedDict):
    result: PatternVocabGenerationResult


class Context(TypedDict):
    config: CourseBuildConfig
    llm: BaseChatModel


class State(TypedDict):
    prepared_input: PreparedPatternVocabGenerationInput
    existing_words: NotRequired[list[ExistingWordPromptInfo]]
    generated_batch: NotRequired[list[WordBatchItemPayload]]
    result: NotRequired[PatternVocabGenerationResult]


class LoadGenerationStateUpdate(TypedDict):
    existing_words: list[ExistingWordPromptInfo]
    generated_batch: list[WordBatchItemPayload]
    result: PatternVocabGenerationResult


class GenerateWordBatchUpdate(TypedDict):
    generated_batch: list[WordBatchItemPayload]


class ValidateGeneratedWordBatchUpdate(TypedDict):
    result: PatternVocabGenerationResult


Graph = CompiledStateGraph[
    State,
    Context,
    InputState,
    OutputState,
]


def load_generation_state(state: State) -> LoadGenerationStateUpdate:
    prepared_input = state["prepared_input"]
    return {
        "existing_words": list(prepared_input.existing_words),
        "generated_batch": [],
        "result": PatternVocabGenerationResult(
            words_created=0,
            section_words_created=0,
            word_theme_links_created=0,
            iterations=0,
            inventory_complete=prepared_input.max_words == 0,
            example_sentences=[],
            generated_words=[],
        ),
    }


def route_after_state_load(state: State) -> RouteAfterStateLoad:
    if state["prepared_input"].max_words == 0:
        return END_NODE
    return GENERATE_PATTERN_VOCAB_WITH_MODEL


async def generate_pattern_vocab_with_model(
    state: State,
    runtime: Runtime[Context],
) -> GenerateWordBatchUpdate:
    config = runtime.context["config"]
    section = config.current_section
    response_format = build_pattern_vocab_response_format(
        min_item_count=state["prepared_input"].min_words,
        max_item_count=state["prepared_input"].max_words,
    )
    llm = cast(
        StructuredOutputRunnable,
        runtime.context["llm"].with_structured_output(response_format, method="json_schema"),
    )
    LOGGER.info(
        "Pattern vocab generation: requesting %s-%s words across %s allowed patterns",
        state["prepared_input"].min_words,
        state["prepared_input"].max_words,
        len(state["prepared_input"].allowed_pattern_codes),
    )

    existing_word_lines = format_existing_word_lines(state.get("existing_words", []))
    messages = PATTERN_VOCAB_GENERATION_PROMPT.format_messages(
        scope_title=section.title,
        scope_description=section.generation_description,
        primary_themes=", ".join(section.primary_themes),
        secondary_themes=", ".join(section.secondary_themes),
        patterns_scope=format_pattern_scope_lines(
            pattern_templates_by_code={pattern.code: pattern.templates for pattern in config.patterns},
            allowed_pattern_codes=state["prepared_input"].allowed_pattern_codes,
        ),
        existing_words=existing_word_lines,
    )
    payload = WordBatchPayload.model_validate(await llm.ainvoke(messages))
    LOGGER.info("Pattern vocab generation: received %s items", len(payload.items))
    return {"generated_batch": payload.items}


def validate_generated_word_batch(state: State) -> ValidateGeneratedWordBatchUpdate:
    generated_batch = state.get("generated_batch", [])
    min_requested_count = state["prepared_input"].min_words
    max_requested_count = state["prepared_input"].max_words
    existing_words = state.get("existing_words", [])
    existing_lemmas = {word.canonical_writing_ja for word in existing_words}
    existing_pairs = {(word.canonical_writing_ja, word.reading_kana) for word in existing_words}
    validation_errors: list[str] = []
    accepted_batch: list[WordBatchItemPayload] = []
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
            for word in existing_words
        ],
        *[
            VocabItem(
                word_id=None,
                canonical_writing_ja=candidate.canonical_writing_ja,
                reading_kana=candidate.reading_kana,
                gloss_primary_en=candidate.gloss_primary_en,
                gloss_alternatives_en=tuple(candidate.gloss_alternatives_en),
                usage_note_en=candidate.usage_note_en,
                pos=candidate.pos.value,
            )
            for candidate in generated_batch
        ],
    ]

    if len(generated_batch) > max_requested_count:
        msg = f"Structured output generated more items than requested: {len(generated_batch)} > {max_requested_count}"
        raise RuntimeError(msg)
    if len(generated_batch) < min_requested_count:
        msg = f"Structured output generated fewer items than required: {len(generated_batch)} < {min_requested_count}"
        raise RuntimeError(msg)

    seen_lemma_reading_pairs: set[tuple[str, str]] = set()
    for candidate in generated_batch:
        if candidate.pos.value in LexemePos.mechanical_values():
            msg = (
                "Word generation produced a mechanical form that should come from config, "
                f"not the LLM: {candidate.canonical_writing_ja} ({candidate.pos.value})"
            )
            raise RuntimeError(msg)
        candidate_errors: list[str] = []
        if candidate.canonical_writing_ja != candidate.canonical_writing_ja.strip():
            candidate_errors.append(
                f"{candidate.canonical_writing_ja}: remove leading/trailing whitespace from canonical_writing_ja"
            )
        if candidate.reading_kana != candidate.reading_kana.strip():
            candidate_errors.append(
                f"{candidate.canonical_writing_ja}: remove leading/trailing whitespace from reading_kana"
            )
        lemma_reading_pair = (candidate.canonical_writing_ja, candidate.reading_kana)
        if lemma_reading_pair in seen_lemma_reading_pairs:
            candidate_errors.append(
                f"{candidate.canonical_writing_ja}: duplicate lemma/reading pair in generated batch"
            )
        else:
            seen_lemma_reading_pairs.add(lemma_reading_pair)
        if lemma_reading_pair in existing_pairs:
            candidate_errors.append(f"{candidate.canonical_writing_ja}: lemma/reading pair already exists in inventory")
        elif candidate.canonical_writing_ja in existing_lemmas:
            candidate_errors.append(f"{candidate.canonical_writing_ja}: lemma already exists in inventory")
        if not candidate.gloss_primary_en.strip():
            candidate_errors.append(f"{candidate.canonical_writing_ja}: gloss_primary_en must not be empty")
        if "/" in candidate.gloss_primary_en or ";" in candidate.gloss_primary_en:
            candidate_errors.append(
                f"{candidate.canonical_writing_ja}: gloss_primary_en must use one clean gloss without '/' or ';'"
            )
        if not candidate.reading_kana.strip():
            candidate_errors.append(f"{candidate.canonical_writing_ja}: reading_kana must not be empty")
        if any(char.isspace() for char in candidate.reading_kana):
            candidate_errors.append(f"{candidate.canonical_writing_ja}: reading_kana must not contain spaces")
        if not is_kana_text(candidate.reading_kana):
            candidate_errors.append(f"{candidate.canonical_writing_ja}: reading_kana must contain kana only")
        if len(candidate.example_sentences) != REQUIRED_EXAMPLE_SENTENCE_COUNT:
            candidate_errors.append(
                f"{candidate.canonical_writing_ja}: exactly {REQUIRED_EXAMPLE_SENTENCE_COUNT} example_sentences are required"
            )
        for sentence in candidate.example_sentences:
            if sentence.ja_text != sentence.ja_text.strip():
                candidate_errors.append(
                    f"{candidate.canonical_writing_ja}: example sentence ja_text must not have outer whitespace"
                )
            if sentence.en_text != sentence.en_text.strip():
                candidate_errors.append(
                    f"{candidate.canonical_writing_ja}: example sentence en_text must not have outer whitespace"
                )
            if not sentence_uses_generated_lemma(candidate=candidate, sentence_ja_text=sentence.ja_text):
                candidate_errors.append(
                    f"{candidate.canonical_writing_ja}: each example sentence must include the generated lemma in ja_text"
                )
            try:
                build_japanese_sentence_analysis(
                    sentence_ja=sentence.ja_text,
                    vocab=batch_validation_vocab,
                )
            except UnsupportedSentenceStructureError as exc:
                candidate_errors.append(
                    f"{candidate.canonical_writing_ja}: example sentence must use only current available vocab; {exc}"
                )
        if candidate_errors:
            validation_errors.extend(candidate_errors)
        else:
            accepted_batch.append(candidate)
    if validation_errors:
        raise ValueError("; ".join(validation_errors))
    return {
        "result": PatternVocabGenerationResult(
            words_created=len(accepted_batch),
            section_words_created=len(accepted_batch),
            word_theme_links_created=0,
            iterations=1,
            inventory_complete=True,
            example_sentences=[
                example_sentence for candidate in accepted_batch for example_sentence in candidate.example_sentences
            ],
            generated_words=accepted_batch,
        ),
    }


@lru_cache(maxsize=1)
def get_pattern_vocab_graph() -> Graph:
    workflow = StateGraph(
        State,
        context_schema=Context,
        input_schema=InputState,
        output_schema=OutputState,
    )
    workflow.add_node(LOAD_GENERATION_STATE, load_generation_state)
    workflow.add_node(
        GENERATE_PATTERN_VOCAB_WITH_MODEL,
        generate_pattern_vocab_with_model,
        retry_policy=RetryPolicy(max_attempts=1),
    )
    workflow.add_node(VALIDATE_GENERATED_WORD_BATCH, validate_generated_word_batch)
    workflow.add_edge(START, LOAD_GENERATION_STATE)
    workflow.add_conditional_edges(LOAD_GENERATION_STATE, route_after_state_load)
    workflow.add_edge(GENERATE_PATTERN_VOCAB_WITH_MODEL, VALIDATE_GENERATED_WORD_BATCH)
    workflow.add_edge(VALIDATE_GENERATED_WORD_BATCH, END_NODE)
    return workflow.compile()
