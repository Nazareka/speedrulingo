from __future__ import annotations

from pathlib import Path

import pytest

from course_builder.build_runs.models import BuildRequest


def test_build_request_rejects_section_code_with_all_sections() -> None:
    with pytest.raises(ValueError, match="must not be provided when --all-sections is used"):
        BuildRequest(
            config=Path("config/en-ja-v1"),
            build_version=1,
            section_code="PRE_A1",
            all_sections=True,
        )
