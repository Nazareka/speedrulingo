from __future__ import annotations

from pydantic import BaseModel


class LessonSummary(BaseModel):
    id: str
    order_index: int
    kind: str
    state: str
    is_locked: bool
    attempts_used: int | None = None


class SentencePreview(BaseModel):
    id: str
    ja_text: str
    en_text: str


class UnitSummary(BaseModel):
    id: str
    section_id: str
    section_title: str
    unit_order_index: int
    title: str
    description: str
    lesson_count: int
    completed_lessons: int
    is_locked: bool
    is_completed: bool


class SectionUnits(BaseModel):
    id: str
    title: str
    units: list[UnitSummary]


class PathResponse(BaseModel):
    sections: list[SectionUnits]
    current_unit_id: str | None
    current_lesson_id: str | None


class CurrentCourseResponse(BaseModel):
    course_version_id: str
    course_code: str
    course_version: int
    status: str
    current_unit_id: str | None
    current_lesson_id: str | None


class UnitDetail(BaseModel):
    id: str
    section_id: str
    section_title: str
    unit_order_index: int
    title: str
    description: str
    pattern_tags: list[str]
    theme_tags: list[str]
    article_md: str | None
    lessons: list[LessonSummary]
    sentence_samples: list[SentencePreview]
