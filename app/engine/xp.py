"""Sistema de XP, níveis e títulos."""
from __future__ import annotations

from app.engine.content import DIFFICULTY_XP, Exercise

# Marcos de XP acumulado para subir de nível (nível 1 = a partir de 0)
LEVEL_XP = [0, 120, 300, 600, 1000, 1600, 2400, 3400, 4600, 6000,
            7800, 10000, 12800, 16200, 20400, 25600, 32000, 40000, 50000]

# Títulos da jornada (mapeamento amplo por faixa de nível)
LEVEL_TITLES = {
    1: "Novato", 2: "Novato",
    3: "Aprendiz", 4: "Aprendiz", 5: "Aprendiz",
    6: "Coder", 7: "Coder", 8: "Coder",
    9: "Programador", 10: "Programador", 11: "Programador",
    12: "Python Developer", 13: "Python Developer", 14: "Python Developer",
    15: "Data Analyst", 16: "Data Analyst", 17: "Data Analyst",
    18: "Data Master", 19: "Data Master", 20: "Data Master",
}


def level_from_xp(xp: int) -> int:
    level = 1
    for threshold in LEVEL_XP:
        if xp >= threshold:
            level += 1
    return max(1, level - 1)


def title_for_level(level: int) -> str:
    if level > 20:
        return "PyMaster"
    return LEVEL_TITLES.get(level, "Novato")


def xp_progress(xp: int) -> tuple[int, int, float]:
    """Retorna (nível, XP atual dentro do nível, progresso 0..1)."""
    level = level_from_xp(xp)
    if level >= len(LEVEL_XP):
        return level, 0, 1.0
    base = LEVEL_XP[level - 1] if level - 1 < len(LEVEL_XP) else 0
    nxt = LEVEL_XP[level] if level < len(LEVEL_XP) else base
    span = max(1, nxt - base)
    return level, xp - base, min(1.0, (xp - base) / span)


# Redução de XP conforme dicas usadas (quanto mais ajuda, menor a recompensa)
HINT_MULTIPLIER = {0: 1.0, 1: 0.80, 2: 0.60, 3: 0.40, 4: 0.15}


def xp_for_exercise(
    exercise: Exercise,
    *,
    correct: bool,
    first_try: bool,
    hints_used: int,
    is_review: bool,
) -> int:
    if not correct:
        return 0
    base = exercise.xp or DIFFICULTY_XP.get(exercise.difficulty, 15)
    multiplier = HINT_MULTIPLIER.get(hints_used, 0.5)
    if first_try and is_review:
        multiplier *= 1.6   # recuperação de conteúdo antigo vale mais
    elif first_try:
        multiplier *= 1.25
    elif is_review:
        multiplier *= 0.75
    return max(1, round(base * multiplier))


def next_level_xp(xp: int) -> int | None:
    level = level_from_xp(xp)
    if level < len(LEVEL_XP):
        return LEVEL_XP[level]
    return None