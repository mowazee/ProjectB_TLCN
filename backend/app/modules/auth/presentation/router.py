"""API auth (SDD mục 7.1): POST /api/auth/login, GET /api/auth/me, POST /api/auth/logout."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from app.modules.auth.application import login as login_uc
from app.modules.auth.presentation.deps import AuthState, Ctx, DbSession, auth_state, check_origin
from app.shared.config import settings
from app.shared.context import Principal

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=100, description="Username hoặc email")
    password: str = Field(min_length=1, max_length=128)


class UserBrief(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str
    department_id: int | None


class SessionOut(BaseModel):
    user: UserBrief
    roles: list[str]
    csrf_token: str
    features: list[str]


def _out(principal: Principal, csrf: str) -> SessionOut:
    return SessionOut(
        user=UserBrief(
            id=principal.id,
            username=principal.username,
            full_name=principal.full_name,
            department_id=principal.department_id,
        ),
        roles=sorted(principal.roles),
        csrf_token=csrf,
        features=sorted(settings.features_enabled),
    )


def _set_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        settings.SESSION_COOKIE_NAME,
        session_id,
        max_age=settings.SESSION_TTL_SECONDS,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api",
    )


@router.post("/login", response_model=SessionOut)
def login(data: LoginIn, request: Request, response: Response, db: DbSession, ctx: Ctx) -> SessionOut:
    check_origin(request)
    result = login_uc.login(db, data.username, data.password, ctx, request.cookies.get(settings.SESSION_COOKIE_NAME))
    _set_cookie(response, result.session.session_id)
    return _out(result.principal, result.session.csrf_token)


@router.get("/me", response_model=SessionOut)
def me(state: Annotated[AuthState, Depends(auth_state)]) -> SessionOut:
    return _out(state.principal, state.session.csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(state: Annotated[AuthState, Depends(auth_state)], db: DbSession, ctx: Ctx) -> Response:
    login_uc.logout(db, state.principal, state.session.session_id, ctx)
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    resp.delete_cookie(settings.SESSION_COOKIE_NAME, path="/api")
    return resp
