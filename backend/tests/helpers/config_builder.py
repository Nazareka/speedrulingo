from __future__ import annotations

from copy import deepcopy
from typing import Any

import yaml

from tests.helpers.test_config_source import TEST_CONFIG_YAML

ConfigPath = tuple[str | int, ...]


def load_base_test_config_data() -> dict[str, Any]:
    loaded = yaml.safe_load(TEST_CONFIG_YAML)
    if not isinstance(loaded, dict):
        msg = "Expected TEST_CONFIG_YAML to load into a mapping"
        raise TypeError(msg)
    return cast_config_dict(loaded)


def build_test_config_data(
    *,
    updates: dict[ConfigPath, Any] | None = None,
    appends: dict[ConfigPath, list[Any]] | None = None,
) -> dict[str, Any]:
    config_data = deepcopy(load_base_test_config_data())
    for path, value in (updates or {}).items():
        _set_path_value(config_data, path=path, value=value)
    for path, values in (appends or {}).items():
        _append_path_values(config_data, path=path, values=values)
    return config_data


def build_test_config_yaml(
    *,
    updates: dict[ConfigPath, Any] | None = None,
    appends: dict[ConfigPath, list[Any]] | None = None,
) -> str:
    return yaml.safe_dump(
        build_test_config_data(updates=updates, appends=appends),
        allow_unicode=True,
        sort_keys=False,
    )


def cast_config_dict(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        msg = "Expected config value to be a mapping"
        raise TypeError(msg)
    return value


def _set_path_value(config_data: dict[str, Any], *, path: ConfigPath, value: Any) -> None:
    parent, final_key = _resolve_parent(config_data, path=path)
    if isinstance(final_key, int):
        if not isinstance(parent, list):
            msg = f"Expected list parent for indexed path {path!r}"
            raise TypeError(msg)
        parent[final_key] = value
        return
    if not isinstance(parent, dict):
        msg = f"Expected mapping parent for path {path!r}"
        raise TypeError(msg)
    parent[final_key] = value


def _append_path_values(config_data: dict[str, Any], *, path: ConfigPath, values: list[Any]) -> None:
    parent, final_key = _resolve_parent(config_data, path=path)
    if isinstance(final_key, int):
        msg = f"Append paths must end in a mapping key, got indexed path {path!r}"
        raise TypeError(msg)
    if not isinstance(parent, dict):
        msg = f"Expected mapping parent for path {path!r}"
        raise TypeError(msg)
    current_value = parent[final_key]
    if not isinstance(current_value, list):
        msg = f"Expected list at path {path!r}"
        raise TypeError(msg)
    current_value.extend(values)


def _resolve_parent(config_data: dict[str, Any], *, path: ConfigPath) -> tuple[object, str | int]:
    if not path:
        msg = "Config path must not be empty"
        raise ValueError(msg)
    current: object = config_data
    for segment in path[:-1]:
        if isinstance(segment, int):
            if not isinstance(current, list):
                msg = f"Expected list while traversing indexed segment {segment!r} in {path!r}"
                raise TypeError(msg)
            current = current[segment]
            continue
        if not isinstance(current, dict):
            msg = f"Expected mapping while traversing segment {segment!r} in {path!r}"
            raise TypeError(msg)
        current = current[segment]
    return current, path[-1]
