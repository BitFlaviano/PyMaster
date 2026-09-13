"""Modelos de dados (SQLModel / SQLite)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today_midnight() -> datetime:
    d = datetime.now(timezone.utc).date()
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    created_at: datetime = Field(default_factory=_now)

    # Perfil local
    avatar: str = "🎓"                 # emoji/nome de perfil
    pin_hash: str | None = None        # PIN opcional de proteção do perfil

    # Onboarding
    prior_level: str | None = None       # never|tried|logic|other_lang|python
    goal: str | None = None              # trabalho|faculdade|dados|automacao|curiosidade|carreira|outro
    diagnosed_level: int | None = None   # 0..16 (nível inicial estimado)
    onboarding_done: bool = False

    # Progressão / gamificação
    xp: int = 0
    streak: int = 0
    last_active_at: datetime | None = None

    # Acessibilidade / preferências
    theme: str = "dark"
    font_scale: int = 100
    reduce_motion: bool = False

    # Retomada onde parou
    continue_lesson_id: str | None = None

    def update_streak(self) -> bool:
        """Recomputa a sequência ao registrar atividade. Retorna True se houve avanço."""
        today = _today_midnight()
        if self.last_active_at is None:
            self.streak = 1
            self.last_active_at = today
            return True
        last_day = self.last_active_at.date()
        today_day = today.date()
        if last_day == today_day:
            return False
        if (today_day - last_day).days == 1:
            self.streak += 1
            self.last_active_at = today
            return True
        self.streak = 1
        self.last_active_at = today
        return True


class UserConcept(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    concept_id: str = Field(index=True)
    status: str = "novo"                       # novo|aprendendo|praticando|dominado|revisar
    mastery: float = 0.0                       # 0..100
    attempts: int = 0
    correct_attempts: int = 0
    reviews: int = 0
    lapses: int = 0                            # erros durante revisão espaçada
    last_answer_at: datetime | None = None
    next_review: datetime | None = None        # próxima data de revisão
    interval_days: int = 1                     # intervalo atual (1,2,4,7,14,30)


class Attempt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    exercise_id: str = Field(index=True)
    exercise_type: str
    concept_id: str | None = None
    correct: bool
    first_try: bool = False
    hints_used: int = 0
    time_s: int = 0
    xp_earned: int = 0
    created_at: datetime = Field(default_factory=_now)


class UserBadge(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    badge_id: str
    unlocked_at: datetime = Field(default_factory=_now)


class Certificate(SQLModel, table=True):
    """Certificado de conclusão emitido ao terminar todos os módulos."""
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    cert_no: str = Field(index=True, unique=True)
    overall_pct: float = 0.0        # aproveitamento global (média de domínio) no momento da emissão
    modules_total: int = 0
    issued_at: datetime = Field(default_factory=_now)


class CodeSnippet(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    title: str = "Experimento"
    code: str
    created_at: datetime = Field(default_factory=_now)