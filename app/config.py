"""Configuração central do PyMaster."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "app" / "data"
CONTENT_DIR = DATA_DIR / "content"
DATASETS_DIR = DATA_DIR / "datasets"
STATIC_DIR = BASE_DIR / "app" / "static"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
SCRATCH_ROOT = BASE_DIR / ".scratch"
DB_PATH = Path(os.environ.get("PYMASTER_DB", BASE_DIR / "pymaster.db"))
SECRET_FILE = BASE_DIR / ".secret"

# Avatares enviados pelo usuário (servidos como estáticos, `/static/uploads/...`)
UPLOADS_DIR = STATIC_DIR / "uploads"

SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _load_secret() -> str:
    env_secret = os.environ.get("PYMASTER_SECRET")
    if env_secret:
        return env_secret
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text(encoding="utf-8").strip()
    token = secrets.token_hex(32)
    SECRET_FILE.write_text(token, encoding="utf-8")
    return token


SECRET_KEY = _load_secret()

SQLITE_URI = f"sqlite:///{DB_PATH.as_posix()}"

# Segurança do executor (padrões; cada exercício pode sobrescrever)
RUN_TIMEOUT_SECONDS = 3.0
RUN_TIMEOUT_LAB_SECONDS = 10.0
MAX_OUTPUT_CHARS = 20_000
MAX_VISUALIZER_STEPS = 3_000
MAX_RECURSION = 300

DEFAULT_FORBIDDEN_IMPORTS = {
    "os", "sys", "subprocess", "socket", "shutil", "ctypes",
    "multiprocessing", "importlib", "winreg", "wave", "pickle",
    "marshal", "gc", "signal", "threading", "asyncio", "concurrent",
    "ftplib", "http", "telnetlib", "urllib", "requests", "httpx",
    "tempfile", "sqlite3", "shelve",
}

# Datasets gerados para a trilha de dados
EXAMPLE_DATASETS = [
    "vendas.csv", "clientes.csv", "produtos.csv", "estoque.csv",
    "funcionarios.csv", "pedidos.csv", "financeiro.csv", "notas.csv",
    "imoveis.csv", "temperaturas.csv",
]