from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.auth.models import User, UserCourseEnrollment
from domain.content.models import CourseVersion
from security import create_access_token, hash_password, verify_password


def _get_active_course(db: Session) -> CourseVersion | None:
    return db.scalar(
        select(CourseVersion)
        .where(CourseVersion.status == "active")
        .order_by(CourseVersion.created_at.desc(), CourseVersion.version.desc(), CourseVersion.build_version.desc())
    )


def _ensure_enrollment(db: Session, user: User) -> UserCourseEnrollment | None:
    active_course = _get_active_course(db)
    if active_course is None:
        return None

    enrollment = db.scalar(
        select(UserCourseEnrollment).where(
            UserCourseEnrollment.user_id == user.id,
            UserCourseEnrollment.course_version_id == active_course.id,
        )
    )
    if enrollment is not None:
        return enrollment

    enrollment = UserCourseEnrollment(user_id=user.id, course_version_id=active_course.id)
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


def register_user(db: Session, *, email: str, password: str) -> str:
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    _ensure_enrollment(db, user)
    return create_access_token(user.id)


def login_user(db: Session, *, email: str, password: str) -> str:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    _ensure_enrollment(db, user)
    return create_access_token(user.id)


def get_me_context(db: Session, user: User) -> tuple[str | None, str | None]:
    enrollment = _ensure_enrollment(db, user)
    if enrollment is None:
        return None, None
    return enrollment.id, enrollment.course_version_id
