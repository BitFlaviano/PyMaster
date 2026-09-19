"""Avaliação e desbloqueio de conquistas."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import Attempt, CodeSnippet, User, UserBadge, UserConcept
from app.engine.badges_defs import BADGES, BADGE_BY_ID


def count_exercises(session: Session, user_id: int, *, correct_only: bool = True) -> int:
    statement = select(Attempt).where(Attempt.user_id == user_id)
    if correct_only:
        statement = statement.where(Attempt.correct == True)  # noqa: E712
    return len(list(session.exec(statement)))


def evaluate_badges(
    session: Session,
    user_id: int,
    *,
    context: dict | None = None,
) -> list[str]:
    """Verifica todas as conquistas e desbloqueia as pendentes. Retorna os novos IDs."""
    context = context or {}
    have = set(session.exec(
        select(UserBadge.badge_id).where(UserBadge.user_id == user_id)
    ).all())
    newly: list[str] = []

    def grant(badge_id: str) -> bool:
        if badge_id in have:
            return False
        session.add(UserBadge(user_id=user_id, badge_id=badge_id, unlocked_at=datetime.now(timezone.utc)))
        have.add(badge_id)
        newly.append(badge_id)
        return True

    exercises_correct = count_exercises(session, user_id, correct_only=True)
    if exercises_correct >= 1:
        grant("primeiro_codigo")

    bug_types = {"find_error", "fix", "debug"}
    bug_correct = session.exec(
        select(Attempt).where(
            Attempt.user_id == user_id,
            Attempt.correct == True,  # noqa: E712
        )
    )
    if any(a.exercise_type in bug_types for a in bug_correct):
        grant("depurador_iniciante")

    no_hint = session.exec(
        select(Attempt).where(
            Attempt.user_id == user_id,
            Attempt.correct == True,  # noqa: E712
            Attempt.hints_used == 0,
        )
    )
    if len(list(no_hint)) >= 10:
        grant("autodidata_10")

    if _has_streak_correct(session, user_id, 5):
        grant("racha_conceito")

    user = context.get("user")
    if user is not None:
        if user.streak >= 3:
            grant("combo_3")
        if user.streak >= 7:
            grant("combo_7")
        if user.streak >= 14:
            grant("combo_14")
        if user.xp >= 500:
            grant("xp_500")
        if user.xp >= 2000:
            grant("xp_2000")

    reviews = session.exec(
        select(UserConcept).where(
            UserConcept.user_id == user_id,
            UserConcept.reviews >= 1,
        )
    )
    if sum(uc.reviews for uc in reviews) >= 3:
        grant("revisor_3")

    dominant = session.exec(
        select(UserConcept).where(
            UserConcept.user_id == user_id,
            UserConcept.mastery >= 70,
        )
    )
    if any(uc.mastery >= 70 for uc in dominant):
        grant("dominio_primeiro")

    snippets = session.exec(select(CodeSnippet).where(CodeSnippet.user_id == user_id))
    if len(list(snippets)) >= 1:
        grant("explorador_lab")

    if _mastered_level_0_1(session, user_id):
        grant("certificado_python")

    session.commit()
    return newly


def _has_streak_correct(session: Session, user_id: int, n: int) -> bool:
    attempts = session.exec(
        select(Attempt).where(Attempt.user_id == user_id).order_by(Attempt.created_at.desc())
    )
    streak = 0
    for attempt in attempts:
        if attempt.correct:
            streak += 1
            if streak >= n:
                return True
        else:
            return False
    return False


def _mastered_level_0_1(session: Session, user_id: int) -> bool:
    from app.engine.content import load_content

    registry = load_content()
    user = session.exec(select(User).where(User.id == user_id)).first()
    goal = (user.goal or "") if user else ""
    concepts = [
        c for c in registry.concepts_for(goal) if c.level <= 1
    ]
    if not concepts:
        return False
    ucs = session.exec(select(UserConcept).where(UserConcept.user_id == user_id))
    status = {uc.concept_id: uc for uc in ucs}
    for concept in concepts:
        uc = status.get(concept.id)
        if not uc or uc.mastery < 70:
            return False
    return True


def user_badges_list(session: Session, user_id: int) -> list[dict]:
    rows = session.exec(select(UserBadge).where(UserBadge.user_id == user_id)).all()
    dates = {r.badge_id: r.unlocked_at for r in rows}
    out = []
    for b in BADGES:
        item = dict(b)
        item["locked"] = b["id"] not in dates
        item["unlocked_at"] = dates.get(b["id"])
        out.append(item)
    return out