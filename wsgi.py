"""Adapter WSGI para hospedar o PyMaster no PythonAnywhere (plano gratuito).

Cuida de 3 coisas:
  1. coloca a pasta do projeto no `sys.path`;
  2. define os caminhos de dados dentro da home do usuário (disco persistente);
  3. embrulha o app ASGI/FastAPI em WSGI via a2wsgi (o PythonAnywhere usa mod_wsgi).
"""
import os
import sys

HOME = os.path.expanduser("~")
REPO = os.path.join(HOME, "PyMaster")

if REPO not in sys.path:
    sys.path.insert(0, REPO)

os.environ.setdefault("PYMASTER_DB", os.path.join(REPO, "pymaster.db"))
os.environ.setdefault("PYMASTER_SCRATCH_DIR", os.path.join(REPO, ".scratch"))
os.environ.setdefault("PYMASTER_UPLOADS_DIR", os.path.join(REPO, "app", "static", "uploads"))
os.environ.setdefault("PYMASTER_SECRET", "")  # se vazio, o próprio app gera .secret

from a2wsgi import ASGIMiddleware  # noqa: E402
from app.main import app  # noqa: E402

application = ASGIMiddleware(app)