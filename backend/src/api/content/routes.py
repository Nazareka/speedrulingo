from __future__ import annotations

from fastapi import APIRouter

from api.content.schemas import CurrentCourseResponse, PathResponse, UnitDetail, UnitSummary
from dependencies import CurrentEnrollment, DBSession
from domain.content.service import get_current_course, get_path, get_unit_detail, list_units

router = APIRouter(tags=["content"])


@router.get("/path", response_model=PathResponse)
def path(enrollment: CurrentEnrollment, db: DBSession) -> PathResponse:
    return get_path(db, enrollment)


@router.get("/course/current", response_model=CurrentCourseResponse)
def current_course(enrollment: CurrentEnrollment, db: DBSession) -> CurrentCourseResponse:
    return get_current_course(db, enrollment)


@router.get("/units", response_model=list[UnitSummary])
def units(enrollment: CurrentEnrollment, db: DBSession) -> list[UnitSummary]:
    return list_units(db, enrollment)


@router.get("/units/{unit_id}", response_model=UnitDetail)
def unit_detail(unit_id: str, enrollment: CurrentEnrollment, db: DBSession) -> UnitDetail:
    return get_unit_detail(db, enrollment, unit_id)
