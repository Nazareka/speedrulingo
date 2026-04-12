from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from html import escape
from pathlib import Path
import shutil
from typing import Any, ClassVar, override
from urllib.parse import urlencode

from fastapi import FastAPI
from sqladmin import Admin, BaseView, ModelView, expose
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import InstrumentedAttribute, Session, sessionmaker
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from domain.auth.models import User, UserCourseEnrollment
from domain.content.models import (
    CourseVersion,
    Kanji,
    Lesson,
    Pattern,
    Section,
    Sentence,
    SentenceAudioAsset,
    Unit,
    Word,
    WordAudioAsset,
)
from domain.kana.models import KanaAudioAsset, KanaLesson, UserKanaProgress
from domain.learning.models import ExamAttempt, UserLessonProgress
from security import verify_password

ModelColumnAttr = str | InstrumentedAttribute[Any]


class SqlAdminAuthBackend(AuthenticationBackend):
    def __init__(self, *, secret_key: str, session_maker: sessionmaker[Session]) -> None:
        super().__init__(secret_key=secret_key)
        self._session_maker = session_maker

    @override
    async def login(self, request: Request) -> bool:
        form = await request.form()
        email = form.get("username")
        password = form.get("password")
        if not isinstance(email, str) or not isinstance(password, str):
            return False

        with self._session_maker() as session:
            user = _get_admin_user(session, email=email)
            if user is None or not verify_password(password, user.password_hash):
                return False
            request.session.update({"admin_user_id": user.id})
        return True

    @override
    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    @override
    async def authenticate(self, request: Request) -> bool:
        user_id = request.session.get("admin_user_id")
        if not isinstance(user_id, str):
            return False
        with self._session_maker() as session:
            user = session.get(User, user_id)
            return user is not None and user.is_admin


def _get_admin_user(session: Session, *, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email, User.is_admin.is_(True)).limit(1))


class UserAdmin(ModelView, model=User):
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"
    column_list: ClassVar[Sequence[ModelColumnAttr]] = (User.id, User.email, User.is_admin, User.has_pro_sub, User.created_at)
    column_searchable_list: ClassVar[Sequence[ModelColumnAttr]] = (User.email,)
    column_sortable_list: ClassVar[Sequence[ModelColumnAttr]] = (User.email, User.created_at)
    form_excluded_columns: ClassVar[Sequence[ModelColumnAttr]] = (User.password_hash,)


class CourseVersionAdmin(ModelView, model=CourseVersion):
    name = "Course Build"
    name_plural = "Course Builds"
    icon = "fa-solid fa-code-branch"
    column_list: ClassVar[Sequence[ModelColumnAttr]] = (
        CourseVersion.id,
        CourseVersion.code,
        CourseVersion.version,
        CourseVersion.build_version,
        CourseVersion.status,
        CourseVersion.config_version,
        CourseVersion.created_at,
    )
    column_searchable_list: ClassVar[Sequence[ModelColumnAttr]] = (CourseVersion.code, CourseVersion.config_version)
    column_sortable_list: ClassVar[Sequence[ModelColumnAttr]] = (
        CourseVersion.created_at,
        CourseVersion.version,
        CourseVersion.build_version,
    )


class SectionAdmin(ModelView, model=Section):
    name = "Section"
    name_plural = "Sections"
    icon = "fa-solid fa-book"
    column_list: ClassVar[Sequence[ModelColumnAttr]] = (Section.id, Section.course_version_id, Section.code, Section.order_index, Section.title)
    column_searchable_list: ClassVar[Sequence[ModelColumnAttr]] = (Section.code, Section.title)
    column_sortable_list: ClassVar[Sequence[ModelColumnAttr]] = (Section.order_index, Section.title)


class UnitAdmin(ModelView, model=Unit):
    name = "Unit"
    name_plural = "Units"
    icon = "fa-solid fa-layer-group"
    column_list: ClassVar[Sequence[ModelColumnAttr]] = (Unit.id, Unit.section_id, Unit.order_index, Unit.title, Unit.description)
    column_searchable_list: ClassVar[Sequence[ModelColumnAttr]] = (Unit.title, Unit.description)
    column_sortable_list: ClassVar[Sequence[ModelColumnAttr]] = (Unit.order_index, Unit.title)


class LessonAdmin(ModelView, model=Lesson):
    name = "Lesson"
    name_plural = "Lessons"
    icon = "fa-solid fa-list-check"
    column_list: ClassVar[Sequence[ModelColumnAttr]] = (
        Lesson.id,
        Lesson.unit_id,
        Lesson.order_index,
        Lesson.kind,
        Lesson.force_kana_display,
        Lesson.target_item_count,
    )
    column_sortable_list: ClassVar[Sequence[ModelColumnAttr]] = (Lesson.order_index, Lesson.kind, Lesson.target_item_count)


class PatternAdmin(ModelView, model=Pattern):
    name = "Pattern"
    name_plural = "Patterns"
    icon = "fa-solid fa-shapes"
    column_list: ClassVar[Sequence[ModelColumnAttr]] = (Pattern.id, Pattern.course_version_id, Pattern.code, Pattern.name, Pattern.intro_order)
    column_searchable_list: ClassVar[Sequence[ModelColumnAttr]] = (Pattern.code, Pattern.name)
    column_sortable_list: ClassVar[Sequence[ModelColumnAttr]] = (Pattern.intro_order, Pattern.code, Pattern.name)


class WordAdmin(ModelView, model=Word):
    name = "Word"
    name_plural = "Words"
    icon = "fa-solid fa-language"
    column_list: ClassVar[Sequence[ModelColumnAttr]] = (
        Word.id,
        Word.course_version_id,
        Word.intro_order,
        Word.canonical_writing_ja,
        Word.reading_kana,
        Word.gloss_primary_en,
        Word.pos,
        Word.source_kind,
    )
    column_searchable_list: ClassVar[Sequence[ModelColumnAttr]] = (Word.canonical_writing_ja, Word.reading_kana, Word.gloss_primary_en)
    column_sortable_list: ClassVar[Sequence[ModelColumnAttr]] = (Word.intro_order, Word.canonical_writing_ja, Word.reading_kana)


class SentenceAdmin(ModelView, model=Sentence):
    name = "Sentence"
    name_plural = "Sentences"
    icon = "fa-solid fa-comment"
    column_list: ClassVar[Sequence[ModelColumnAttr]] = (
        Sentence.id,
        Sentence.course_version_id,
        Sentence.ja_text,
        Sentence.en_text,
        Sentence.target_word_id,
        Sentence.target_pattern_id,
    )
    column_searchable_list: ClassVar[Sequence[ModelColumnAttr]] = (Sentence.ja_text, Sentence.en_text)


class KanjiAdmin(ModelView, model=Kanji):
    name = "Kanji"
    name_plural = "Kanji"
    icon = "fa-solid fa-pen"
    column_list: ClassVar[Sequence[ModelColumnAttr]] = (Kanji.char, Kanji.primary_meaning)
    column_searchable_list: ClassVar[Sequence[ModelColumnAttr]] = (Kanji.char, Kanji.primary_meaning)


def _get_active_course(session: Session) -> CourseVersion | None:
    return session.scalar(
        select(CourseVersion)
        .where(CourseVersion.status == "active")
        .order_by(CourseVersion.created_at.desc(), CourseVersion.version.desc(), CourseVersion.build_version.desc())
        .limit(1)
    )


def _get_or_create_enrollment(session: Session, *, user_id: str, course_version_id: str) -> UserCourseEnrollment:
    enrollment = session.scalar(
        select(UserCourseEnrollment).where(
            UserCourseEnrollment.user_id == user_id,
            UserCourseEnrollment.course_version_id == course_version_id,
        )
    )
    if enrollment is not None:
        return enrollment
    enrollment = UserCourseEnrollment(user_id=user_id, course_version_id=course_version_id)
    session.add(enrollment)
    session.flush()
    return enrollment


def _load_course_units(session: Session, *, course_version_id: str) -> list[tuple[Section, Unit]]:
    rows = session.execute(
        select(Section, Unit)
        .join(Unit, Unit.section_id == Section.id)
        .where(Section.course_version_id == course_version_id)
        .order_by(Section.order_index.asc(), Unit.order_index.asc())
    )
    return list(rows.tuples())


def _load_unit_lessons(session: Session, *, unit_id: str) -> list[Lesson]:
    return list(session.scalars(select(Lesson).where(Lesson.unit_id == unit_id).order_by(Lesson.order_index.asc())))


def _set_unit_completion_state(
    session: Session,
    *,
    user_id: str,
    course_version_id: str,
    unit_id: str,
    is_completed: bool,
) -> None:
    lessons = _load_unit_lessons(session, unit_id=unit_id)
    lesson_ids = [lesson.id for lesson in lessons]
    if not lesson_ids:
        return

    enrollment = session.scalar(
        select(UserCourseEnrollment).where(
            UserCourseEnrollment.user_id == user_id,
            UserCourseEnrollment.course_version_id == course_version_id,
        )
    )

    if is_completed:
        active_enrollment = enrollment or _get_or_create_enrollment(
            session, user_id=user_id, course_version_id=course_version_id
        )
        existing_progress_by_lesson_id = {
            progress.lesson_id: progress
            for progress in session.scalars(
                select(UserLessonProgress).where(
                    UserLessonProgress.enrollment_id == active_enrollment.id,
                    UserLessonProgress.lesson_id.in_(lesson_ids),
                )
            )
        }
        now = datetime.now(UTC)
        for lesson_id in lesson_ids:
            progress = existing_progress_by_lesson_id.get(lesson_id)
            if progress is None:
                session.add(
                    UserLessonProgress(
                        enrollment_id=active_enrollment.id,
                        lesson_id=lesson_id,
                        state="completed",
                        updated_at=now,
                    )
                )
            else:
                progress.state = "completed"
                progress.updated_at = now
        return

    if enrollment is None:
        return
    session.execute(
        delete(UserLessonProgress).where(
            UserLessonProgress.enrollment_id == enrollment.id,
            UserLessonProgress.lesson_id.in_(lesson_ids),
        )
    )
    session.execute(
        delete(ExamAttempt).where(
            ExamAttempt.enrollment_id == enrollment.id,
            ExamAttempt.lesson_id.in_(lesson_ids),
        )
    )


def _set_lesson_completion_state(
    session: Session,
    *,
    user_id: str,
    course_version_id: str,
    lesson_id: str,
    is_completed: bool,
) -> None:
    enrollment = session.scalar(
        select(UserCourseEnrollment).where(
            UserCourseEnrollment.user_id == user_id,
            UserCourseEnrollment.course_version_id == course_version_id,
        )
    )

    if is_completed:
        active_enrollment = enrollment or _get_or_create_enrollment(
            session, user_id=user_id, course_version_id=course_version_id
        )
        progress = session.get(
            UserLessonProgress,
            {"enrollment_id": active_enrollment.id, "lesson_id": lesson_id},
        )
        if progress is None:
            session.add(
                UserLessonProgress(
                    enrollment_id=active_enrollment.id,
                    lesson_id=lesson_id,
                    state="completed",
                    updated_at=datetime.now(UTC),
                )
            )
        else:
            progress.state = "completed"
            progress.updated_at = datetime.now(UTC)
        return

    if enrollment is None:
        return
    session.execute(
        delete(UserLessonProgress).where(
            UserLessonProgress.enrollment_id == enrollment.id,
            UserLessonProgress.lesson_id == lesson_id,
        )
    )
    session.execute(
        delete(ExamAttempt).where(
            ExamAttempt.enrollment_id == enrollment.id,
            ExamAttempt.lesson_id == lesson_id,
        )
    )


class UnitCompletionAdmin(BaseView):
    name = "Unit Completion"
    identity = "unit-completion"
    icon = "fa-solid fa-circle-check"
    session_maker: ClassVar[sessionmaker[Session]]

    @expose("/unit-completion", methods=["GET", "POST"], identity="unit-completion")
    async def unit_completion(self, request: Request) -> HTMLResponse | RedirectResponse:
        selected_user_id = request.query_params.get("user_id")
        message = request.query_params.get("message")

        with self.session_maker() as session:
            active_course = _get_active_course(session)
            if request.method == "POST":
                form = await request.form()
                raw_user_id = form.get("user_id")
                raw_unit_id = form.get("unit_id")
                raw_lesson_id = form.get("lesson_id")
                raw_operation = form.get("operation")
                selected_user_id = raw_user_id if isinstance(raw_user_id, str) else selected_user_id
                unit_id = raw_unit_id if isinstance(raw_unit_id, str) else None
                lesson_id = raw_lesson_id if isinstance(raw_lesson_id, str) else None
                operation = raw_operation if isinstance(raw_operation, str) else None
                if (
                    active_course is not None
                    and selected_user_id is not None
                    and operation in {
                        "set_completed",
                        "unset_completed",
                        "set_lesson_completed",
                        "unset_lesson_completed",
                    }
                ):
                    if operation in {"set_completed", "unset_completed"} and unit_id is not None:
                        _set_unit_completion_state(
                            session,
                            user_id=selected_user_id,
                            course_version_id=active_course.id,
                            unit_id=unit_id,
                            is_completed=operation == "set_completed",
                        )
                        status_message = "Unit completion updated."
                    elif operation in {"set_lesson_completed", "unset_lesson_completed"} and lesson_id is not None:
                        _set_lesson_completion_state(
                            session,
                            user_id=selected_user_id,
                            course_version_id=active_course.id,
                            lesson_id=lesson_id,
                            is_completed=operation == "set_lesson_completed",
                        )
                        status_message = "Lesson completion updated."
                    else:
                        status_message = ""
                    session.commit()
                    redirect_query = urlencode({"user_id": selected_user_id, "message": status_message})
                    return RedirectResponse(url=f"{request.url.path}?{redirect_query}", status_code=303)

            users = list(session.scalars(select(User).order_by(User.email.asc())))
            selected_user = next((user for user in users if user.id == selected_user_id), users[0] if users else None)
            section_units = _load_course_units(session, course_version_id=active_course.id) if active_course is not None else []
            enrollment = (
                session.scalar(
                    select(UserCourseEnrollment).where(
                        UserCourseEnrollment.user_id == selected_user.id,
                        UserCourseEnrollment.course_version_id == active_course.id,
                    )
                )
                if active_course is not None and selected_user is not None
                else None
            )
            progress_by_lesson_id = (
                {
                    progress.lesson_id: progress.state
                    for progress in session.scalars(
                        select(UserLessonProgress).where(UserLessonProgress.enrollment_id == enrollment.id)
                    )
                }
                if enrollment is not None
                else {}
            )

            page_title = "Unit Completion"
            message_html = (
                f"<p style='color:#2b8a3e;font-weight:600'>{escape(message)}</p>"
                if isinstance(message, str) and message
                else ""
            )
            active_course_html = (
                f"<p><strong>Active course:</strong> {escape(active_course.code)} "
                f"(version {active_course.version}, build {active_course.build_version})</p>"
                if active_course is not None
                else "<p><strong>Active course:</strong> none</p>"
            )
            user_options_html = "".join(
                (
                    f"<option value='{escape(user.id)}'"
                    f"{' selected' if selected_user is not None and user.id == selected_user.id else ''}>"
                    f"{escape(user.email)}</option>"
                )
                for user in users
            )

            unit_rows_html = ""
            if active_course is not None and selected_user is not None:
                for section, unit in section_units:
                    lessons = [
                        {
                            "id": lesson.id,
                            "kind": lesson.kind,
                            "state": progress_by_lesson_id.get(lesson.id, "not_started"),
                        }
                        for lesson in _load_unit_lessons(session, unit_id=unit.id)
                    ]
                    completed_lessons = sum(1 for lesson in lessons if lesson["state"] == "completed")
                    lesson_count = len(lessons)
                    is_completed = any(
                        lesson["kind"] == "exam" and lesson["state"] == "completed" for lesson in lessons
                    )
                    set_disabled = " disabled" if is_completed else ""
                    unset_disabled = " disabled" if lesson_count == 0 or completed_lessons == 0 else ""
                    section_label = escape(f"{section.order_index}. {section.title}")
                    unit_label = escape(f"{unit.order_index}. {unit.title}")
                    unit_rows_html += (
                        "<tr>"
                        f"<td>{section_label}</td>"
                        f"<td>{unit_label}</td>"
                        f"<td>{completed_lessons} / {lesson_count}</td>"
                        f"<td>{'completed' if is_completed else 'not completed'}</td>"
                        "<td>"
                        f"<form method='post' style='display:inline-block;margin-right:8px'>"
                        f"<input type='hidden' name='user_id' value='{escape(selected_user.id)}'>"
                        f"<input type='hidden' name='unit_id' value='{escape(unit.id)}'>"
                        "<input type='hidden' name='operation' value='set_completed'>"
                        f"<button type='submit'{set_disabled}>Set completed</button>"
                        "</form>"
                        f"<form method='post' style='display:inline-block'>"
                        f"<input type='hidden' name='user_id' value='{escape(selected_user.id)}'>"
                        f"<input type='hidden' name='unit_id' value='{escape(unit.id)}'>"
                        "<input type='hidden' name='operation' value='unset_completed'>"
                        f"<button type='submit'{unset_disabled}>Unset</button>"
                        "</form>"
                        "</td>"
                        "<td>"
                        + "".join(
                            (
                                f"<div style='margin-bottom:8px'><strong>{escape(f'{index}. {lesson['kind']}')}</strong> "
                                f"({escape(lesson['state'])}) "
                                f"<form method='post' style='display:inline-block;margin-left:8px;margin-right:6px'>"
                                f"<input type='hidden' name='user_id' value='{escape(selected_user.id)}'>"
                                f"<input type='hidden' name='lesson_id' value='{escape(lesson['id'])}'>"
                                "<input type='hidden' name='operation' value='set_lesson_completed'>"
                                f"<button type='submit'{' disabled' if lesson['state'] == 'completed' else ''}>Set</button>"
                                "</form>"
                                f"<form method='post' style='display:inline-block'>"
                                f"<input type='hidden' name='user_id' value='{escape(selected_user.id)}'>"
                                f"<input type='hidden' name='lesson_id' value='{escape(lesson['id'])}'>"
                                "<input type='hidden' name='operation' value='unset_lesson_completed'>"
                                f"<button type='submit'{' disabled' if lesson['state'] == 'not_started' else ''}>Unset</button>"
                                "</form></div>"
                            )
                            for index, lesson in enumerate(lessons, start=1)
                        )
                        + "</td>"
                        "</tr>"
                    )
            if not unit_rows_html:
                unit_rows_html = "<tr><td colspan='6'>No units available.</td></tr>"

            html = (
                "<!doctype html><html><head><meta charset='utf-8'>"
                f"<title>{page_title}</title>"
                "<style>"
                "body{font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:24px;line-height:1.4;}"
                "table{border-collapse:collapse;width:100%;margin-top:16px;}"
                "th,td{border:1px solid #d0d7de;padding:8px 10px;text-align:left;vertical-align:top;}"
                "th{background:#f6f8fa;}"
                "select,button{font:inherit;padding:6px 10px;}"
                "</style></head><body>"
                f"<h1>{page_title}</h1>"
                f"{_admin_home_link_html()}"
                f"{active_course_html}"
                f"{message_html}"
                "<form method='get'>"
                "<label for='user_id'><strong>User:</strong></label> "
                f"<select id='user_id' name='user_id'>{user_options_html}</select> "
                "<button type='submit'>Load</button>"
                "</form>"
                "<table>"
                "<thead><tr><th>Section</th><th>Unit</th><th>Completed lessons</th><th>Unit state</th><th>Unit actions</th><th>Lesson actions</th></tr></thead>"
                f"<tbody>{unit_rows_html}</tbody>"
                "</table>"
                "</body></html>"
            )
            return HTMLResponse(html)


def _clear_user_kana_progress(
    session: Session,
    *,
    user_id: str,
    course_version_id: str,
) -> str:
    """Remove all kana practice state for the user's enrollment on the given course build."""
    enrollment = session.scalar(
        select(UserCourseEnrollment).where(
            UserCourseEnrollment.user_id == user_id,
            UserCourseEnrollment.course_version_id == course_version_id,
        )
    )
    if enrollment is None:
        return "No enrollment for this user on the active course — nothing to clear."

    eid = enrollment.id
    progress_n = (
        session.scalar(select(func.count()).select_from(UserKanaProgress).where(UserKanaProgress.enrollment_id == eid))
        or 0
    )
    lessons_n = session.scalar(select(func.count()).select_from(KanaLesson).where(KanaLesson.enrollment_id == eid)) or 0
    session.execute(delete(KanaLesson).where(KanaLesson.enrollment_id == eid))
    session.execute(delete(UserKanaProgress).where(UserKanaProgress.enrollment_id == eid))
    return f"Cleared {progress_n} kana progress row(s) and {lessons_n} kana lesson(s)."


class KanaProgressAdmin(BaseView):
    name = "Kana Progress"
    identity = "kana-progress"
    icon = "fa-solid fa-font"
    session_maker: ClassVar[sessionmaker[Session]]

    @expose("/kana-progress", methods=["GET", "POST"], identity="kana-progress")
    async def kana_progress(self, request: Request) -> HTMLResponse | RedirectResponse:
        selected_user_id = request.query_params.get("user_id")
        message = request.query_params.get("message")

        with self.session_maker() as session:
            active_course = _get_active_course(session)
            if request.method == "POST":
                form = await request.form()
                raw_user_id = form.get("user_id")
                raw_operation = form.get("operation")
                selected_user_id = raw_user_id if isinstance(raw_user_id, str) else selected_user_id
                operation = raw_operation if isinstance(raw_operation, str) else None
                if active_course is not None and selected_user_id is not None and operation == "clear_kana_progress":
                    status_message = _clear_user_kana_progress(
                        session,
                        user_id=selected_user_id,
                        course_version_id=active_course.id,
                    )
                    session.commit()
                    redirect_query = urlencode({"user_id": selected_user_id, "message": status_message})
                    return RedirectResponse(url=f"{request.url.path}?{redirect_query}", status_code=303)

            users = list(session.scalars(select(User).order_by(User.email.asc())))
            selected_user = next((user for user in users if user.id == selected_user_id), users[0] if users else None)
            enrollment = (
                session.scalar(
                    select(UserCourseEnrollment).where(
                        UserCourseEnrollment.user_id == selected_user.id,
                        UserCourseEnrollment.course_version_id == active_course.id,
                    )
                )
                if active_course is not None and selected_user is not None
                else None
            )
            progress_count = (
                session.scalar(
                    select(func.count())
                    .select_from(UserKanaProgress)
                    .where(UserKanaProgress.enrollment_id == enrollment.id)
                )
                if enrollment is not None
                else None
            )
            lesson_count = (
                session.scalar(
                    select(func.count()).select_from(KanaLesson).where(KanaLesson.enrollment_id == enrollment.id)
                )
                if enrollment is not None
                else None
            )

            page_title = "Kana Progress"
            message_html = (
                f"<p style='color:#2b8a3e;font-weight:600'>{escape(message)}</p>"
                if isinstance(message, str) and message
                else ""
            )
            active_course_html = (
                f"<p><strong>Active course:</strong> {escape(active_course.code)} "
                f"(version {active_course.version}, build {active_course.build_version})</p>"
                if active_course is not None
                else "<p><strong>Active course:</strong> none</p>"
            )
            user_options_html = "".join(
                (
                    f"<option value='{escape(user.id)}'"
                    f"{' selected' if selected_user is not None and user.id == selected_user.id else ''}>"
                    f"{escape(user.email)}</option>"
                )
                for user in users
            )
            stats_html = ""
            if active_course is not None and selected_user is not None:
                if enrollment is None:
                    stats_html = "<p><em>No enrollment on the active course yet — the learner has not started.</em></p>"
                else:
                    stats_html = (
                        f"<p><strong>Enrollment:</strong> {escape(enrollment.id)}</p>"
                        f"<p><strong>User kana progress rows:</strong> {progress_count or 0}</p>"
                        f"<p><strong>In-progress kana lessons:</strong> {lesson_count or 0}</p>"
                    )

            can_clear_kana = (
                active_course is not None
                and selected_user is not None
                and enrollment is not None
                and ((progress_count or 0) > 0 or (lesson_count or 0) > 0)
            )
            clear_disabled = "" if can_clear_kana else " disabled"

            html = (
                "<!doctype html><html><head><meta charset='utf-8'>"
                f"<title>{page_title}</title>"
                "<style>"
                "body{font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:24px;line-height:1.4;}"
                "select,button{font:inherit;padding:6px 10px;}"
                ".danger{background:#c92a2a;border:1px solid #a61e1e;color:#fff;border-radius:6px;}"
                ".card{border:1px solid #d0d7de;border-radius:10px;padding:16px;max-width:720px;margin-top:16px;}"
                "</style></head><body>"
                f"<h1>{page_title}</h1>"
                f"{_admin_home_link_html()}"
                f"{active_course_html}"
                f"{message_html}"
                "<p>Clear all <strong>kana character progress</strong> and <strong>in-flight kana lessons</strong> "
                "for the selected user on the <strong>active course</strong> (the kana practice page).</p>"
                "<form method='get'>"
                "<label for='user_id'><strong>User:</strong></label> "
                f"<select id='user_id' name='user_id'>{user_options_html}</select> "
                "<button type='submit'>Load</button>"
                "</form>"
                f"{stats_html}"
                "<div class='card'>"
                "<p><strong>Reset kana practice</strong></p>"
                "<p>This removes per-character exposure counts and any unfinished kana lesson sessions. "
                "It does not delete course content or audio assets.</p>"
                "<form method='post'>"
                f"<input type='hidden' name='user_id' value='{escape(selected_user.id) if selected_user else ''}'>"
                "<input type='hidden' name='operation' value='clear_kana_progress'>"
                f"<button class='danger' type='submit'{clear_disabled}>Clear kana progress</button>"
                "</form>"
                "</div>"
                "</body></html>"
            )
            return HTMLResponse(html)


def _wipe_all_assets(
    session: Session,
    *,
    model: type[SentenceAudioAsset] | type[WordAudioAsset] | type[KanaAudioAsset],
) -> int:
    storage_paths = list(session.scalars(select(model.storage_path)))
    deleted_count = len(storage_paths)

    for storage_path in storage_paths:
        path = Path(storage_path)
        try:
            path.unlink(missing_ok=True)
        except IsADirectoryError:
            shutil.rmtree(path, ignore_errors=True)

    session.execute(delete(model))
    session.flush()

    # Best-effort cleanup of now-empty provider/voice directories left behind by file deletes.
    visited_roots: set[Path] = set()
    for storage_path in storage_paths:
        current = Path(storage_path).parent
        while current != current.parent and current not in visited_roots:
            visited_roots.add(current)
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent

    return deleted_count


def _wipe_all_sentence_audio(session: Session) -> int:
    return _wipe_all_assets(session, model=SentenceAudioAsset)


def _wipe_all_word_audio(session: Session) -> int:
    return _wipe_all_assets(session, model=WordAudioAsset)


def _wipe_all_character_audio(session: Session) -> int:
    return _wipe_all_assets(session, model=KanaAudioAsset)


def _admin_home_link_html() -> str:
    return (
        "<p style='margin:0 0 16px 0'>"
        "<a href='/admin/' "
        "style='display:inline-block;padding:8px 12px;border:1px solid #d0d7de;border-radius:6px;"
        "text-decoration:none;color:#24292f;background:#f6f8fa'>Back to Admin</a>"
        "</p>"
    )


class SentenceAudioAdmin(BaseView):
    name = "Sentence Audio"
    identity = "sentence-audio"
    icon = "fa-solid fa-volume-high"
    session_maker: ClassVar[sessionmaker[Session]]

    @expose("/sentence-audio", methods=["GET", "POST"], identity="sentence-audio")
    async def sentence_audio(self, request: Request) -> HTMLResponse | RedirectResponse:
        message = request.query_params.get("message")

        with self.session_maker() as session:
            if request.method == "POST":
                form = await request.form()
                operation = form.get("operation")
                if operation == "wipe_all_audio":
                    deleted_count = _wipe_all_sentence_audio(session)
                    session.commit()
                    redirect_query = urlencode(
                        {"message": f"Deleted {deleted_count} sentence audio assets from the database and disk."}
                    )
                    return RedirectResponse(url=f"{request.url.path}?{redirect_query}", status_code=303)

            asset_count = session.scalar(select(func.count()).select_from(SentenceAudioAsset)) or 0
            latest_asset = session.scalar(
                select(SentenceAudioAsset)
                .order_by(SentenceAudioAsset.created_at.desc(), SentenceAudioAsset.id.desc())
                .limit(1)
            )
            message_html = (
                f"<p style='color:#2b8a3e;font-weight:600'>{escape(message)}</p>"
                if isinstance(message, str) and message
                else ""
            )
            latest_asset_html = (
                f"<p><strong>Latest asset:</strong> {escape(latest_asset.id)} "
                f"({escape(latest_asset.status)})</p>"
                if latest_asset is not None
                else "<p><strong>Latest asset:</strong> none</p>"
            )
            html = (
                "<!doctype html><html><head><meta charset='utf-8'>"
                "<title>Sentence Audio</title>"
                "<style>"
                "body{font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:24px;line-height:1.4;}"
                "button{font:inherit;padding:8px 12px;}"
                ".danger{background:#c92a2a;border:1px solid #a61e1e;color:#fff;border-radius:6px;}"
                ".card{border:1px solid #d0d7de;border-radius:10px;padding:16px;max-width:720px;}"
                "</style></head><body>"
                "<h1>Sentence Audio</h1>"
                f"{_admin_home_link_html()}"
                f"{message_html}"
                f"<p><strong>Stored assets:</strong> {asset_count}</p>"
                f"{latest_asset_html}"
                "<div class='card'>"
                "<p><strong>Danger zone</strong></p>"
                "<p>Delete all generated sentence audio from both Postgres metadata and local disk so audio can be regenerated from scratch.</p>"
                "<form method='post'>"
                "<input type='hidden' name='operation' value='wipe_all_audio'>"
                "<button class='danger' type='submit'>Wipe All Sentence Audio</button>"
                "</form>"
                "</div>"
                "</body></html>"
            )
            return HTMLResponse(html)


class WordAudioAdmin(BaseView):
    name = "Word Audio"
    identity = "word-audio"
    icon = "fa-solid fa-wave-square"
    session_maker: ClassVar[sessionmaker[Session]]

    @expose("/word-audio", methods=["GET", "POST"], identity="word-audio")
    async def word_audio(self, request: Request) -> HTMLResponse | RedirectResponse:
        message = request.query_params.get("message")

        with self.session_maker() as session:
            if request.method == "POST":
                form = await request.form()
                operation = form.get("operation")
                if operation == "wipe_all_audio":
                    deleted_count = _wipe_all_word_audio(session)
                    session.commit()
                    redirect_query = urlencode(
                        {"message": f"Deleted {deleted_count} word audio assets from the database and disk."}
                    )
                    return RedirectResponse(url=f"{request.url.path}?{redirect_query}", status_code=303)

            asset_count = session.scalar(select(func.count()).select_from(WordAudioAsset)) or 0
            latest_asset = session.scalar(
                select(WordAudioAsset)
                .order_by(WordAudioAsset.created_at.desc(), WordAudioAsset.id.desc())
                .limit(1)
            )
            message_html = (
                f"<p style='color:#2b8a3e;font-weight:600'>{escape(message)}</p>"
                if isinstance(message, str) and message
                else ""
            )
            latest_asset_html = (
                f"<p><strong>Latest asset:</strong> {escape(latest_asset.id)} "
                f"({escape(latest_asset.status)})</p>"
                if latest_asset is not None
                else "<p><strong>Latest asset:</strong> none</p>"
            )
            html = (
                "<!doctype html><html><head><meta charset='utf-8'>"
                "<title>Word Audio</title>"
                "<style>"
                "body{font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:24px;line-height:1.4;}"
                "button{font:inherit;padding:8px 12px;}"
                ".danger{background:#c92a2a;border:1px solid #a61e1e;color:#fff;border-radius:6px;}"
                ".card{border:1px solid #d0d7de;border-radius:10px;padding:16px;max-width:720px;}"
                "</style></head><body>"
                "<h1>Word Audio</h1>"
                f"{_admin_home_link_html()}"
                f"{message_html}"
                f"<p><strong>Stored assets:</strong> {asset_count}</p>"
                f"{latest_asset_html}"
                "<div class='card'>"
                "<p><strong>Danger zone</strong></p>"
                "<p>Delete all generated word audio from both Postgres metadata and local disk so audio can be regenerated from scratch.</p>"
                "<form method='post'>"
                "<input type='hidden' name='operation' value='wipe_all_audio'>"
                "<button class='danger' type='submit'>Wipe All Word Audio</button>"
                "</form>"
                "</div>"
                "</body></html>"
            )
            return HTMLResponse(html)


class CharacterAudioAdmin(BaseView):
    name = "Character Audio"
    identity = "character-audio"
    icon = "fa-solid fa-font"
    session_maker: ClassVar[sessionmaker[Session]]

    @expose("/character-audio", methods=["GET", "POST"], identity="character-audio")
    async def character_audio(self, request: Request) -> HTMLResponse | RedirectResponse:
        message = request.query_params.get("message")

        with self.session_maker() as session:
            if request.method == "POST":
                form = await request.form()
                operation = form.get("operation")
                if operation == "wipe_all_audio":
                    deleted_count = _wipe_all_character_audio(session)
                    session.commit()
                    redirect_query = urlencode(
                        {"message": f"Deleted {deleted_count} character audio assets from the database and disk."}
                    )
                    return RedirectResponse(url=f"{request.url.path}?{redirect_query}", status_code=303)

            asset_count = session.scalar(select(func.count()).select_from(KanaAudioAsset)) or 0
            latest_asset = session.scalar(
                select(KanaAudioAsset)
                .order_by(KanaAudioAsset.created_at.desc(), KanaAudioAsset.id.desc())
                .limit(1)
            )
            message_html = (
                f"<p style='color:#2b8a3e;font-weight:600'>{escape(message)}</p>"
                if isinstance(message, str) and message
                else ""
            )
            latest_asset_html = (
                f"<p><strong>Latest asset:</strong> {escape(latest_asset.id)} "
                f"({escape(latest_asset.status)})</p>"
                if latest_asset is not None
                else "<p><strong>Latest asset:</strong> none</p>"
            )
            html = (
                "<!doctype html><html><head><meta charset='utf-8'>"
                "<title>Character Audio</title>"
                "<style>"
                "body{font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:24px;line-height:1.4;}"
                "button{font:inherit;padding:8px 12px;}"
                ".danger{background:#c92a2a;border:1px solid #a61e1e;color:#fff;border-radius:6px;}"
                ".card{border:1px solid #d0d7de;border-radius:10px;padding:16px;max-width:720px;}"
                "</style></head><body>"
                "<h1>Character Audio</h1>"
                f"{_admin_home_link_html()}"
                f"{message_html}"
                f"<p><strong>Stored assets:</strong> {asset_count}</p>"
                f"{latest_asset_html}"
                "<div class='card'>"
                "<p><strong>Danger zone</strong></p>"
                "<p>Delete all generated character audio from both Postgres metadata and local disk so kana audio can be regenerated from scratch.</p>"
                "<form method='post'>"
                "<input type='hidden' name='operation' value='wipe_all_audio'>"
                "<button class='danger' type='submit'>Wipe All Character Audio</button>"
                "</form>"
                "</div>"
                "</body></html>"
            )
            return HTMLResponse(html)


def install_admin(
    app: FastAPI,
    *,
    secret_key: str,
    engine: Engine,
    session_maker: sessionmaker[Session] | None = None,
) -> Admin:
    active_session_maker = session_maker or sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    UnitCompletionAdmin.session_maker = active_session_maker
    KanaProgressAdmin.session_maker = active_session_maker
    SentenceAudioAdmin.session_maker = active_session_maker
    WordAudioAdmin.session_maker = active_session_maker
    CharacterAudioAdmin.session_maker = active_session_maker
    admin = Admin(
        app=app,
        engine=engine,
        title="Speedrulingo Admin",
        session_maker=active_session_maker,
        authentication_backend=SqlAdminAuthBackend(secret_key=secret_key, session_maker=active_session_maker),
    )
    admin.add_view(UserAdmin)
    admin.add_view(CourseVersionAdmin)
    admin.add_view(SectionAdmin)
    admin.add_view(UnitAdmin)
    admin.add_view(LessonAdmin)
    admin.add_view(PatternAdmin)
    admin.add_view(WordAdmin)
    admin.add_view(SentenceAdmin)
    admin.add_view(KanjiAdmin)
    admin.add_view(UnitCompletionAdmin)
    admin.add_view(KanaProgressAdmin)
    admin.add_view(SentenceAudioAdmin)
    admin.add_view(WordAudioAdmin)
    admin.add_view(CharacterAudioAdmin)
    return admin
