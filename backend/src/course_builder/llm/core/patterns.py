from __future__ import annotations


def normalize_pattern_code_alias(pattern_code: str, *, allowed_codes: set[str]) -> str | None:
    if pattern_code in allowed_codes:
        return pattern_code
    if pattern_code.endswith("_STATEMENT"):
        base_code = pattern_code.removesuffix("_STATEMENT")
        if base_code in allowed_codes:
            return base_code
    return None
