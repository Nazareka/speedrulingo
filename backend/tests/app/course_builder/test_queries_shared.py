from __future__ import annotations

import pytest

from course_builder.queries.shared import CourseVersionQueries


def test_course_version_queries_rejects_overriding_reserved_shared_methods() -> None:
    with pytest.raises(TypeError, match="cannot override shared query methods"):

        class InvalidQueries(CourseVersionQueries):
            def get_section_id(self) -> str | None:
                return None
