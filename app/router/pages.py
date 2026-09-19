"""Rotas de páginas (full-page render com Jinja2)."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.engine.content import load_content
from app.engine.diagnostic import (
    DIAGNOSTIC_QUESTIONS,
    bootstrap_user,
    compute_diagnosed_level,
)
from app.engine import progression, review
from app.engine.xp import level_from_xp, title_for_level, xp_progress
from app.models import Attempt, CodeSnippet, User, UserBadge, UserConcept
from app.security import hash_password, make_session_token, verify_password
from app.router.deps import COOKIE_NAME, get_current_user, template_context

router = APIRouter()

EOF_REDIRECT = RedirectResponse("/", status_code=303)
DASHBOARD_REDIRECT = RedirectResponse("/dashboard", status_code=303)


def _ctx(request: Request, user: User | None, session: Session) -> dict:
    return template_context(request, session, user)


# ── Landing / seletor de perfis ──────────────────────────────
@router.get("/", response_class=HTMLResponse)
async def landing(request: Request, user: User | None = Depends(get_current_user), session: Session = Depends(get_session)):
    if user:
        return DASHBOARD_REDIRECT
    profiles = list(session.exec(select(User).order_by(User.last_active_at.desc())).all())
    if not profiles:
        return RedirectResponse("/onboarding", status_code=303)
    ctx = _ctx(request, None, session)
    ctx.update({
        "profiles": profiles,
        "pin_profile": request.query_params.get("pin"),
        "picker_error": request.query_params.get("error"),
    })
    return request.app.state.templates.TemplateResponse(request, "profiles.html", ctx)


@router.get("/profiles", response_class=HTMLResponse)
async def profiles_page(request: Request, user: User | None = Depends(get_current_user), session: Session = Depends(get_session)):
    profiles = list(session.exec(select(User).order_by(User.last_active_at.desc())).all())
    if not profiles:
        return RedirectResponse("/onboarding", status_code=303)
    ctx = _ctx(request, user, session)
    ctx.update({
        "profiles": profiles,
        "pin_profile": request.query_params.get("pin"),
        "picker_error": request.query_params.get("error"),
    })
    return request.app.state.templates.TemplateResponse(request, "profiles.html", ctx)


@router.post("/profiles/switch", response_class=HTMLResponse)
async def profiles_switch(
    request: Request,
    session: Session = Depends(get_session),
    profile_id: str = Form(""),
    pin: str = Form(""),
):
    try:
        pid = int(profile_id)
    except (TypeError, ValueError):
        return RedirectResponse("/", status_code=303)
    from datetime import datetime, timezone

    user = session.get(User, pid)
    if user is None:
        return RedirectResponse("/", status_code=303)
    if user.pin_hash and not verify_password(pin, user.pin_hash):
        return RedirectResponse(f"/profiles?pin={pid}&error=pin", status_code=303)
    user.last_active_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()
    token = make_session_token(pid)
    resp = RedirectResponse("/dashboard", status_code=303)
    resp.set_cookie(COOKIE_NAME, token, httponly=True, max_age=90 * 86400, samesite="lax")
    return resp


@router.post("/profiles/{profile_id}/update", response_class=HTMLResponse)
async def profiles_update(
    profile_id: str,
    request: Request,
    session: Session = Depends(get_session),
    name: str = Form(""),
    avatar: str = Form(""),
    pin: str = Form(""),
    clear_pin: str = Form("0"),
):
    try:
        pid = int(profile_id)
    except (TypeError, ValueError):
        return RedirectResponse("/profiles", status_code=303)
    user = session.get(User, pid)
    if user is None:
        return RedirectResponse("/profiles", status_code=303)
    if name.strip():
        user.name = name.strip()[:120]
    if avatar.strip():
        av = avatar.strip()
        user.avatar = av if av.startswith("/static/uploads/") else av[:8]
    if pin:
        if len(pin) < 4:
            return RedirectResponse("/profiles?error=pin_short", status_code=303)
        user.pin_hash = hash_password(pin)
    elif clear_pin == "1":
        user.pin_hash = None
    session.add(user)
    session.commit()
    return RedirectResponse("/settings#perfis", status_code=303)


@router.post("/profiles/{profile_id}/delete", response_class=HTMLResponse)
async def profiles_delete(
    profile_id: str,
    request: Request,
    session: Session = Depends(get_session),
    confirm: str = Form("0"),
):
    if confirm != "1":
        return RedirectResponse("/profiles?error=confirm", status_code=303)
    try:
        pid = int(profile_id)
    except (TypeError, ValueError):
        return RedirectResponse("/profiles", status_code=303)
    total = len(list(session.exec(select(User)).all()))
    if total <= 1:
        return RedirectResponse("/profiles?error=last", status_code=303)
    user = session.get(User, pid)
    if user is None:
        return RedirectResponse("/profiles", status_code=303)
    for model in (Attempt, UserConcept, UserBadge, CodeSnippet):
        for row in session.exec(select(model).where(model.user_id == pid)).all():
            session.delete(row)
    session.delete(user)
    session.commit()
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


# ── Onboarding ────────────────────────────────────────────────
@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page(request: Request, user: User | None = Depends(get_current_user), session: Session = Depends(get_session)):
    if user and request.query_params.get("new") != "1":
        return DASHBOARD_REDIRECT
    ctx = _ctx(request, None, session)
    ctx.update({"questions": DIAGNOSTIC_QUESTIONS, "new_profile": request.query_params.get("new") == "1"})
    return request.app.state.templates.TemplateResponse(request, "onboarding.html", ctx)


@router.post("/onboarding", response_class=HTMLResponse)
async def onboarding_register(
    request: Request,
    session: Session = Depends(get_session),
    name: str = Form(...),
    avatar: str = Form("🎓"),
    pin: str = Form(""),
    prior_level: str = Form("never"),
    goal: str = Form("curiosidade"),
    q_logica_1: str = Form("0"),
    q_sequencia_1: str = Form("0"),
    q_variavel_1: str = Form("0"),
    q_condicao_1: str = Form("0"),
    q_loop_1: str = Form("0"),
    q_dados_1: str = Form("0"),
):
    answers = {
        "logica_1": int(q_logica_1), "sequencia_1": int(q_sequencia_1),
        "variavel_1": int(q_variavel_1), "condicao_1": int(q_condicao_1),
        "loop_1": int(q_loop_1), "dados_1": int(q_dados_1),
    }
    name = name.strip()[:120]
    if not name:
        ctx = _ctx(request, None, session)
        ctx.update({"questions": DIAGNOSTIC_QUESTIONS, "error": "Preencha o nome do perfil."})
        return request.app.state.templates.TemplateResponse(request, "onboarding.html", ctx)
    if len(pin) > 0 and len(pin) < 4:
        ctx = _ctx(request, None, session)
        ctx.update({"questions": DIAGNOSTIC_QUESTIONS, "error": "O PIN precisa ter pelo menos 4 caracteres."})
        return request.app.state.templates.TemplateResponse(request, "onboarding.html", ctx)

    diagnosed = compute_diagnosed_level(prior_level, answers)
    user = User(
        name=name,
        email=f"local-{uuid.uuid4().hex}@pymaster.local",
        password_hash=hash_password(uuid.uuid4().hex),
        avatar=(avatar.strip()[:8] or "🎓"),
        pin_hash=hash_password(pin) if pin else None,
        prior_level=prior_level, goal=goal,
        diagnosed_level=diagnosed, onboarding_done=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    bootstrap_user(session, user, diagnosed)

    token = make_session_token(user.id)
    resp = DASHBOARD_REDIRECT
    resp.set_cookie(COOKIE_NAME, token, httponly=True, max_age=90 * 86400, samesite="lax")
    return resp


# ── Login / Logout ────────────────────────────────────────────
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: User | None = Depends(get_current_user)):
    if user:
        return DASHBOARD_REDIRECT
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
async def logout_submit():
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


# ── Dashboard ─────────────────────────────────────────────────
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, user: User | None = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user:
        return EOF_REDIRECT
    user.update_streak()
    session.add(user); session.commit(); session.refresh(user)
    registry = load_content()
    level, xp_in_level, prog = xp_progress(user.xp)
    next_item = progression.next_learning_item(session, user.id)
    due_count = len(review.due_reviews(session, user.id))
    overview = progression.overview(session, user.id)
    from app.engine.badges import user_badges_list
    badges = user_badges_list(session, user.id)[:6]
    recent_attempts = session.exec(
        select(Attempt).where(Attempt.user_id == user.id).order_by(Attempt.created_at.desc())
    ).all()[:5]
    python_progress = progression.overall_learning_progress(session, user.id, max_level=1)
    total_progress = progression.total_course_progress(session, user.id)
    from app.engine import certificate
    certificate.issue_certificate_if_ready(session, user)
    ctx = _ctx(request, user, session)
    ctx.update({
        "level": level, "xp_in_level": xp_in_level, "xp_progress": prog,
        "next_item": next_item, "due_count": due_count,
        "overview": overview, "badges": badges, "recent_attempts": recent_attempts,
        "python_progress": python_progress, "total_progress": total_progress,
    })
    return request.app.state.templates.TemplateResponse(request, "dashboard.html", ctx)


# ── Aprendizado ───────────────────────────────────────────────
@router.get("/learn", response_class=HTMLResponse)
async def learn_page(request: Request, user: User | None = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user:
        return EOF_REDIRECT
    overview = progression.overview(session, user.id)
    ctx = _ctx(request, user, session)
    ctx["overview"] = overview
    return request.app.state.templates.TemplateResponse(request, "learn.html", ctx)


@router.get("/concept/{concept_id}", response_class=HTMLResponse)
async def concept_page(concept_id: str, request: Request, user: User | None = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user:
        return EOF_REDIRECT
    registry = load_content()
    concept = registry.concept(concept_id)
    if not concept:
        return RedirectResponse("/learn", status_code=303)
    uc = progression.get_user_concept(session, user.id, concept_id)
    exercises = registry.exercises_of(concept_id)
    unlocked = progression.is_unlocked(session, user.id, concept_id)
    solved_ids = [
        e.id for e in exercises
        if session.exec(select(Attempt).where(
            Attempt.user_id == user.id, Attempt.exercise_id == e.id,
            Attempt.correct == True,  # noqa: E712
        )).first()
    ]
    concepts_ordered = registry.concepts_for(user.goal or "outro")
    idx_concept = next((i for i, c in enumerate(concepts_ordered) if c.id == concept_id), -1)
    next_concept_id = concepts_ordered[idx_concept + 1].id if 0 <= idx_concept + 1 < len(concepts_ordered) else None
    ex_nav = {}
    for i, ex in enumerate(exercises):
        ex_nav[ex.id] = {
            "prev": exercises[i - 1].id if i > 0 else None,
            "next": exercises[i + 1].id if i + 1 < len(exercises) else None,
            "next_concept": next_concept_id if i + 1 == len(exercises) else None,
        }
    ctx = _ctx(request, user, session)
    ctx.update({"concept": concept, "uc": uc, "exercises": exercises,
                "unlocked": unlocked, "solved_ids": solved_ids, "ex_nav": ex_nav})
    return request.app.state.templates.TemplateResponse(request, "concept.html", ctx)


# ── Revisão ──────────────────────────────────────────────────
@router.get("/review", response_class=HTMLResponse)
async def review_page(request: Request, user: User | None = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user:
        return EOF_REDIRECT
    due_items = review.due_reviews(session, user.id)
    registry = load_content()
    item = None
    if due_items:
        uc = due_items[0]
        concept = registry.concept(uc.concept_id)
        import random, hashlib
        from datetime import datetime
        day_seed = datetime.now().date().isoformat()
        pool = registry.exercises_of(uc.concept_id) or []
        if pool:
            seed = int(hashlib.sha256(f"{day_seed}:{uc.concept_id}".encode()).hexdigest()[:8], 16)
            item = random.Random(seed).choice(pool)
    ctx = _ctx(request, user, session)
    ctx["review_due"] = due_items
    ctx["review_exercise"] = item
    ctx["review_concept"] = registry.concept(item.concept) if item else None
    return request.app.state.templates.TemplateResponse(request, "review.html", ctx)


# ── Laboratório ──────────────────────────────────────────────
@router.get("/lab", response_class=HTMLResponse)
async def lab_page(request: Request, user: User | None = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user:
        return EOF_REDIRECT
    snippets = session.exec(
        select(CodeSnippet).where(CodeSnippet.user_id == user.id).order_by(CodeSnippet.created_at.desc())
    ).all()[:10]
    ctx = _ctx(request, user, session)
    ctx["snippets"] = snippets
    return request.app.state.templates.TemplateResponse(request, "lab.html", ctx)


# ── Mapa ──────────────────────────────────────────────────────
@router.get("/map", response_class=HTMLResponse)
async def map_page(request: Request, user: User | None = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user:
        return EOF_REDIRECT
    overview = progression.overview(session, user.id)
    ctx = _ctx(request, user, session)
    ctx["overview"] = overview
    return request.app.state.templates.TemplateResponse(request, "map.html", ctx)


# ── Conquistas ────────────────────────────────────────────────
@router.get("/badges", response_class=HTMLResponse)
async def badges_page(request: Request, user: User | None = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user:
        return EOF_REDIRECT
    from app.engine.badges import user_badges_list
    items = user_badges_list(session, user.id)
    ctx = _ctx(request, user, session)
    ctx["badges"] = items
    return request.app.state.templates.TemplateResponse(request, "badges.html", ctx)


# ── Certificado de conclusão ──────────────────────────────────
@router.get("/certificate", response_class=HTMLResponse)
async def certificate_page(request: Request, user: User | None = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user:
        return EOF_REDIRECT
    from app.engine import certificate as cert_engine
    cert_engine.issue_certificate_if_ready(session, user)
    modules = cert_engine.module_progress(session, user.id)
    cert = cert_engine.get_certificate(session, user.id)
    overall_pct = cert.overall_pct if cert else round(
        sum(m["mastery"] for m in modules) / len(modules), 1
    ) if modules else 0.0
    completed_count = sum(1 for m in modules if m["completion"] >= 100)
    cert_date_human = cert_date_short = ""
    if cert:
        from datetime import timezone as _tz
        issued = cert.issued_at.astimezone()
        meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
                 "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
        cert_date_human = f"{issued.day} de {meses[issued.month - 1]} de {issued.year}"
        cert_date_short = issued.strftime("%d/%m/%Y")
    ctx = _ctx(request, user, session)
    ctx.update({
        "certificate": cert,
        "modules": modules,
        "extra_badges": cert_engine.extra_badges_list(session, user.id),
        "overall_pct": overall_pct,
        "completed_count": completed_count,
        "modules_total": len(modules),
        "cert_date_human": cert_date_human,
        "cert_date_short": cert_date_short,
    })
    return request.app.state.templates.TemplateResponse(request, "certificate.html", ctx)


# ── Configurações ─────────────────────────────────────────────
@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user: User | None = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user:
        return EOF_REDIRECT
    profiles = list(session.exec(select(User).order_by(User.created_at)).all())
    ctx = _ctx(request, user, session)
    ctx["profiles"] = profiles
    ctx["about_error"] = request.query_params.get("about_error", "")
    return request.app.state.templates.TemplateResponse(request, "settings.html", ctx)


@router.post("/settings/about", response_class=HTMLResponse)
async def settings_about_update(
    request: Request,
    session: Session = Depends(get_session),
    user: User | None = Depends(get_current_user),
    name: str = Form(""),
    avatar: str = Form("🎓"),
    clear_avatar: str = Form("0"),
    file: UploadFile | None = File(None),
):
    if not user:
        return EOF_REDIRECT
    from urllib.parse import quote

    from app.engine import avatar as avatar_engine
    if name.strip():
        user.name = name.strip()[:120]
    try:
        if clear_avatar == "1":
            avatar_engine.remove_avatar_file(user.avatar)
            user.avatar = avatar.strip()[:8] or "🎓"
        elif file is not None and file.filename:
            user.avatar = avatar_engine.save_avatar_upload(file)
        elif avatar.strip():
            new_av = avatar.strip()
            if avatar_engine.is_image_avatar(new_av):
                user.avatar = new_av
            else:
                if avatar_engine.is_image_avatar(user.avatar):
                    avatar_engine.remove_avatar_file(user.avatar)
                user.avatar = new_av[:8]
        session.add(user)
        session.commit()
        return RedirectResponse("/settings#sobre", status_code=303)
    except ValueError as exc:
        return RedirectResponse(
            f"/settings#sobre?about_error={quote(str(exc))}", status_code=303,
        )


@router.post("/settings/update")
async def settings_update(
    request: Request,
    user: User | None = Depends(get_current_user),
    session: Session = Depends(get_session),
    theme: str = Form("dark"),
    font_scale: int = Form(100),
    reduce_motion: bool = Form(False),
):
    if not user:
        return EOF_REDIRECT
    user.theme = theme
    user.font_scale = max(80, min(150, font_scale))
    user.reduce_motion = reduce_motion
    session.add(user)
    session.commit()
    resp = RedirectResponse("/settings", status_code=303)
    resp.set_cookie(COOKIE_NAME, request.cookies.get(COOKIE_NAME, ""), httponly=True, max_age=90*86400)
    return resp


# ── Sobre ─────────────────────────────────────────────────────
@router.get("/about", response_class=HTMLResponse)
async def about_page(request: Request, user: User | None = Depends(get_current_user), session: Session = Depends(get_session)):
    ctx = _ctx(request, user, session)
    return request.app.state.templates.TemplateResponse(request, "about.html", ctx)


@router.get("/datasets", response_class=HTMLResponse)
async def datasets_page(request: Request, user: User | None = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user:
        return EOF_REDIRECT
    from app.config import DATASETS_DIR
    rows = sorted(p.name for p in DATASETS_DIR.glob("*.csv"))
    ctx = _ctx(request, user, session)
    ctx["datasets_rows"] = rows
    return request.app.state.templates.TemplateResponse(request, "datasets.html", ctx)


@router.get("/datasets/{name}", response_class=HTMLResponse)
async def dataset_view(name: str, request: Request, user: User | None = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user:
        return EOF_REDIRECT
    from app.config import DATASETS_DIR
    safe_name = (name or "").replace("/", "").replace("\\", "")
    path = DATASETS_DIR / safe_name
    if not path.exists() or not safe_name.endswith(".csv"):
        return RedirectResponse("/datasets", status_code=303)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    preview = lines[:15]
    rows_preview = [line.split(";") if ";" in line else line.split(",") for line in lines]
    header = rows_preview[0] if rows_preview else []
    data_rows = rows_preview[1:22]
    cols = len(header)
    ctx = _ctx(request, user, session)
    ctx.update({
        "name": safe_name, "n_cols": cols, "n_rows": len(rows_preview) - 1,
        "header": header, "data_rows": data_rows, "path_abs": str(path),
    })
    return request.app.state.templates.TemplateResponse(request, "dataset_view.html", ctx)