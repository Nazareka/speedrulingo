#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"

ADMIN_EMAIL="${1:-admin@speedrulingo.local}"
ADMIN_PASSWORD="${2:-password123}"
USER_EMAIL="${3:-user@speedrulingo.local}"
USER_PASSWORD="${4:-password123}"

cd "${BACKEND_DIR}"
PYTHONPATH=src uv run python - "${ADMIN_EMAIL}" "${ADMIN_PASSWORD}" "${USER_EMAIL}" "${USER_PASSWORD}" <<'PY'
from __future__ import annotations

import sys

from sqlalchemy import delete
from sqlalchemy import select

from db.engine import SessionLocal
from domain.auth.models import User, UserCourseEnrollment
from domain.content.models import CourseVersion, Lesson, Section, Unit
from domain.learning.models import UserLessonProgress
from security import hash_password


def recreate_user(
    *,
    db,
    email: str,
    password: str,
    is_admin: bool,
    has_pro_sub: bool,
) -> tuple[User, str]:
    existing_user = db.scalar(select(User).where(User.email == email))
    action = "recreated" if existing_user is not None else "created"
    if existing_user is not None:
        db.delete(existing_user)
        db.flush()

    user = User(
        email=email,
        password_hash=hash_password(password),
        is_admin=is_admin,
        has_pro_sub=has_pro_sub,
    )
    db.add(user)
    db.flush()
    return user, action


def ensure_enrollment(*, db, user_id: str, course_version_id: str) -> UserCourseEnrollment:
    enrollment = db.scalar(
        select(UserCourseEnrollment).where(
            UserCourseEnrollment.user_id == user_id,
            UserCourseEnrollment.course_version_id == course_version_id,
        )
    )
    if enrollment is None:
        enrollment = UserCourseEnrollment(user_id=user_id, course_version_id=course_version_id)
        db.add(enrollment)
        db.flush()
    return enrollment


def main() -> None:  # noqa: PLR0915  # small one-off bootstrap script with explicit setup steps
    email = sys.argv[1]
    password = sys.argv[2]
    user_email = sys.argv[3]
    user_password = sys.argv[4]

    if email == user_email:
        raise ValueError("Admin and learner emails must be different")

    with SessionLocal() as db:
        admin_user, admin_action = recreate_user(
            db=db,
            email=email,
            password=password,
            is_admin=True,
            has_pro_sub=True,
        )
        learner_user, learner_action = recreate_user(
            db=db,
            email=user_email,
            password=user_password,
            is_admin=False,
            has_pro_sub=False,
        )

        active_course = db.scalar(
            select(CourseVersion)
            .where(CourseVersion.status == "active")
            .order_by(CourseVersion.created_at.desc(), CourseVersion.version.desc(), CourseVersion.build_version.desc())
        )

        if active_course is not None:
            admin_enrollment = ensure_enrollment(db=db, user_id=admin_user.id, course_version_id=active_course.id)
            learner_enrollment = ensure_enrollment(db=db, user_id=learner_user.id, course_version_id=active_course.id)

            lesson_ids = db.scalars(
                select(Lesson.id)
                .join(Unit, Unit.id == Lesson.unit_id)
                .join(Section, Section.id == Unit.section_id)
                .where(Section.course_version_id == active_course.id)
            ).all()

            # Reset progress to make the script idempotent.
            db.execute(delete(UserLessonProgress).where(UserLessonProgress.enrollment_id == admin_enrollment.id))
            db.execute(delete(UserLessonProgress).where(UserLessonProgress.enrollment_id == learner_enrollment.id))

            if lesson_ids:
                db.add_all(
                    UserLessonProgress(
                        enrollment_id=admin_enrollment.id,
                        lesson_id=lesson_id,
                        state="completed",
                    )
                    for lesson_id in lesson_ids
                )

        db.commit()
        sys.stdout.write(f"{admin_action} admin user {email}\n")
        sys.stdout.write(f"{learner_action} learner user {user_email}\n")
        if active_course is None:
            sys.stdout.write("No active course found; created users without enrollments or progress.\n")
        else:
            sys.stdout.write(f"Seeded admin progress for active course {active_course.id}\n")
            sys.stdout.write("Learner progress reset to empty.\n")


if __name__ == "__main__":
    main()
PY
