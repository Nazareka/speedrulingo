from __future__ import annotations

from collections import defaultdict

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.content.schemas import (
    CurrentCourseResponse,
    LessonSummary,
    PathResponse,
    SectionUnits,
    SentencePreview,
    UnitDetail,
    UnitSummary,
)
from domain.auth.models import UserCourseEnrollment
from domain.content.display import display_sentence_text_ja, sentence_uses_kana_display
from domain.content.models import (
    CourseVersion,
    Item,
    Lesson,
    LessonSentence,
    Pattern,
    Section,
    Sentence,
    SentenceUnit,
    ThemeTag,
    Unit,
    UnitPatternLink,
    UnitThemeLink,
)
from domain.learning.models import ExamAttempt, UserLessonProgress


def _get_course_units(db: Session, course_version_id: str) -> list[tuple[Section, Unit]]:
    rows = db.execute(
        select(Section, Unit)
        .join(Unit, Unit.section_id == Section.id)
        .where(Section.course_version_id == course_version_id)
        .order_by(Section.order_index.asc(), Unit.order_index.asc())
    )
    return list(rows.tuples())


def _get_progress_by_lesson(db: Session, enrollment_id: str) -> dict[str, str]:
    return {
        progress.lesson_id: progress.state
        for progress in db.scalars(select(UserLessonProgress).where(UserLessonProgress.enrollment_id == enrollment_id))
    }


def _get_exam_attempts_by_lesson(db: Session, enrollment_id: str) -> dict[str, int]:
    attempt_rows = list(
        db.execute(
            select(ExamAttempt.lesson_id, ExamAttempt.attempt_no)
            .where(ExamAttempt.enrollment_id == enrollment_id)
            .order_by(ExamAttempt.lesson_id.asc(), ExamAttempt.attempt_no.desc())
        )
    )
    attempts_by_lesson: dict[str, int] = {}
    for lesson_id, attempt_no in attempt_rows:
        attempts_by_lesson.setdefault(lesson_id, attempt_no)
    return attempts_by_lesson


def _build_lesson_summaries_for_unit(
    lessons: list[Lesson],
    progress_by_lesson: dict[str, str],
    attempts_by_lesson: dict[str, int],
) -> list[LessonSummary]:
    lesson_summaries: list[LessonSummary] = []
    unlocked = True
    for lesson in lessons:
        if lesson.kind == "exam":
            normal_lessons = [candidate for candidate in lessons if candidate.kind == "normal"]
            unlocked = all(progress_by_lesson.get(candidate.id) == "completed" for candidate in normal_lessons)
        lesson_summaries.append(
            LessonSummary(
                id=lesson.id,
                order_index=lesson.order_index,
                kind=lesson.kind,
                state=progress_by_lesson.get(lesson.id, "not_started"),
                is_locked=not unlocked,
                attempts_used=attempts_by_lesson.get(lesson.id) if lesson.kind == "exam" else None,
            )
        )
    return lesson_summaries


def _get_lessons_with_items(db: Session, unit_ids: list[str]) -> dict[str, list[Lesson]]:
    if not unit_ids:
        return {}

    rows = db.execute(
        select(Lesson, func.count(Item.id).label("item_count"))
        .outerjoin(Item, Item.lesson_id == Lesson.id)
        .where(Lesson.unit_id.in_(unit_ids))
        .group_by(Lesson.id)
        .order_by(Lesson.unit_id.asc(), Lesson.order_index.asc())
    )
    lessons_by_unit: dict[str, list[Lesson]] = defaultdict(list)
    for lesson, item_count in rows.tuples():
        if item_count > 0:
            lessons_by_unit[lesson.unit_id].append(lesson)
    return lessons_by_unit


def _build_unit_summaries(
    db: Session, enrollment: UserCourseEnrollment
) -> tuple[list[tuple[Section, Unit]], list[UnitSummary]]:
    section_units = _get_course_units(db, enrollment.course_version_id)
    if not section_units:
        return [], []

    units = [unit for _, unit in section_units]
    unit_ids = [unit.id for unit in units]
    lessons_by_unit = _get_lessons_with_items(db, unit_ids)
    exam_lesson_by_unit_id = {
        unit_id: next((lesson for lesson in unit_lessons if lesson.kind == "exam"), None)
        for unit_id, unit_lessons in lessons_by_unit.items()
    }

    progress_by_lesson = _get_progress_by_lesson(db, enrollment.id)
    attempts_by_lesson = _get_exam_attempts_by_lesson(db, enrollment.id)
    summaries: list[UnitSummary] = []
    previous_unit_completed = True

    for section, unit in section_units:
        unit_lessons = lessons_by_unit.get(unit.id, [])
        completed_lessons = sum(1 for lesson in unit_lessons if progress_by_lesson.get(lesson.id) == "completed")
        exam_lesson = exam_lesson_by_unit_id.get(unit.id)
        is_completed = exam_lesson is not None and progress_by_lesson.get(exam_lesson.id) == "completed"
        lesson_summaries = _build_lesson_summaries_for_unit(unit_lessons, progress_by_lesson, attempts_by_lesson)
        summaries.append(
            UnitSummary(
                id=unit.id,
                section_id=section.id,
                section_title=section.title,
                unit_order_index=unit.order_index,
                title=unit.title,
                description=unit.description,
                lesson_count=len(unit_lessons),
                completed_lessons=completed_lessons,
                is_locked=not previous_unit_completed,
                is_completed=is_completed,
                lessons=lesson_summaries,
            )
        )
        previous_unit_completed = is_completed

    return section_units, summaries


def list_units(db: Session, enrollment: UserCourseEnrollment) -> list[UnitSummary]:
    _, summaries = _build_unit_summaries(db, enrollment)
    return summaries


def get_path(db: Session, enrollment: UserCourseEnrollment) -> PathResponse:
    section_units, summaries = _build_unit_summaries(db, enrollment)
    summaries_by_id = {summary.id: summary for summary in summaries}
    sections_by_id: dict[str, SectionUnits] = {}
    current_unit_id: str | None = None
    current_lesson_id: str | None = None
    progress_by_lesson = _get_progress_by_lesson(db, enrollment.id)

    for section, unit in section_units:
        if section.id not in sections_by_id:
            sections_by_id[section.id] = SectionUnits(
                id=section.id, title=section.title, description=section.description, units=[]
            )
        summary = summaries_by_id[unit.id]
        sections_by_id[section.id].units.append(summary)
        if current_unit_id is None and not summary.is_locked and not summary.is_completed:
            current_unit_id = unit.id
            available_lessons = _get_lessons_with_items(db, [unit.id]).get(unit.id, [])
            lesson = available_lessons[0] if available_lessons else None
            if lesson is not None:
                current_lesson_id = next(
                    (
                        candidate.id
                        for candidate in available_lessons
                        if progress_by_lesson.get(candidate.id) != "completed"
                    ),
                    lesson.id,
                )

    return PathResponse(
        sections=list(sections_by_id.values()),
        current_unit_id=current_unit_id,
        current_lesson_id=current_lesson_id,
    )


def get_current_course(db: Session, enrollment: UserCourseEnrollment) -> CurrentCourseResponse:
    course = db.get(CourseVersion, enrollment.course_version_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active course version not found")
    path = get_path(db, enrollment)
    return CurrentCourseResponse(
        course_version_id=course.id,
        course_code=course.code,
        course_version=course.version,
        status=course.status,
        current_unit_id=path.current_unit_id,
        current_lesson_id=path.current_lesson_id,
    )


def get_unit_detail(db: Session, enrollment: UserCourseEnrollment, unit_id: str) -> UnitDetail:
    row = db.execute(
        select(Section, Unit)
        .join(Unit, Unit.section_id == Section.id)
        .where(Section.course_version_id == enrollment.course_version_id, Unit.id == unit_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    section, unit = row

    progress_by_lesson = _get_progress_by_lesson(db, enrollment.id)
    attempts_by_lesson = _get_exam_attempts_by_lesson(db, enrollment.id)
    lessons = _get_lessons_with_items(db, [unit.id]).get(unit.id, [])
    lesson_summaries = _build_lesson_summaries_for_unit(lessons, progress_by_lesson, attempts_by_lesson)

    theme_tags = list(
        db.scalars(
            select(ThemeTag.code)
            .join(UnitThemeLink, UnitThemeLink.theme_tag_id == ThemeTag.id)
            .where(UnitThemeLink.unit_id == unit.id)
            .order_by(ThemeTag.code.asc())
        )
    )
    pattern_tags = list(
        db.scalars(
            select(Pattern.code)
            .join(UnitPatternLink, UnitPatternLink.pattern_id == Pattern.id)
            .where(UnitPatternLink.unit_id == unit.id)
            .order_by(Pattern.intro_order.asc(), Pattern.code.asc())
        )
    )

    sentence_links = list(
        db.execute(
            select(LessonSentence.sentence_id, LessonSentence.order_index)
            .join(Lesson, Lesson.id == LessonSentence.lesson_id)
            .where(Lesson.unit_id == unit.id)
            .order_by(Lesson.order_index.asc(), LessonSentence.order_index.asc(), LessonSentence.sentence_id.asc())
        ).all()
    )
    sentence_ids = [row.sentence_id for row in sentence_links[:5]]
    sentence_map = {
        sentence.id: sentence for sentence in db.scalars(select(Sentence).where(Sentence.id.in_(sentence_ids)))
    }
    sentence_units_by_id: dict[str, list[SentenceUnit]] = defaultdict(list)
    for sentence_unit in db.scalars(
        select(SentenceUnit)
        .where(SentenceUnit.sentence_id.in_(sentence_ids), SentenceUnit.lang == "ja")
        .order_by(SentenceUnit.sentence_id.asc(), SentenceUnit.unit_index.asc())
    ):
        sentence_units_by_id[sentence_unit.sentence_id].append(sentence_unit)
    sentence_samples = [
        SentencePreview(
            id=sentence_id,
            ja_text=display_sentence_text_ja(
                sentence=sentence_map[sentence_id],
                units=sentence_units_by_id.get(sentence_id, []),
                use_kana=sentence_uses_kana_display(db, sentence_id=sentence_id),
            ),
            en_text=sentence_map[sentence_id].en_text,
        )
        for sentence_id in sentence_ids
        if sentence_id in sentence_map
    ]

    return UnitDetail(
        id=unit.id,
        section_id=section.id,
        section_title=section.title,
        unit_order_index=unit.order_index,
        title=unit.title,
        description=unit.description,
        pattern_tags=pattern_tags,
        theme_tags=theme_tags,
        article_md=None,
        lessons=lesson_summaries,
        sentence_samples=sentence_samples,
    )
