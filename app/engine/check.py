"""Verificação das respostas de exercícios interativos."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.engine.content import ContentRegistry, Exercise
from app.engine import sandbox
from app.engine.error_patterns import analyze_code_error

# Bibliotecas que exigem liberar o bloqueio de módulos internos no sandbox
# (pandas/numpy importam os/sys/subprocess/... na inicialização).
DATA_LIBS = {"pandas", "numpy", "matplotlib", "scipy", "seaborn", "plotly", "polars"}


def data_mode(exercise: Exercise) -> bool:
    if not set(exercise.allow_imports).isdisjoint(DATA_LIBS):
        return True
    if exercise.code and re.search(
        r"^\s*(?:import|from)\s+(pandas|numpy)", exercise.code, re.M
    ):
        return True
    return False


@dataclass
class CheckResult:
    correct: bool
    message: str = ""
    feedback: str = ""
    actual_output: str = ""
    expected_output: str = ""
    run_error: dict | None = None
    tests_passed: int = 0
    tests_total: int = 0
    final_code: str = ""

    @property
    def all_ok(self) -> bool:
        return self.correct


def signal_correct(exercise: Exercise, note: str = "Resposta correta!") -> CheckResult:
    hint_count = len(exercise.hints)
    if hint_count:
        note += " De olho em eventuais dicas para manter o máximo de XP."
    return CheckResult(correct=True, message=note)


def signal_wrong(message: str, exercise: Exercise, extra: str = "") -> CheckResult:
    return CheckResult(correct=False, message=message, feedback=extra)


def check_exercise(
    registry: ContentRegistry,
    exercise: Exercise,
    user_answer: str,
) -> CheckResult:
    """Avalia a resposta do usuário conforme o tipo de exercício."""
    etype = exercise.type

    if etype in {"choice", "explain"}:
        try:
            ok = int(user_answer.strip()) == int(exercise.answer or -1)
        except (TypeError, ValueError):
            ok = exercise.answer is not None and user_answer.strip() == str(exercise.answer)
        return signal_correct(exercise) if ok else signal_wrong(
            "Resposta incorreta. Revise o conceito e tente de novo.",
            exercise,
        )

    if etype == "complete":
        expected = sandbox.normalize_text(exercise.answer or "")
        given = sandbox.normalize_text(user_answer)
        if expected == given:
            return signal_correct(exercise)
        return signal_wrong(
            f"Quase! O trecho esperado era: `{exercise.answer}`", exercise,
        )

    if etype == "predict":
        return _check_predict(exercise, user_answer)

    if etype == "order":
        try:
            given_lines = [ln for ln in user_answer.split("\n")]
            ok = given_lines == exercise.lines
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            return signal_correct(exercise)
        return signal_wrong("A ordem ainda não está correta! Compare cada linha.", exercise)

    if etype == "find_error":
        try:
            given_line = int(user_answer.strip())
        except (TypeError, ValueError):
            given_line = -1
        if exercise.error_line is not None and given_line == exercise.error_line:
            return signal_correct(exercise, "Você detectou a linha do problema.")
        return signal_wrong(
            "Ainda não é essa linha. Analise qual comando pode causar o erro.",
            exercise,
        )

    if etype in {"fix", "write", "debug"}:
        return _check_code(exercise, user_answer)

    return CheckResult(correct=False, message="Tipo de exercício não suportado.")


def _check_predict(exercise: Exercise, user_answer: str) -> CheckResult:
    """Resposta do usuário é comparada com a execução REAL do código."""
    run = sandbox.run_code(
        exercise.code or "",
        visualize=False,
        allow_imports=exercise.allow_imports,
        exempt_block=data_mode(exercise),
    )
    actual = run.get("output", "")
    if run.get("error"):
        return CheckResult(
            correct=False,
            message="O código, na verdade, gera um erro. Execute para descobrir qual!",
            actual_output=actual,
            run_error=run["error"],
        )
    if sandbox.outputs_match(user_answer, actual):
        return signal_correct(exercise)
    return CheckResult(
        correct=False,
        message="A previsão não bate com o que o Python exibe. Veja a execução passo a passo.",
        actual_output=actual,
        expected_output=run.get("output", ""),
    )


def _check_code(exercise: Exercise, user_code: str) -> CheckResult:
    if not user_code.strip():
        return CheckResult(correct=False, message="Escreva seu código antes de verificar.")

    missing = [token for token in exercise.must_include if token not in user_code]
    if missing:
        return CheckResult(
            correct=False,
            message=f"O código precisa conter: `{'`, `'.join(missing)}` (sem isso, o exercício perde o sentido).",
        )

    if len(user_code) > 20_000:
        return CheckResult(correct=False, message="Código grande demais para este exercício (máx. 20.000 caracteres).")

    if reimports_forbidden(exercise, user_code):
        return CheckResult(
            correct=False,
            message="Este exercício não permite importar módulos externos.",
        )

    tests = exercise.tests
    if not tests:
        return _free_form_check(exercise, user_code)

    passed = 0
    failures: list[str] = []
    last_run: dict = {}
    expected_vis: str = ""
    dmode = data_mode(exercise)
    for test in tests:
        run = sandbox.run_code(
            user_code,
            stdin=test.input,
            allow_imports=exercise.allow_imports,
            exempt_block=dmode,
        )
        last_run = run
        if run.get("error"):
            failures.append(f"{test.name}: erro ao executar: {run['error'].get('class', 'erro')}")
            continue
        ok = sandbox.outputs_match(test.expected, run.get("output", ""))
        if test.must_not_contain:
            if test.must_not_contain in (run.get("output", "") + user_code):
                failures.append(f"{test.name}: o código/saída não pode conter `{test.must_not_contain}`")
                ok = False
        if ok:
            passed += 1
        else:
            failures.append(f"{test.name}: saída esperada diferente da obtida.")
            if not expected_vis:
                expected_vis = test.expected
    total = len(tests)

    if passed == total:
        return CheckResult(
            correct=True,
            message=f"Todos os {total} teste(s) passaram!",
            tests_passed=passed,
            tests_total=total,
            actual_output=last_run.get("output", ""),
            final_code=user_code,
        )

    feedback = analyze_code_error(exercise, user_code, last_run.get("error"))
    return CheckResult(
        correct=False,
        message=f"{len(failures)} teste(s) falharam. Ajuste o código e tente de novo.",
        feedback=feedback or "",  # "" (falsy) é substituído por fallback no template
        tests_passed=passed,
        tests_total=total,
        actual_output=last_run.get("output", ""),
        expected_output=expected_vis,
        run_error=last_run.get("error"),
        final_code=user_code,
    )


def _free_form_check(exercise: Exercise, user_code: str) -> CheckResult:
    """Exercícios 'write' sem testes declarados: validam execução sem erro + dica do solução."""
    run = sandbox.run_code(
        user_code,
        allow_imports=exercise.allow_imports,
        exempt_block=data_mode(exercise),
    )
    if run.get("error"):
        feedback = analyze_code_error(exercise, user_code, run["error"])
        return CheckResult(
            correct=False,
            message="O código ainda apresenta erro de execução.",
            feedback=feedback or run["error"].get("message", ""),
            actual_output=run.get("output", ""),
            run_error=run["error"],
        )
    return CheckResult(
        correct=True,
        message="Seu código rodou sem erros!",
        actual_output=run.get("output", ""),
        final_code=user_code,
    )


def reimports_forbidden(exercise: Exercise, user_code: str) -> bool:
    if exercise.allow_imports:
        allowed = set(exercise.allow_imports)
    else:
        allowed = set()
    needed = find_imports(user_code)
    return bool({n for n in needed if n not in allowed})


def find_imports(code: str) -> set[str]:
    imports: set[str] = set()
    for match in re.finditer(r"^\s*(?:import|from)\s+([A-Za-z_][\w.]*)", code, re.M):
        imports.add(match.group(1).split(".")[0])
    return imports