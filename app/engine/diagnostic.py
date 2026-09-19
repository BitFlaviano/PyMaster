"""Avaliação diagnóstica adaptativa do primeiro acesso."""
from __future__ import annotations

from sqlmodel import Session

from app.models import User, UserConcept

# Prioridade de entrada conforme resposta do usuário (§36)
PRIOR_LEVEL = {
    "never": 0,
    "tried": 0,
    "logic": 0,
    "other_lang": 1,
    "python": 2,
}

# Perguntas diagnósticas curtas (nível estimado → 0..3)
# Cada pergunta: texto, opções, índice correto e peso ("peso" sobe com a profundidade)
DIAGNOSTIC_QUESTIONS = [
    {
        "id": "logica_1",
        "q": "Você tem estas instruções: LIGAR COMPUTADOR, ABRIR EDITOR, ESCREVER CÓDIGO. "
             "O que significa seguir instruções nessa ordem exata?",
        "options": [
            "Escolher apenas uma instrução e ignorar as outras.",
            "Executar os passos um após o outro, na sequência dada.",
            "Executar os passos em qualquer ordem.",
            "Repetir o primeiro passo para sempre.",
        ],
        "answer": 1,
        "weight": 1,
    },
    {
        "id": "sequencia_1",
        "q": "Qual será a saída deste código?\n\n"
             "```python\nprint(\"A\")\nprint(\"B\")\n```",
        "options": ['"A B"', '"A"\n"B"', "A\nB", "B\nA"],
        "answer": 2,
        "weight": 1,
    },
    {
        "id": "variavel_1",
        "q": "O que o Python exibe?\n\n"
             "```python\nidade = 20\nidade = 21\nprint(idade)\n```",
        "options": ["20", "21", "20 21", "Erro"],
        "answer": 1,
        "weight": 2,
    },
    {
        "id": "condicao_1",
        "q": "O que será exibido?\n\n"
             "```python\nif 5 > 2:\n    print(\"sim\")\nelse:\n    print(\"não\")\n```",
        "options": ["sim", "não", "sim\nnão", "Erro"],
        "answer": 0,
        "weight": 2,
    },
    {
        "id": "loop_1",
        "q": "Quantas vezes a palavra \"oi\" aparece na tela?\n\n"
             "```python\nfor i in range(3):\n    print(\"oi\")\n```",
        "options": ["1", "2", "3", "4"],
        "answer": 2,
        "weight": 2,
    },
    {
        "id": "dados_1",
        "q": "Qual ferramenta Python é mais usada para analisar tabelas de dados?",
        "options": ["Pandas", "Turtle", "Calendar", "Turtle Graphics"],
        "answer": 0,
        "weight": 3,
    },
]

MIN_SCORE = 0.0
MAX_SCORE = 11.0  # soma dos pesos


def initial_from_prior(prior_level: str | None) -> int:
    return PRIOR_LEVEL.get(prior_level or "never", 0)


def compute_diagnosed_level(prior_level: str | None, answers: dict[str, int]) -> int:
    """Nível derivado da autodeclaração + desempenho no diagnóstico."""
    base = initial_from_prior(prior_level or "never")
    score = sum(
        q["weight"]
        for q in DIAGNOSTIC_QUESTIONS
        if int(answers.get(q["id"], -1)) == q["answer"]
    )
    pct = score / MAX_SCORE

    if base >= 2 and pct < 0.33:
        # Quem se disse "já programo" mas não acerta o diagnóstico básico
        base = max(0, base - 2)
    elif base >= 1 and pct < 0.20:
        base = 0

    for q in DIAGNOSTIC_QUESTIONS:
        if q["weight"] >= 2 and int(answers.get(q["id"], -1)) == q["answer"]:
            extra = 1
            break
    else:
        extra = 0
    return min(3, base + extra)


def bootstrap_user(session: Session, user: User, diagnosed_level: int) -> None:
    """Prepara o progresso inicial conforme o diagnóstico (avanço rápido)."""
    from app.engine.content import load_content

    registry = load_content()
    goal = user.goal or "outro"
    for concept in registry.concepts_for(goal):
        if concept.level < diagnosed_level:
            existing = session.exec(select_uc(user.id, concept.id)).first()
            if existing is None:
                session.add(
                    UserConcept(
                        user_id=user.id,
                        concept_id=concept.id,
                        mastery=60.0,
                        status="praticando",
                        attempts=1,
                        correct_attempts=1,
                    )
                )
    session.commit()


def select_uc(user_id: int, concept_id: str):
    from sqlmodel import select

    return select(UserConcept).where(
        UserConcept.user_id == user_id,
        UserConcept.concept_id == concept_id,
    )