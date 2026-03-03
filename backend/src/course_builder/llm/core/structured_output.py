from __future__ import annotations


def _normalize_openai_strict_schema_node(node: object) -> object:
    if isinstance(node, dict):
        normalized_node = {key: _normalize_openai_strict_schema_node(value) for key, value in node.items()}
        if "$ref" in normalized_node:
            return {"$ref": normalized_node["$ref"]}
        properties = normalized_node.get("properties")
        if isinstance(properties, dict):
            normalized_node["required"] = list(properties.keys())
        return normalized_node
    if isinstance(node, list):
        return [_normalize_openai_strict_schema_node(item) for item in node]
    return node


def build_response_format(*, name: str, schema: dict[str, object]) -> dict[str, object]:
    return {
        "name": name,
        "schema": _normalize_openai_strict_schema_node(schema),
        "strict": True,
    }
