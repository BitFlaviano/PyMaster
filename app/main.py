"""PyMaster — aplicação FastAPI."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import STATIC_DIR, TEMPLATES_DIR
from app.db import init_db
from app.engine.content import load_content
from app.router import api, fragments, pages

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger("pymaster")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    load_content()
    log.info("PyMaster iniciado — conteúdo carregado.")
    yield


app = FastAPI(title="PyMaster", version="0.1.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def _md(text: str) -> str:
    """Mini-markdown: parágrafos, **negrito**, `código`, listas simples e > citações."""
    import html
    import re

    text = html.escape(text.strip())
    lines = text.splitlines()
    out: list[str] = []
    in_list = False
    for raw in lines:
        line = raw
        if re.match(r"^\s*[\-\*]\s+", line):
            if not in_list:
                out.append("<ul>")
                in_list = True
            item = re.sub(r"^\s*[\-\*]\s+", "", line)
            out.append(f"<li>{item}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if line.startswith("> "):
            out.append(f'<blockquote>{line[2:]}</blockquote>')
            continue
        if not line.strip():
            out.append("")
            continue
        out.append(f"<p>{line}</p>")
    if in_list:
        out.append("</ul>")
    html_text = "\n".join(out)
    html_text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html_text)
    html_text = re.sub(r"`([^`]+)`", r"<code>\1</code>", html_text)
    html_text = re.sub(r"^### (.+)$", r"<h4>\1</h4>", html_text, flags=re.M)
    return html_text


def _shuffle_scoped(value, seed: str):
    import random

    items = list(value)
    rng = random.Random(seed if seed else "1")
    rng.shuffle(items)
    return items


templates.env.filters["md"] = _md
templates.env.filters["shuffle_scoped"] = _shuffle_scoped


def _xp_level(xp: int) -> int:
    from app.engine.xp import xp_progress

    return xp_progress(xp)[0]


def _xp_progress_pct(xp: int) -> float:
    from app.engine.xp import xp_progress

    return xp_progress(xp)[2]


templates.env.globals["xp_level_for"] = _xp_level
templates.env.globals["xp_progress_for"] = _xp_progress_pct


def _asset_ver() -> str:
    import hashlib
    import os

    h = hashlib.md5()
    for p in (
        os.path.join(STATIC_DIR, "css", "styles.css"),
        os.path.join(STATIC_DIR, "js", "app.js"),
    ):
        try:
            h.update(str(os.path.getmtime(p)).encode())
        except OSError:
            pass
    return h.hexdigest()[:8]


templates.env.globals["asset_ver"] = _asset_ver

from app.engine.avatar import avatar_src  # noqa: E402

templates.env.globals["avatar_src"] = avatar_src

app.state.templates = templates

app.include_router(pages.router)
app.include_router(fragments.router)
app.include_router(api.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)