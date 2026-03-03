from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.session import get_db
from domain.auth.models import User, UserCourseEnrollment
from domain.content.models import CourseVersion
from security import decode_access_token

DBSession = Annotated[Session, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)


def get_current_user(
    db: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        user_id = decode_access_token(credentials.credentials)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user


def get_active_enrollment(db: DBSession, user: Annotated[User, Depends(get_current_user)]) -> UserCourseEnrollment:
    active_course = db.scalar(
        select(CourseVersion)
        .where(CourseVersion.status == "active")
        .order_by(CourseVersion.created_at.desc(), CourseVersion.version.desc())
    )
    if active_course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active course version")

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


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentEnrollment = Annotated[UserCourseEnrollment, Depends(get_active_enrollment)]
AdminUser = Annotated[User, Depends(require_admin)]
