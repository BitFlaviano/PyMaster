"""Execução segura de código Python do usuário em subprocesso isolado.

O código nunca roda no processo do servidor: um runner filho (app/engine/_runner.py)
executa as instruções com guardas de importação, controle de entrada, limites de
saída e rastreamento para o visualizador.
"""
from __future__ import annotations

import json
import logging
import subprocess
import tempfile
import time
from pathlib import Path

from app.config import (
    DATASETS_DIR,
    DEFAULT_FORBIDDEN_IMPORTS,
    MAX_OUTPUT_CHARS,
    MAX_VISUALIZER_STEPS,
    RUN_TIMEOUT_LAB_SECONDS,
    RUN_TIMEOUT_SECONDS,
    SCRATCH_ROOT,
)

log = logging.getLogger("pymaster.sandbox")

RUNNER = Path(__file__).parent / "_runner.py"


def _python_executable() -> str:
    import sys

    return sys.executable


def run_code(
    code: str,
    stdin: str = "",
    *,
    timeout: float | None = None,
    allow_imports: list[str] | None = None,
    visualize: bool = False,
    forbid: set[str] | None = None,
    max_output: int = MAX_OUTPUT_CHARS,
    max_steps: int = MAX_VISUALIZER_STEPS,
    is_lab: bool = False,
    exempt_block: bool = False,
) -> dict:
    """Executa `code` isoladamente e devolve um dict de resultado."""
    scratch = Path(tempfile.mkdtemp(prefix="pymaster_run_", dir=SCRATCH_ROOT))
    in_path = scratch / "input.json"
    out_path = scratch / "output.json"

    payload = {
        "code": code,
        "stdin": stdin.splitlines(),
        "allow": allow_imports or [],
        "block": sorted(forbid or DEFAULT_FORBIDDEN_IMPORTS),
        "max_output": max_output,
        "max_steps": max_steps,
        "datasets_dir": str(DATASETS_DIR),
        "visualize": visualize,
        "exempt_block": bool(exempt_block),
    }
    in_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    limit = timeout if timeout is not None else (
        RUN_TIMEOUT_LAB_SECONDS if is_lab else RUN_TIMEOUT_SECONDS
    )
    cmd = [_python_executable(), str(RUNNER), str(in_path), str(out_path)]
    start = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(scratch),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            proc.communicate(timeout=limit)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=10,
                )
            except Exception:  # noqa: BLE001
                proc.kill()
            proc.wait(timeout=10)
    except Exception as exc:  # noqa: BLE001
        log.exception("Falha ao iniciar runner")
        return {"ok": False, "output": "", "error": {"class": "RuntimeError", "message": str(exc)}}

    elapsed = round(time.monotonic() - start, 3)
    result = {"ok": False, "output": "", "steps": [], "error": None, "timeout": timed_out}
    if timed_out:
        result["error"] = {
            "class": "TimeoutError",
            "message": "O código demorou demais para terminar e foi interrompido.",
        }
    elif out_path.exists():
        try:
            result = json.loads(out_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            result["error"] = {"class": "RuntimeError", "message": "Falha interna do executor."}
    else:
        result["error"] = {"class": "RuntimeError", "message": "O executor não produziu resultado."}

    result.setdefault("steps", [])
    result.setdefault("output", "")
    result["elapsed_ms"] = int(elapsed * 1000)
    result["timeout"] = bool(timed_out)
    return result


def run_with_inputs(code: str, test_input: str, expected_stripped: bool = True) -> dict:
    """Executa código com um teste (etapa de verificação de exercícios)."""
    return run_code(code, stdin=test_input)


def normalize_text(text: str) -> str:
    return " ".join(
        line.strip() for line in text.splitlines() if line.strip()
    ).strip().lower()


def outputs_match(expected: str, actual: str) -> bool:
    exp_lines = [ln.strip() for ln in expected.splitlines() if ln.strip()]
    act_lines = [ln.strip() for ln in actual.splitlines() if ln.strip()]
    return exp_lines == act_lines