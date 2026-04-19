from __future__ import annotations

from functools import lru_cache
from typing import Final, Literal, NotRequired, cast

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from typing_extensions import TypedDict

from course_builder.config import CourseBuildConfig
from course_builder.integrations.llm_client import create_chat_openai as _create_chat_openai
from course_builder.llm.unit_metadata_generation.json_schema import UnitMetadataPayload
from course_builder.llm.unit_metadata_generation.models import (
    PreparedUnitMetadataInput,
    UnitMetadataGenerationResult,
)

GENERATE: Final[Literal["generate_unit_metadata"]] = "generate_unit_metadata"


class InputState(TypedDict):
    prepared_input: PreparedUnitMetadataInput


class OutputState(TypedDict):
    result: UnitMetadataGenerationResult


class Context(TypedDict):
    config: CourseBuildConfig


class State(TypedDict):
    prepared_input: PreparedUnitMetadataInput
    result: NotRequired[UnitMetadataGenerationResult]


Graph = CompiledStateGraph[
    State,
    Context,
    InputState,
    OutputState,
]


def create_chat_openai(*, model: str, reasoning_effort: str) -> object:
    return _create_chat_openai(model=model, reasoning_effort=reasoning_effort)


def generate_unit_metadata(state: State, runtime: Runtime[Context]) -> OutputState:
    _ = runtime
    prepared_input = state["prepared_input"]

    # Temporary stub while unit metadata prompt size is being reworked.
    # Previous LLM-backed implementation kept here for quick restore:
    #
    # prompt_units: list[UnitMetadataPromptUnit] = [
    #     {
    #         "order_index": unit.order_index,
    #         "lesson_count": len(unit.lessons),
    #         "lessons": [
    #             UnitMetadataPromptLesson(
    #                 lesson_index=lesson.lesson_index,
    #                 lesson_kind=lesson.lesson_kind,
    #                 target_item_count=lesson.target_item_count,
    #                 target_word_lemmas=lesson.target_word_lemmas,
    #                 target_pattern_code=lesson.target_pattern_code,
    #                 available_word_lemmas=lesson.available_word_lemmas,
    #                 available_pattern_codes=lesson.available_pattern_codes,
    #             )
    #             for lesson in unit.lessons
    #         ],
    #     }
    #     for unit in prepared_input.units
    # ]
    # response_format = build_unit_metadata_response_format(
    #     unit_count=len(prepared_input.units),
    #     section_theme_codes=prepared_input.section_theme_codes,
    # )
    # llm = cast(
    #     StructuredOutputRunnable,
    #     runtime.context["llm"].with_structured_output(response_format, method="json_schema"),
    # )
    # messages = UNIT_METADATA_GENERATION_PROMPT.format_messages(
    #     section_title=prepared_input.section_title,
    #     section_description=prepared_input.section_description,
    #     section_theme_codes=normalize_prompt_list(prepared_input.section_theme_codes),
    #     unit_specs=format_unit_metadata_spec_lines(prompt_units),
    #     allocated_unit_content=format_unit_metadata_allocated_content(
    #         units=prompt_units,
    #         word_prompt_info_by_lemma=prepared_input.word_prompt_info_by_lemma,
    #         pattern_templates_by_code=prepared_input.pattern_templates_by_code,
    #     ),
    # )
    # raw_result = await llm.ainvoke(messages)
    # metadata_items: list[UnitMetadataPayload] = []
    # for index in range(1, len(prepared_input.units) + 1):
    #     field_name = f"unit_{index}"
    #     if not isinstance(raw_result, dict) or field_name not in raw_result:
    #         raise ValueError(f"Missing structured output field: {field_name}")
    #     metadata_items.append(UnitMetadataPayload.model_validate(raw_result[field_name]))
    # return {"result": UnitMetadataGenerationResult(metadata_items=metadata_items, iterations=1)}

    section_title = prepared_input.section_title.strip() or "Section"
    theme_codes = prepared_input.section_theme_codes[:1] or ["THEME_PLACEHOLDER"]
    metadata_items = [
        UnitMetadataPayload(
            title=f"{section_title} Unit {unit.order_index}",
            description="Placeholder unit description.",
            theme_codes=theme_codes,
        )
        for unit in prepared_input.units
    ]
    return {"result": UnitMetadataGenerationResult(metadata_items=metadata_items, iterations=0)}


@lru_cache(maxsize=1)
def get_unit_metadata_graph() -> Graph:
    builder = StateGraph(
        State,
        context_schema=Context,
        input_schema=InputState,
        output_schema=OutputState,
    )
    builder.add_node(GENERATE, generate_unit_metadata)
    builder.add_edge(START, GENERATE)
    builder.add_edge(GENERATE, END)
    return builder.compile()


async def run_unit_metadata_generation(
    *,
    config: CourseBuildConfig,
    prepared_input: PreparedUnitMetadataInput,
) -> UnitMetadataGenerationResult:
    if not prepared_input.units:
        return UnitMetadataGenerationResult(metadata_items=[], iterations=0)

    # Temporary stub while unit metadata prompt size is being reworked.
    # Previous call path:
    #
    # llm = create_chat_openai(
    #     model=config.llm.unit_metadata_generation.model,
    #     reasoning_effort=config.llm.unit_metadata_generation.reasoning_effort,
    # )
    # result = await graph.ainvoke(
    #     {"prepared_input": prepared_input},
    #     context={"config": config, "llm": llm},
    # )

    graph = get_unit_metadata_graph()
    result = await graph.ainvoke(
        {"prepared_input": prepared_input},
        context={"config": config},
        config={"run_name": "unitMetadataGeneration"},
    )
    return cast(UnitMetadataGenerationResult, result["result"])
