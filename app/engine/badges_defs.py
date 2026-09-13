"""Definições de conquistas (badges)."""
from __future__ import annotations

# `level` indica o módulo (Nível 0..6) a que a conquista pertence no
# certificado. Conquistas sem `level` são transversais (toda a jornada).
BADGES = [
    {
        "id": "primeiro_codigo",
        "name": "Primeiro Código",
        "icon": "⚡",
        "description": "Acertou seu primeiro exercício.",
        "level": 0,
    },
    {
        "id": "depurador_iniciante",
        "name": "Detetive de Bugs",
        "icon": "🔍",
        "description": "Detectou e corrigiu o primeiro bug.",
        "level": 3,
    },
    {
        "id": "autodidata_10",
        "name": "Autodidata",
        "icon": "🛠",
        "description": "Resolveu 10 exercícios sem usar nenhuma dica.",
    },
    {
        "id": "racha_conceito",
        "name": "Racha-Cuca",
        "icon": "🧠",
        "description": "Acertou 5 exercícios seguidos.",
    },
    {
        "id": "combo_3",
        "name": "Constância — 3 dias",
        "icon": "🔥",
        "description": "Estudou em 3 dias consecutivos.",
    },
    {
        "id": "combo_7",
        "name": "Constância — 7 dias",
        "icon": "🌋",
        "description": "Estudou em 7 dias consecutivos.",
    },
    {
        "id": "combo_14",
        "name": "Constância — 14 dias",
        "icon": "🚀",
        "description": "Estudou em 14 dias consecutivos.",
    },
    {
        "id": "revisor_3",
        "name": "Revisor Ativo",
        "icon": "🔁",
        "description": "Completou 3 revisões espaçadas.",
    },
    {
        "id": "dominio_primeiro",
        "name": "Primeiro Domínio",
        "icon": "🏅",
        "description": "Dominou o primeiro conceito (domínio ≥ 70%).",
        "level": 0,
    },
    {
        "id": "explorador_lab",
        "name": "Explorador do Lab",
        "icon": "🧪",
        "description": "Salvou código de experimentos no Laboratório.",
    },
    {
        "id": "xp_500",
        "name": "Colecionador de XP",
        "icon": "🎯",
        "description": "Acumulou 500 XP.",
    },
    {
        "id": "xp_2000",
        "name": "Maratonista de XP",
        "icon": "🏆",
        "description": "Acumulou 2.000 XP.",
    },
    {
        "id": "certificado_python",
        "name": "Mestre dos Fundamentos",
        "icon": "🎓",
        "description": "Dominou todo o Nível 0 e 1 com revisões em dia.",
        "level": 1,
    },
]

BADGE_BY_ID = {b["id"]: b for b in BADGES}


def unlocked_badge_ids(user_badges) -> set[str]:
    return {ub.badge_id for ub in user_badges}