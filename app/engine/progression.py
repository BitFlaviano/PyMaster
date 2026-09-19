"""Motor adaptativo: domínio por conceito, desbloqueio progressivo e rótulos."""
from __future__ import annotations

import hashlib
import random
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.engine.content import Exercise, load_content
from app.engine import review
from app.models import Attempt, User, UserConcept

WEIGHT = {"easy": 1.0, "medium": 1.5, "hard": 2.2}

# Nível mínimo de domínio do conceito anterior para liberar o próximo
PREREQ_MASTERY = 45.0


def _user_goal(session: Session, user_id: int) -> str:
    user = session.exec(select(User).where(User.id == user_id)).first()
    return (user.goal or "") if user else ""


def get_user_concept(session: Session, user_id: int, concept_id: str) -> UserConcept:
    row = session.exec(
        select(UserConcept).where(
            UserConcept.user_id == user_id,
            UserConcept.concept_id == concept_id,
        )
    ).first()
    if row is None:
        row = UserConcept(user_id=user_id, concept_id=concept_id)
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def recalc_status(uc: UserConcept) -> None:
    if uc.attempts <= 0:
        uc.status = "novo"
    elif uc.mastery >= 70 and uc.correct_attempts >= 2 and uc.attempts >= 3:
        uc.status = "dominado"
    elif uc.mastery >= 40:
        uc.status = "praticando"
    else:
        uc.status = "aprendendo"
    if uc.lapses > 0 and uc.attempts > 0 and uc.next_review is not None and datetime.now(timezone.utc).date() >= uc.next_review.date():
        uc.status = "revisar"


def exercise_solved(session: Session, user_id: int, exercise_id: str) -> bool:
    row = session.exec(
        select(Attempt).where(
            Attempt.user_id == user_id,
            Attempt.exercise_id == exercise_id,
            Attempt.correct == True,  # noqa: E712
        )
    ).first()
    return row is not None


def record_attempt(
    session: Session,
    user_id: int,
    exercise: Exercise,
    *,
    correct: bool,
    first_try: bool,
    hints_used: int,
    xp_earned: int,
    time_s: int,
    is_review: bool,
) -> UserConcept:
    """Registra a tentativa e atualiza a chapa de domínio do conceito."""
    uc = get_user_concept(session, user_id, exercise.concept)
    uc.attempts += 1
    weight = WEIGHT.get(exercise.difficulty, 1.0)

    attempt = Attempt(
        user_id=user_id,
        exercise_id=exercise.id,
        exercise_type=exercise.type,
        concept_id=exercise.concept,
        correct=correct,
        first_try=first_try,
        hints_used=hints_used,
        time_s=time_s,
        xp_earned=xp_earned,
    )
    session.add(attempt)

    if is_review:
        # Revisão: o erro derruba mais, o acerto consolida menos agressivamente
        delta = (weight * 1.1) if correct else -(weight * review.MASTERY_LAPSE_DECAY)
        if not correct:
            uc.lapses += 1
        new_mastery = uc.mastery + delta
        review.record_review_answer(session, uc, correct, min(new_mastery, 96.0))
    else:
        if correct:
            if hints_used >= 3:
                uc.mastery += weight * (100 - uc.mastery) * 0.12
            else:
                uc.mastery += weight * (100 - uc.mastery) * 0.38
            uc.correct_attempts += 1
        else:
            uc.mastery -= weight * 10.0
            if hints_used:
                uc.mastery -= review.MASTERY_HINT_DECAY
        uc.mastery = max(0.0, min(100.0, uc.mastery))
        if correct and uc.next_review is None:
            review.schedule_first_review(uc)

    uc.last_answer_at = datetime.now(timezone.utc)
    recalc_status(uc)
    session.add(uc)
    session.commit()
    return uc


def is_unlocked(session: Session, user_id: int, concept_id: str) -> bool:
    """O conceito está liberado? Exige domínio mínimo do conceito anterior."""
    registry = load_content()
    concept = registry.concept(concept_id)
    if concept is None:
        return False
    previous = None
    for c in registry.concepts_for(_user_goal(session, user_id)):
        if c.id == concept_id:
            break
        previous = c
    if previous is None:
        return True
    uc = session.exec(
        select(UserConcept).where(
            UserConcept.user_id == user_id,
            UserConcept.concept_id == previous.id,
        )
    ).first()
    return uc is not None and uc.mastery >= PREREQ_MASTERY


def next_learning_item(session: Session, user_id: int) -> tuple | None:
    """Próximo item da trilha: conceito → lição → exercício não resolvido."""
    registry = load_content()
    for concept in registry.concepts_for(_user_goal(session, user_id)):
        if not is_unlocked(session, user_id, concept.id):
            continue
        uc = session.exec(
            select(UserConcept).where(
                UserConcept.user_id == user_id,
                UserConcept.concept_id == concept.id,
            )
        ).first()
        if uc is not None and uc.status == "dominado":
            continue
        for lesson in registry.lessons_of(concept.id):
            for exc in registry.exercises_of(concept.id):
                if not exercise_solved(session, user_id, exc.id):
                    return (concept, lesson, exc)
    return None


def overview(session: Session, user_id: int) -> list[dict]:
    """Visão por conceito para o mapa/árvore de habilidades."""
    registry = load_content()
    rows = session.exec(
        select(UserConcept).where(UserConcept.user_id == user_id)
    )
    by_id = {uc.concept_id: uc for uc in rows}
    out = []
    goal = _user_goal(session, user_id)
    for concept in registry.concepts_for(goal):
        uc = by_id.get(concept.id)
        mastery = round(uc.mastery) if uc else 0
        status = uc.status if uc else "novo"
        if uc and uc.lapses > 0 and uc.next_review is not None and datetime.now(timezone.utc).date() >= uc.next_review.date():
            status = "revisar"
        out.append({
            "concept": concept,
            "mastery": mastery,
            "status": status,
            "unlocked": is_unlocked(session, user_id, concept.id),
            "next_review": uc.next_review if uc else None,
        })
    return out


def due_reviews_for_user(session: Session, user_id: int) -> list[tuple]:
    """Retorna [(conceito, exercício)] para as revisões de hoje (determinístico por dia)."""
    registry = load_content()
    goal = _user_goal(session, user_id)
    due_concepts = review.due_reviews(session, user_id)
    day_seed = datetime.now(timezone.utc).date().isoformat()
    result = []
    for uc in due_concepts:
        concept = registry.concept(uc.concept_id)
        if concept is None or not concept.exercises:
            continue
        if concept.goals and goal not in concept.goals:
            continue
        # seleção estável no dia: mesmo exercício até acertar
        pool = concept.exercises
        seed = hashlib.sha256(f"{day_seed}:{uc.concept_id}".encode()).hexdigest()
        rng = random.Random(int(seed[:8], 16))
        chosen = rng.choice(pool)
        result.append((concept, chosen))
    return result


def overall_learning_progress(session: Session, user_id: int, max_level: int = 1) -> float:
    """Percentual médio de domínio na trilha (camadas 0..max_level)."""
    registry = load_content()
    rows = session.exec(
        select(UserConcept).where(UserConcept.user_id == user_id)
    )
    by_id = {uc.concept_id: uc for uc in rows}
    goal = _user_goal(session, user_id)
    concepts = [
        c for c in registry.concepts_for(goal) if c.level <= max_level
    ]
    if not concepts:
        return 0.0
    total = sum(min(by_id[c.id].mastery, 100) if c.id in by_id else 0 for c in concepts)
    return round(total / len(concepts), 1)


def total_course_progress(session: Session, user_id: int) -> float:
    """Percentual de conclusão do curso completo (exercícios resolvidos ÷ total)."""
    registry = load_content()
    goal = _user_goal(session, user_id)
    all_exercises = [e for concept in registry.concepts_for(goal) for e in concept.exercises]
    if not all_exercises:
        return 0.0
    solved = sum(1 for e in all_exercises if exercise_solved(session, user_id, e.id))
    return round(solved / len(all_exercises) * 100, 1)