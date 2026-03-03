from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from course_builder.llm.core.structured_output import build_response_format


class UnitMetadataPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    theme_codes: list[str] = Field(min_length=1)


def build_unit_metadata_response_format(*, unit_count: int, section_theme_codes: list[str]) -> dict[str, object]:
    if not section_theme_codes:
        raise ValueError("section_theme_codes cannot be empty")
    properties = {
        f"unit_{index}": {
            "type": "object",
            "additionalProperties": False,
            "description": f"Metadata for unit {index}.",
            "properties": {
                "title": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Short unit title summarizing the learner-facing focus of this unit.",
                },
                "description": {
                    "type": "string",
                    "minLength": 1,
                    "description": "One concise sentence explaining what the learner practices in this unit.",
                },
                "theme_codes": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "enum": list(dict.fromkeys(section_theme_codes))},
                    "description": "Theme codes active in this unit. Use only codes from the provided section theme scope.",
                },
            },
        }
        for index in range(1, unit_count + 1)
    }
    return build_response_format(
        name="unit_out",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
        },
    )
