from __future__ import annotations

from functools import lru_cache
from typing import Final, Literal, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from typing_extensions import TypedDict

from course_builder.config import CourseBuildConfig
from course_builder.llm.core.formatting import format_target_lexeme_lines
from course_builder.llm.core.types import StructuredOutputRunnable
from course_builder.llm.mechanical_word_generation.json_schema import (
    MechanicalWordBatchPayload,
    MechanicalWordPayload,
    build_mechanical_word_generation_response_format,
)
from course_builder.llm.mechanical_word_generation.models import (
    MechanicalWordGenerationResult,
    PreparedMechanicalWordGenerationInput,
)
from course_builder.llm.mechanical_word_generation.prompts import MECHANICAL_WORD_GENERATION_PROMPT

GENERATE: Final[Literal["generate_mechanical_words"]] = "generate_mechanical_words"
MAX_ALTERNATE_GLOSSES: Final[int] = 2


class InputState(TypedDict):
    prepared_input: PreparedMechanicalWordGenerationInput


class OutputState(TypedDict):
    result: MechanicalWordGenerationResult


class Context(TypedDict):
    config: CourseBuildConfig
    llm: BaseChatModel


class State(TypedDict):
    prepared_input: PreparedMechanicalWordGenerationInput
    result: MechanicalWordGenerationResult


def _trim_overlong_alternate_glosses(payload: object) -> object:
    if not isinstance(payload, dict):
        return payload
    item_key = "i" if "i" in payload else "items"
    items = payload.get(item_key)
    if not isinstance(items, list):
        return payload

    normalized_items: list[object] = []
    for item in items:
        if not isinstance(item, dict):
            normalized_items.append(item)
            continue
        alternate_glosses = item.get("ga")
        if isinstance(alternate_glosses, list) and len(alternate_glosses) > MAX_ALTERNATE_GLOSSES:
            # Temporary workaround: GPT-5.4 occasionally returns more alternate glosses
            # than requested even under structured output, so trim to the schema max.
            normalized_items.append({**item, "ga": alternate_glosses[:MAX_ALTERNATE_GLOSSES]})
            continue
        normalized_items.append(item)
    return {**payload, item_key: normalized_items}


Graph = CompiledStateGraph[
    State,
    Context,
    InputState,
    OutputState,
]


async def generate_mechanical_words(
    state: State,
    runtime: Runtime[Context],
) -> OutputState:
    prepared_input = state["prepared_input"]
    response_format = build_mechanical_word_generation_response_format(item_count=len(prepared_input.lexemes))
    llm = cast(
        StructuredOutputRunnable,
        runtime.context["llm"].with_structured_output(response_format, method="json_schema"),
    )
    lexeme_lines = format_target_lexeme_lines(
        (lexeme.canonical_writing_ja, lexeme.reading_kana, lexeme.pos.value) for lexeme in prepared_input.lexemes
    )
    raw_payload = await llm.ainvoke(MECHANICAL_WORD_GENERATION_PROMPT.format_messages(requested_lexemes=lexeme_lines))
    payload = MechanicalWordBatchPayload.model_validate(
        _trim_overlong_alternate_glosses(raw_payload)
    )
    validated_items: list[MechanicalWordPayload] = []
    for payload_item, expected in zip(payload.items, prepared_input.lexemes, strict=True):
        if (
            payload_item.canonical_writing_ja != expected.canonical_writing_ja
            or payload_item.reading_kana != expected.reading_kana
            or payload_item.pos != expected.pos.value
        ):
            msg = (
                "Mechanical word generation changed requested lexeme identity: "
                f"expected={expected.canonical_writing_ja}|{expected.reading_kana}|{expected.pos.value} "
                f"actual={payload_item.canonical_writing_ja}|{payload_item.reading_kana}|{payload_item.pos}"
            )
            raise ValueError(msg)
        if "/" in payload_item.gloss_primary_en or ";" in payload_item.gloss_primary_en:
            msg = (
                f"Mechanical word generation produced an invalid primary gloss for {payload_item.canonical_writing_ja}"
            )
            raise ValueError(msg)
        validated_items.append(payload_item)

    return {
        "result": MechanicalWordGenerationResult(
            words=validated_items,
            iterations=1,
        )
    }


@lru_cache(maxsize=1)
def get_mechanical_word_generation_graph() -> Graph:
    builder = StateGraph(
        State,
        context_schema=Context,
        input_schema=InputState,
        output_schema=OutputState,
    )
    builder.add_node(GENERATE, generate_mechanical_words)
    builder.add_edge(START, GENERATE)
    builder.add_edge(GENERATE, END)
    return builder.compile()
