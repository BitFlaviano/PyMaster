"""Fragmentos HTMX (feedback, execução, progressão, revisão)."""
from __future__ import annotations

import hashlib
import random
import time
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.db import get_session
from app.engine import badges, progression, review
from app.engine.check import check_exercise
from app.engine.content import load_content
from app.engine.error_patterns import analyze_code_error
from app.engine.sandbox import outputs_match, run_code
from app.engine.xp import xp_for_exercise
from app.models import Attempt, CodeSnippet, User
from app.router.deps import get_current_user, template_context

router = APIRouter()


def _user(request: Request, session: Session) -> User | None:
    return get_current_user(request, session)


def _exercise_status(exercise, user) -> str:
    return ""


def _daily_pick(pool, concept_id: str):
    seed = int(hashlib.sha256(
        f"{datetime.now().date().isoformat()}:{concept_id}".encode()
    ).hexdigest()[:8], 16)
    return random.Random(seed).choice(pool) if pool else None


def _review_expected(exercise) -> str | None:
    """Texto do que era esperado, para o feedback de revisão."""
    et = exercise.type
    if et in {"choice", "explain"} and exercise.options and exercise.answer is not None:
        try:
            idx = int(exercise.answer)
        except (TypeError, ValueError):
            idx = -1
        return exercise.options[idx] if 0 <= idx < len(exercise.options) else None
    if et == "complete":
        return exercise.answer
    if et == "order" and exercise.lines:
        return "\n".join(exercise.lines)
    if et == "find_error" and exercise.lines and exercise.error_line is not None:
        if 0 <= exercise.error_line < len(exercise.lines):
            return exercise.lines[exercise.error_line]
        return None
    if et in {"write", "fix", "debug"}:
        return (exercise.solution or "").rstrip("\n") or None
    if et == "predict":
        return exercise.answer
    return None


# ── Exercício: executar código dentro do enunciado ────────────
@router.post("/frag/exercise/{exercise_id}/run", response_class=HTMLResponse)
async def frag_exercise_run(
    exercise_id: str,
    request: Request,
    session: Session = Depends(get_session),
    code: str = Form(""),
    stdin: str = Form(""),
):
    user = _user(request, session)
    registry = load_content()
    exercise = registry.exercise(exercise_id)
    if not exercise:
        return HTMLResponse("<div class='msg-err'>Exercício não encontrado.</div>")
    result = run_code(code, stdin=stdin, is_lab=False)
    ctx = template_context(request, session, user)
    ctx.update({"code": code, "result": result, "exercise": exercise, "user": user})
    return request.app.state.templates.TemplateResponse(request, "partials/_exercise_console.html", ctx)


# ── Exercício: enviar resposta ────────────────────────────────
@router.post("/frag/exercise/{exercise_id}/answer", response_class=HTMLResponse)
async def frag_exercise_answer(
    exercise_id: str,
    request: Request,
    session: Session = Depends(get_session),
    answer: str = Form(""),
    code: str = Form(""),
):
    user = _user(request, session)
    if not user:
        return HTMLResponse("<div class='msg-err'>Faça login.</div>")
    registry = load_content()
    exercise = registry.exercise(exercise_id)
    if not exercise:
        return HTMLResponse("<div class='msg-err'>Exercício não encontrado.</div>")

    prior = list(session.exec(select(Attempt).where(
        Attempt.user_id == user.id, Attempt.exercise_id == exercise_id,
    )).all())
    first_try = not any(a.correct for a in prior)
    hints_used = max((a.hints_used for a in prior), default=0)

    payload = code if exercise.type in {"write", "fix", "debug"} else answer
    check = check_exercise(registry, exercise, payload)
    if exercise.type == "predict":
        run = run_code(exercise.code or "", is_lab=False)
        if run.get("error"):
            check.actual_output = run["error"].get("message", "")
            check.correct = False
        else:
            check.actual_output = run.get("output", "")
            check.correct = outputs_match(answer, run.get("output", ""))
    t_elapsed = max(1, int(time.time() - prior[0].created_at.timestamp())) if prior else 5

    xp = xp_for_exercise(exercise, correct=check.correct, first_try=first_try,
                         hints_used=hints_used, is_review=False)
    if check.correct:
        user.xp += xp
        user.update_streak()
        session.add(user)
    uc = progression.record_attempt(
        session, user.id, exercise, correct=check.correct,
        first_try=first_try, hints_used=hints_used,
        xp_earned=xp, time_s=t_elapsed, is_review=False,
    )
    if check.correct:
        badges.evaluate_badges(session, user.id, context={"user": user})
        from app.engine import certificate
        certificate.issue_certificate_if_ready(session, user)
    ctx = template_context(request, session, user)
    ctx.update({
        "exercise": exercise, "check": check, "xp_earned": xp,
        "uc": uc, "user": user,
    })
    return request.app.state.templates.TemplateResponse(request, "partials/_exercise_feedback.html", ctx)


# ── Exercício: próxima dica ──────────────────────────────────
@router.post("/frag/exercise/{exercise_id}/hint", response_class=HTMLResponse)
async def frag_exercise_hint(
    exercise_id: str,
    request: Request,
    session: Session = Depends(get_session),
    hint_level: int = Form(1),
):
    registry = load_content()
    exercise = registry.exercise(exercise_id)
    if not exercise:
        return HTMLResponse("<div class='msg-err'>Exercício não encontrado.</div>")
    hints = exercise.hints
    idx = max(0, min(hint_level - 1, len(hints) - 1)) if hints else 0
    text = hints[idx] if hints and idx < len(hints) else "Sem mais dicas."
    ctx = {"text": text, "level": hint_level, "max": len(hints)}
    return request.app.state.templates.TemplateResponse(request, "partials/_hint.html", ctx)


# ── Revisão: responder ────────────────────────────────────────
@router.post("/frag/review/submit", response_class=HTMLResponse)
async def frag_review_submit(
    request: Request,
    session: Session = Depends(get_session),
    concept_id: str = Form(""),
    exercise_id: str = Form(""),
    answer: str = Form(""),
    code: str = Form(""),
):
    user = _user(request, session)
    if not user:
        return HTMLResponse("<div class='msg-err'>Faça login.</div>")
    registry = load_content()
    exercise = registry.exercise(exercise_id)
    if not exercise:
        return HTMLResponse("<div class='msg-err'>Exercício não encontrado.</div>")
    payload = code if exercise.type in {"write", "fix", "debug"} else answer
    check = check_exercise(registry, exercise, payload)
    if exercise.type == "predict":
        run = run_code(exercise.code or "", is_lab=False)
        if run.get("error"):
            check.actual_output = run["error"].get("message", "")
            check.correct = False
        else:
            check.actual_output = run.get("output", "")
            check.correct = outputs_match(answer, run.get("output", ""))
    xp = xp_for_exercise(exercise, correct=check.correct, first_try=True,
                         hints_used=0, is_review=True)
    if check.correct:
        user.xp += xp
        user.update_streak()
        session.add(user)
    uc = progression.record_attempt(
        session, user.id, exercise, correct=check.correct, first_try=True,
        hints_used=0, xp_earned=xp, time_s=0, is_review=True,
    )
    badges.evaluate_badges(session, user.id, context={"user": user})
    from app.engine import certificate
    certificate.issue_certificate_if_ready(session, user)

    due = review.due_reviews(session, user.id)
    concept = registry.concept(concept_id) if concept_id else None
    ctx = template_context(request, session, user)
    ctx.update({
        "check": check, "xp_earned": xp, "user": user,
        "review_concept": concept,
        "review_exercise": exercise,
        "review_due": due,
        "user_answer": payload,
        "expected_text": _review_expected(exercise),
    })
    return request.app.state.templates.TemplateResponse(request, "partials/_review_feedback.html", ctx)


# ── Revisão: carregar próxima pergunta ──────────────────────────
@router.get("/frag/review/next", response_class=HTMLResponse)
async def frag_review_next(
    request: Request,
    session: Session = Depends(get_session),
):
    user = _user(request, session)
    if not user:
        return HTMLResponse("<div class='msg-err'>Faça login.</div>")
    registry = load_content()
    due = review.due_reviews(session, user.id)
    if due:
        nuc = due[0]
        concept = registry.concept(nuc.concept_id)
        pool = registry.exercises_of(nuc.concept_id)
        item = _daily_pick(pool, nuc.concept_id) if pool else None
        if item:
            ctx = template_context(request, session, user)
            ctx.update({"next_item": item, "next_concept": concept, "user": user})
            return request.app.state.templates.TemplateResponse(request, "partials/_review_next.html", ctx)
    ctx = template_context(request, session, user)
    ctx.update({"user": user})
    return request.app.state.templates.TemplateResponse(request, "partials/_review_done.html", ctx)


# ── Laboratório: executar ──────────────────────────────────────
@router.post("/frag/lab/run", response_class=HTMLResponse)
async def frag_lab_run(
    request: Request,
    session: Session = Depends(get_session),
    code: str = Form(""),
    visualize: bool = Form(False),
):
    user = _user(request, session)
    if not user:
        return HTMLResponse("<div class='msg-err'>Faça login.</div>")
    t_start = time.time()
    result = run_code(code, is_lab=True, visualize=visualize)
    elapsed_ms = int((time.time() - t_start) * 1000)
    if result.get("error"):
        result["tip"] = analyze_code_error(None, code, result.get("error"))
    ctx = template_context(request, session, user)
    ctx.update({"result": result, "code": code, "user": user, "elapsed_ms": elapsed_ms})
    return request.app.state.templates.TemplateResponse(request, "partials/_lab_console.html", ctx)


# ── Laboratório: salvar ───────────────────────────────────────
@router.post("/frag/lab/save", response_class=HTMLResponse)
async def frag_lab_save(
    request: Request,
    session: Session = Depends(get_session),
    code: str = Form(""),
    title: str = Form("Experimento"),
):
    user = _user(request, session)
    if not user:
        return HTMLResponse("<div class='msg-err'>Faça login.</div>")
    session.add(CodeSnippet(
        user_id=user.id, title=(title.strip()[:100] or "Experimento"),
        code=code[:20_000],
    ))
    session.commit()
    badges.evaluate_badges(session, user.id, context={"user": user})
    snippets = list(session.exec(select(CodeSnippet).where(
        CodeSnippet.user_id == user.id
    ).order_by(CodeSnippet.created_at.desc())).all()[:10])
    ctx = template_context(request, session, user)
    ctx.update({"snippets": snippets, "user": user})
    return request.app.state.templates.TemplateResponse(request, "partials/_lab_history.html", ctx)


# ── Settings: toggle ──────────────────────────────────────────
@router.post("/frag/settings/toggle", response_class=HTMLResponse)
async def frag_settings_toggle(
    request: Request,
    session: Session = Depends(get_session),
    key: str = Form("theme"),
):
    user = _user(request, session)
    if not user:
        return HTMLResponse("")
    if key == "theme":
        user.theme = "light" if user.theme == "dark" else "dark"
    elif key == "reduce_motion":
        user.reduce_motion = not user.reduce_motion
    session.add(user)
    session.commit()
    return HTMLResponse("ok")


# ── Settings: font scale ──────────────────────────────────────
@router.post("/frag/settings/font_scale", response_class=HTMLResponse)
async def frag_settings_font_scale(
    request: Request,
    session: Session = Depends(get_session),
    scale: int = Form(100),
):
    user = _user(request, session)
    if user:
        user.font_scale = max(80, min(150, scale))
        session.add(user)
        session.commit()
        return HTMLResponse(f"{user.font_scale}%")
    return HTMLResponse("100%")