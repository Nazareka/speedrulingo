from __future__ import annotations

from typing import cast

from langchain_core.messages import BaseMessage
from pydantic import BaseModel


class SequentialStructuredLlm:
    def __init__(self, *, payloads: list[dict[str, object]], record_messages: bool = False) -> None:
        self._payloads = payloads
        self.calls = 0
        self.messages: list[list[BaseMessage]] = []
        self._record_messages = record_messages
        self._schema: object | None = None

    def with_structured_output(
        self,
        schema: object,
        *,
        method: str,
        **kwargs: object,
    ) -> SequentialStructuredLlm:
        _ = method
        _ = kwargs
        self._schema = schema
        return self

    def invoke(self, messages: object) -> object:
        parsed_messages = cast(list[BaseMessage], messages)
        if self._record_messages:
            self.messages.append(parsed_messages)
        payload = self._payloads[self.calls] if self.calls < len(self._payloads) else self._payloads[-1]
        self.calls += 1
        assert self._schema is not None
        if isinstance(self._schema, type) and issubclass(self._schema, BaseModel):
            normalized_payload = payload
            if isinstance(payload, dict):
                schema_field_names = list(self._schema.model_fields)
                if schema_field_names and all(name.startswith("unit_") for name in schema_field_names):
                    unit_entries = [payload[key] for key in sorted(payload) if key.startswith("unit_")]
                    if not unit_entries:
                        unit_entries = [
                            {"title": "Generated Unit", "description": "Generated unit.", "theme_codes": []}
                        ]
                    normalized_payload = {
                        field_name: unit_entries[min(index, len(unit_entries) - 1)]
                        for index, field_name in enumerate(schema_field_names)
                    }
            return self._schema.model_validate(normalized_payload).model_dump(
                mode="python",
                warnings=False,
                by_alias=False,
            )
        if isinstance(self._schema, dict) and isinstance(payload, dict):
            schema_body = self._schema.get("schema")
            if isinstance(schema_body, dict):
                properties = schema_body.get("properties")
                if isinstance(properties, dict):
                    property_names = list(properties)
                    if property_names and all(name.startswith("unit_") for name in property_names):
                        unit_entries = [payload[key] for key in sorted(payload) if key.startswith("unit_")]
                        if not unit_entries:
                            unit_entries = [
                                {"title": "Generated Unit", "description": "Generated unit.", "theme_codes": []}
                            ]
                        return {
                            field_name: unit_entries[min(index, len(unit_entries) - 1)]
                            for index, field_name in enumerate(property_names)
                        }
        return payload

    async def ainvoke(self, messages: object) -> object:
        return self.invoke(messages)
