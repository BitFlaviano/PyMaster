"""Dependências de rotas (sessão + contexto de template)."""
from __future__ import annotations

from fastapi import Cookie, Depends, Request
from sqlmodel import Session, select

from app.db import get_session
from app.models import User
from app.security import read_session_token

COOKIE_NAME = "pymaster_session"


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    user_id = read_session_token(token)
    if user_id is None:
        return None
    return session.get(User, user_id)


def require_user(
    user: User | None = Depends(get_current_user),
):
    if user is None:
        return None
    return user


def template_context(
    request: Request,
    session: Session,
    user: User | None,
) -> dict:
    from app.engine.content import load_content
    from app.engine.xp import level_from_xp, title_for_level, xp_progress
    from app.engine import review

    registry = load_content()
    due_count = len(review.due_reviews(session, user.id)) if user else 0
    level, _, progress = xp_progress(user.xp) if user else (1, 0, 0.0)
    certificate_issued = False
    if user:
        from app.models import Certificate
        certificate_issued = bool(session.exec(
            select(Certificate.cert_no).where(Certificate.user_id == user.id).limit(1)
        ).first())
    return {
        "user": user,
        "request": request,
        "registry": registry,
        "xp_level": level if user else 1,
        "xp_title": title_for_level(level) if user else "Novato",
        "xp_progress": progress if user else 0.0,
        "due_reviews": due_count if user else 0,
        "certificate_issued": certificate_issued,
        "page_settings": {
            "theme": (user.theme if user else "dark"),
            "font_scale": (user.font_scale if user else 100),
            "reduce_motion": (user.reduce_motion if user else False),
        },
    }


def current_user_id(user: User) -> int:
    return user.id  # type: ignore[return-value]