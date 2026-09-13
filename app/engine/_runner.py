"""Runner executado em subprocesso isolado.

Lê um arquivo JSON de entrada, executa o código do usuário com guardas de
segurança (imports bloqueados, entrada via stdin controlada, saída limitada,
rastreamento opcional para o visualizador) e grava o resultado em JSON.
"""
from __future__ import annotations

import builtins
import json
import sys
import traceback
from typing import Any

SAFE_IMPORTS = {
    "math", "random", "statistics", "string", "datetime", "array",
    "collections", "functools", "itertools", "decimal", "fractions",
    "json", "csv", "re", "unicodedata", "keyword", "types", "abc",
    "dataclasses", "enum", "textwrap", "heapq", "bisect", "operator",
    "copy", "typing", "zoneinfo", "numpy", "pandas", "seaborn",
    "matplotlib", "plotly", "scipy", "statistics", "calendar", "pprint",
    "hashlib",
}


class _CaptureStream:
    def __init__(self, cap: int) -> None:
        self._buf: list[str] = []
        self._cap = cap
        self._overflow = False

    def write(self, text: str) -> int:
        if not text:
            return 0
        space = self._cap - self._chars()
        if space <= 0:
            self._overflow = True
            return len(text)
        self._buf.append(text[:space])
        if self._chars() >= self._cap:
            self._overflow = True
        return len(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False

    def _chars(self) -> int:
        return sum(len(chunk) for chunk in self._buf)

    def value(self) -> str:
        out = "".join(self._buf)
        if self._overflow:
            out += "\n[...saída truncada, limite atingido...]"
        return out


def _short_repr(value: Any, limit: int = 120) -> str:
    tokens: list[str] = []
    try:
        if isinstance(value, dict):
            for k, v in list(value.items())[:6]:
                tokens.append(f"{k!r}: {_scalar(v)}")
            return "{" + ", ".join(tokens) + ("..." if len(value) > 6 else "") + "}"
        if isinstance(value, (list, tuple)):
            kind = "lista" if isinstance(value, list) else "tupla"
            show = list(value)[:6]
            return f"{kind} [{', '.join(_scalar(x) for x in show)}]" + (
                " ..." if len(value) > 6 else "")
        if isinstance(value, set):
            show = list(value)[:4]
            return "conjunto {" + ", ".join(_scalar(x) for x in show) + "}"
    except Exception:
        pass
    return _scalar(value, limit)


def _scalar(value: Any, limit: int = 120) -> str:
    try:
        text = repr(value)
    except Exception:
        text = type(value).__name__
    if len(text) > limit:
        text = text[:limit] + "…"
    return text


class InputRequested(Exception):
    """Sinaliza que o código chamou input() e não há mais valores na fila."""

    def __init__(self, prompt: str = "") -> None:
        self.prompt = prompt
        super().__init__(prompt)


class _SafeInput:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self._idx = 0

    def __call__(self, prompt: str = "") -> str:
        if self._idx >= len(self._lines):
            raise InputRequested(prompt)
        line = self._lines[self._idx]
        self._idx += 1
        return line


def _trace(cfg: dict, state: dict):
    max_steps = int(cfg.get("max_steps", 3000))
    code_lines = state["code_lines"]

    def tracer(frame, event, arg):
        if event == "line" and frame.f_code.co_filename == "<PyMaster>":
            if state["trace_bytes"] > max_steps * 60:
                state["overflow"] = True
                return None
            state["steps"].append(_make_step(frame, code_lines.get(frame.f_lineno)))
            state["trace_bytes"] += 200
            if len(state["steps"]) >= max_steps:
                state["overflow"] = True
                return None
        return tracer

    return tracer


def _make_step(frame, source_line: str | None) -> dict:
    locals_snap: dict[str, str] = {}
    for name in list(frame.f_locals):
        if name.startswith("__"):
            continue
        value = frame.f_locals[name]
        display = _short_repr(value)
        vtype = type(value).__name__
        locals_snap[name] = f"{display}  ·{vtype}"
    return {
        "line": frame.f_lineno,
        "source": source_line,
        "variables": locals_snap,
    }


def main() -> None:
    in_path = sys.argv[1]
    out_path = sys.argv[2]
    cfg = json.loads(open(in_path, encoding="utf-8").read())

    code = cfg.get("code", "")
    stdin_lines = cfg.get("stdin", [])
    allowed = set(cfg.get("allow", [])) | SAFE_IMPORTS
    always_block = set(cfg.get("block", []))
    max_output = int(cfg.get("max_output", 20000))
    max_steps = int(cfg.get("max_steps", 3000))
    datasets_dir = cfg.get("datasets_dir", "")
    visualize = bool(cfg.get("visualize", False))
    recursion_limit = int(cfg.get("recursion", 300))

    result: dict[str, Any] = {
        "ok": False,
        "output": "",
        "steps": [],
        "error": None,
        "overflow": False,
    }

    out_stream = _CaptureStream(max_output)
    err_stream = _CaptureStream(4000)

    original_open = builtins.open

    def safe_open(file, mode="r", *args, **kwargs):
        if any(ch in mode for ch in "wax+"):
            raise PermissionError("Este ambiente não permite escrever em arquivos.")
        path = str(file)
        if datasets_dir and path.startswith(datasets_dir):
            return original_open(file, mode, *args, **kwargs)
        raise PermissionError("Somente leitura de arquivos dos datasets de exemplo é permitida.")

    blocked: set[str] = set()
    import_ctx = 0  # >0 indica que a importação atual já passou pelo crivo do usuário

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        nonlocal import_ctx
        base = name.split(".")[0]
        top_level = import_ctx == 0
        if base in blocked and top_level:
            raise ImportError(f"O módulo '{base}' não pode ser usado neste exercício.")
        if top_level:
            # A partir daqui, dependências internas de módulos permitidos
            # (ex.: statistics -> random -> os) ficam disponíveis; o bloqueio
            # continua valendo para imports diretos do usuário.
            import_ctx += 1
        try:
            return original_import(name, globals, locals, fromlist, level)
        finally:
            if top_level:
                import_ctx -= 1

    original_import = builtins.__import__
    builtins.__import__ = guarded_import
    if cfg.get("exempt_block"):
        # Exercícios de dados: bibliotecas pesadas (pandas/numpy/...) precisam
        # importar módulos do sistema internamente. Mantemos as demais guardas:
        # sem escrita em arquivos, leitura restrita a datasets, saída limitada,
        # tempo limite e encerramento forçado do processo.
        blocked.clear()
    else:
        for base_block in always_block:
            blocked.add(base_block)
        blocked.update(DEFAULT_BLOCKED)
        # Módulos permitidos (allow_imports do exercício + lista segura) ficam
        # disponíveis, inclusive para dependências internas (ex.: statistics → os).
        blocked.difference_update(allowed)

    old_stdout = sys.stdout
    old_stderr = sys.stderr
    original_input = builtins.input
    sys.stdout = out_stream
    sys.stderr = err_stream
    builtins.input = _SafeInput(stdin_lines)
    builtins.open = safe_open
    sys.setrecursionlimit(recursion_limit)

    namespace: dict[str, Any] = {"__name__": "__main__", "__builtins__": builtins}
    if datasets_dir:
        namespace["DATASETS_DIR"] = datasets_dir

    state = {"steps": [], "trace_bytes": 0, "code_lines": {}, "overflow": False}

    try:
        parsed_or_written = compile(code, "<PyMaster>", "exec")
    except SyntaxError as exc:
        err = {
            "class": "SyntaxError",
            "message": exc.msg or "erro de sintaxe",
            "line": getattr(exc, "lineno", None),
        }
        result["error"] = err
        result["output"] = err_stream.value()
        _write(out_path, result)
        return

    code_lines = {i: ln for i, ln in enumerate(code.splitlines(), start=1)}
    state["code_lines"] = code_lines

    try:
        if visualize:
            sys.settrace(_trace(cfg, state))
        try:
            exec(parsed_or_written, namespace)
        finally:
            sys.settrace(None)
    except InputRequested as ireq:  # noqa: BLE001
        result["input_request"] = {"prompt": ireq.prompt or ""}
    except Exception as exc:  # noqa: BLE001
        tb = traceback.extract_tb(sys.exc_info()[2])
        lineno = None
        if tb:
            for frame in tb:
                if frame.filename == "<PyMaster>":
                    lineno = frame.lineno
                    break
            if lineno is None:
                lineno = tb[-1].lineno
        result["error"] = {
            "class": type(exc).__name__,
            "message": str(exc),
            "line": lineno,
        }
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        builtins.input = original_input
        builtins.open = original_open
        builtins.__import__ = original_import

    result["ok"] = result["error"] is None and "input_request" not in result
    result["output"] = out_stream.value()
    result["steps"] = state["steps"]
    result["overflow"] = state["overflow"] or out_stream._overflow  # noqa: SLF001
    _write(out_path, result)


def _write(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)


DEFAULT_BLOCKED = {
    "os", "sys", "subprocess", "socket", "shutil", "ctypes", "multiprocessing",
    "importlib", "winreg", "pickle", "marshal", "gc", "signal", "threading",
    "asyncio", "concurrent", "ftplib", "http", "telnetlib", "urllib",
    "requests", "httpx", "tempfile", "sqlite3", "shelve",
}


if __name__ == "__main__":
    main()