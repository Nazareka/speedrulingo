from __future__ import annotations

from functools import lru_cache
from typing import Final, Literal, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from typing_extensions import TypedDict

from course_builder.config import CourseBuildConfig
from course_builder.llm.anchored_word_generation import get_anchored_word_generation_graph
from course_builder.llm.anchored_word_generation.json_schema import AnchoredWordPayload
from course_builder.llm.anchored_word_generation.models import AnchoredWordGenerationResult
from course_builder.llm.core.client import create_chat_openai
from course_builder.llm.core.models import ExistingWordPromptInfo
from course_builder.llm.master_pattern_vocab_generation.models import (
    MasterPatternVocabGenerationResult,
    PatternRunResult,
    PreparedMasterPatternVocabGenerationInput,
)
from course_builder.llm.mechanical_word_generation import get_mechanical_word_generation_graph
from course_builder.llm.mechanical_word_generation.json_schema import MechanicalWordPayload
from course_builder.llm.mechanical_word_generation.models import MechanicalWordGenerationResult
from course_builder.llm.pattern_vocab_generation import get_pattern_vocab_graph
from course_builder.llm.pattern_vocab_generation.json_schema import WordBatchItemPayload
from course_builder.llm.pattern_vocab_generation.models import PatternVocabGenerationResult

RUN_CURRENT_PATTERN: Final[Literal["run_current_pattern"]] = "run_current_pattern"
END_NODE: Final[Literal["__end__"]] = "__end__"


class InputState(TypedDict):
    prepared_input: PreparedMasterPatternVocabGenerationInput
    pattern_index: int
    pattern_results: list[PatternRunResult]
    existing_words: list[ExistingWordPromptInfo]


class OutputState(TypedDict):
    result: MasterPatternVocabGenerationResult


class Context(TypedDict):
    config: CourseBuildConfig
    llm: BaseChatModel


class State(TypedDict):
    prepared_input: PreparedMasterPatternVocabGenerationInput
    pattern_index: int
    pattern_results: list[PatternRunResult]
    existing_words: list[ExistingWordPromptInfo]
    result: MasterPatternVocabGenerationResult


Graph = CompiledStateGraph[State, Context, InputState, OutputState]


def _extend_existing_words(
    existing_words: list[ExistingWordPromptInfo],
    *,
    generated_words: list[MechanicalWordPayload] | list[AnchoredWordPayload] | list[WordBatchItemPayload],
) -> list[ExistingWordPromptInfo]:
    updated_words = list(existing_words)
    seen_pairs = {(word.canonical_writing_ja, word.reading_kana) for word in updated_words}
    for generated_word in generated_words:
        pair = (generated_word.canonical_writing_ja, generated_word.reading_kana)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        updated_words.append(
            ExistingWordPromptInfo(
                canonical_writing_ja=generated_word.canonical_writing_ja,
                reading_kana=generated_word.reading_kana,
                gloss_primary_en=generated_word.gloss_primary_en,
                gloss_alternatives_en=generated_word.gloss_alternatives_en,
                usage_note_en=generated_word.usage_note_en,
                pos=generated_word.pos.value,
            )
        )
    return updated_words


def route_after_pattern(state: State) -> str:
    if state["pattern_index"] >= len(state["prepared_input"].prepared_patterns):
        return END_NODE
    return RUN_CURRENT_PATTERN


async def run_current_pattern(
    state: State,
    runtime: Runtime[Context],
) -> dict[str, object]:
    prepared = state["prepared_input"].prepared_patterns[state["pattern_index"]]
    existing_words = list(state["existing_words"])
    mechanical_graph = get_mechanical_word_generation_graph()
    anchored_graph = get_anchored_word_generation_graph()
    lexical_graph = get_pattern_vocab_graph()
    pattern_result = PatternRunResult(pattern_code=prepared.pattern_code)

    for mechanical_batch in prepared.mechanical_batches:
        result = await mechanical_graph.ainvoke(
            {"prepared_input": mechanical_batch},
            context={"config": runtime.context["config"], "llm": runtime.context["llm"]},
            config={"run_name": f"mechanicalWordGeneration:{prepared.pattern_code}"},
        )
        mechanical_result = cast(MechanicalWordGenerationResult, result["result"])
        pattern_result.mechanical_results.append(mechanical_result)
        existing_words = _extend_existing_words(existing_words, generated_words=mechanical_result.words)

    for anchored_batch in prepared.anchored_batches:
        result = await anchored_graph.ainvoke(
            {
                "prepared_input": anchored_batch.model_copy(
                    update={"existing_words": existing_words},
                )
            },
            context={"config": runtime.context["config"], "llm": runtime.context["llm"]},
            config={"run_name": f"anchoredWordGeneration:{prepared.pattern_code}"},
        )
        anchored_result = cast(AnchoredWordGenerationResult, result["result"])
        pattern_result.anchored_results.append(anchored_result)
        existing_words = _extend_existing_words(existing_words, generated_words=anchored_result.words)

    if prepared.lexical_input is not None:
        result = await lexical_graph.ainvoke(
            {
                "prepared_input": prepared.lexical_input.model_copy(
                    update={"existing_words": existing_words},
                )
            },
            context={"config": runtime.context["config"], "llm": runtime.context["llm"]},
            config={"run_name": f"patternVocabGeneration:{prepared.pattern_code}"},
        )
        lexical_result = cast(PatternVocabGenerationResult, result["result"])
        pattern_result.lexical_result = lexical_result
        existing_words = _extend_existing_words(existing_words, generated_words=lexical_result.generated_words)

    pattern_results = [*state["pattern_results"], pattern_result]
    return {
        "pattern_index": state["pattern_index"] + 1,
        "pattern_results": pattern_results,
        "existing_words": existing_words,
        "result": MasterPatternVocabGenerationResult(pattern_results=pattern_results),
    }


@lru_cache(maxsize=1)
def get_master_pattern_vocab_graph() -> Graph:
    builder = StateGraph(
        State,
        context_schema=Context,
        input_schema=InputState,
        output_schema=OutputState,
    )
    builder.add_node(RUN_CURRENT_PATTERN, run_current_pattern)
    builder.add_edge(START, RUN_CURRENT_PATTERN)
    builder.add_conditional_edges(RUN_CURRENT_PATTERN, route_after_pattern)
    return builder.compile()


async def run_master_pattern_vocab_generation(
    *,
    config: CourseBuildConfig,
    prepared_input: PreparedMasterPatternVocabGenerationInput,
) -> MasterPatternVocabGenerationResult:
    if not prepared_input.prepared_patterns:
        return MasterPatternVocabGenerationResult()
    graph = get_master_pattern_vocab_graph()
    llm = create_chat_openai(model=config.llm.pattern_vocab_generation_model)
    input_state: InputState = {
        "prepared_input": prepared_input,
        "pattern_index": 0,
        "pattern_results": [],
        "existing_words": list(prepared_input.existing_words),
    }
    result = await graph.ainvoke(
        input_state,
        context={"config": config, "llm": llm},
        config={"run_name": "masterPatternVocabGeneration"},
    )
    return cast(MasterPatternVocabGenerationResult, result["result"])
