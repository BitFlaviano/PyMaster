"""Certificado de conclusão — emissão, progresso por módulo e conquistas."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.engine.badges_defs import BADGES
from app.engine.content import load_content
from app.models import Certificate, User, UserBadge, UserConcept

# Paleta por módulo (índice = nível) — cada barra ganha sua cor.
LEVEL_COLORS = [
    "#7c3aed",   # 0 · roxo
    "#ec4899",   # 1 · rosê
    "#10b981",   # 2 · esmeralda
    "#f59e0b",   # 3 · âmbar
    "#0ea5e9",   # 4 · céu
    "#14b8a6",   # 5 · teal
    "#d946ef",   # 6 · fúcsia
]
LEVEL_GRADIENTS = [
    "linear-gradient(90deg,#7c3aed,#c026d3)",
    "linear-gradient(90deg,#ec4899,#fb7185)",
    "linear-gradient(90deg,#10b981,#0d9488)",
    "linear-gradient(90deg,#f59e0b,#ea580c)",
    "linear-gradient(90deg,#0ea5e9,#2563eb)",
    "linear-gradient(90deg,#14b8a6,#06b6d4)",
    "linear-gradient(90deg,#d946ef,#a21caf)",
]


def get_certificate(session: Session, user_id: int) -> Certificate | None:
    return session.exec(
        select(Certificate).where(Certificate.user_id == user_id)
    ).first()


def unlocked_badges(session: Session, user_id: int) -> set[str]:
    return set(session.exec(
        select(UserBadge.badge_id).where(UserBadge.user_id == user_id)
    ).all())


def module_progress(session: Session, user_id: int) -> list[dict]:
    """Progresso por módulo: conclusão (% conceitos com status 'dominado') e domínio médio."""
    registry = load_content()
    user = session.exec(select(User).where(User.id == user_id)).first()
    goal = (user.goal or "") if user else ""
    concepts_by_id = {
        uc.concept_id: uc
        for uc in session.exec(select(UserConcept).where(UserConcept.user_id == user_id))
    }
    have = unlocked_badges(session, user_id)
    out: list[dict] = []
    for level in registry.levels:
        concepts = [
            c for c in registry.concepts_for(goal) if c.level == level.number
        ]
        if not concepts:
            continue
        total = len(concepts)
        dominated = sum(
            1 for c in concepts
            if (uc := concepts_by_id.get(c.id)) is not None and uc.status == "dominado"
        )
        completion = round(dominated / total * 100, 1)
        mastery = round(
            sum(min(concepts_by_id[c.id].mastery, 100) if c.id in concepts_by_id else 0
                for c in concepts)
            / total,
            1,
        )
        out.append({
            "number": level.number,
            "title": level.title,
            "completion": completion,
            "mastery": mastery,
            "dominated": dominated,
            "total": total,
            "color": LEVEL_COLORS[len(out) % len(LEVEL_COLORS)],
            "gradient": LEVEL_GRADIENTS[len(out) % len(LEVEL_GRADIENTS)],
            "badges": [b for b in BADGES if b.get("level") == level.number and b["id"] in have],
        })
    return out


def extra_badges_list(session: Session, user_id: int) -> list[dict]:
    have = unlocked_badges(session, user_id)
    return [b for b in BADGES if "level" not in b and b["id"] in have]


def all_modules_done(modules: list[dict]) -> bool:
    return bool(modules) and all(m["completion"] >= 100 for m in modules)


def issue_certificate_if_ready(session: Session, user: User) -> Certificate | None:
    """Emite o certificado quando todos os módulos estão concluídos (uma única vez)."""
    existing = get_certificate(session, user.id)
    if existing is not None:
        return existing
    modules = module_progress(session, user.id)
    if not all_modules_done(modules):
        return None
    overall = round(sum(m["mastery"] for m in modules) / len(modules), 1)
    year = datetime.now(timezone.utc).year
    cert = Certificate(
        user_id=user.id,
        cert_no=f"PYM-{year}-{user.id:03d}-{secrets.token_hex(3).upper()}",
        overall_pct=overall,
        modules_total=len(modules),
    )
    session.add(cert)
    session.commit()
    session.refresh(cert)
    return cert