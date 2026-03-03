from __future__ import annotations

from fastapi import APIRouter

from api.auth.schemas import LoginRequest, MeResponse, RegisterRequest, TokenResponse
from dependencies import CurrentUser, DBSession
from domain.auth.service import get_me_context, login_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: DBSession) -> TokenResponse:
    return TokenResponse(access_token=register_user(db, email=payload.email, password=payload.password))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DBSession) -> TokenResponse:
    return TokenResponse(access_token=login_user(db, email=payload.email, password=payload.password))


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser, db: DBSession) -> MeResponse:
    enrollment_id, course_version_id = get_me_context(db, user)
    return MeResponse(
        id=user.id,
        email=user.email,
        has_pro_sub=user.has_pro_sub,
        is_admin=user.is_admin,
        enrollment_id=enrollment_id,
        course_version_id=course_version_id,
    )
