"""Repetição espaçada — agendamento de revisões por conceito."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import UserConcept

INTERVALS = [1, 2, 4, 7, 14, 30]

MASTERY_HINT_DECAY = 8.0     # penalidade por usar dica (aplicada pelo chamador)
MASTERY_LAPSE_DECAY = 12.0   # penalidade por erro durante revisão


def next_review_date(interval_days: int) -> datetime:
    today = datetime.now(timezone.utc)
    target = today + timedelta(days=interval_days)
    return datetime(target.year, target.month, target.day, tzinfo=timezone.utc)


def advance_interval(current: int) -> int:
    if current in INTERVALS:
        idx = min(INTERVALS.index(current) + 1, len(INTERVALS) - 1)
        return INTERVALS[idx]
    return INTERVALS[0]


def record_review_answer(session: Session, uc: UserConcept, correct: bool, new_mastery: float) -> None:
    """Atualiza o conceito após uma resposta em revisão espaçada."""
    uc.mastery = max(0.0, min(100.0, new_mastery))
    uc.reviews += 1
    if correct:
        uc.interval_days = advance_interval(uc.interval_days)
        uc.next_review = next_review_date(uc.interval_days)
    else:
        uc.lapses += 1
        uc.interval_days = INTERVALS[0]
        uc.next_review = datetime.now(timezone.utc)


def due_reviews(session: Session, user_id: int) -> list[UserConcept]:
    """Conceitos com revisão vencida (next_review <= hoje)."""
    today = datetime.now(timezone.utc).date()
    statement = select(UserConcept).where(
        UserConcept.user_id == user_id,
        UserConcept.next_review.isnot(None),
        UserConcept.mastery >= 20,
    )
    due: list[UserConcept] = []
    for uc in session.exec(statement):
        if uc.next_review is not None and _naive(uc.next_review).date() <= today:
            due.append(uc)
    due.sort(key=lambda u: _naive(u.next_review))
    return due


def _naive(dt: datetime) -> datetime:
    """Normaliza para datetime 'naive' (SQLite devolve sems timezone)."""
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def review_status(uc: UserConcept | None) -> dict:
    """Descreve o status de revisão de um conceito."""
    if uc is None or uc.next_review is None:
        return {"due": False, "days": 0}
    days = (uc.next_review.date() - datetime.now(timezone.utc).date()).days
    return {"due": days <= 0, "days": days}


def schedule_first_review(uc: UserConcept) -> None:
    """Primeira revisão agendada para amanhã."""
    uc.interval_days = INTERVALS[0]
    uc.next_review = next_review_date(INTERVALS[0])