"""API JSON (execução assíncrona para o Laboratório e Visualizador)."""
from __future__ import annotations

from fastapi import APIRouter, Body
from pydantic import BaseModel

from app.engine.sandbox import run_code

router = APIRouter(prefix="/api")


class RunRequest(BaseModel):
    code: str
    visualize: bool = False
    stdin: str = ""


@router.post("/run")
async def api_run(req: RunRequest):
    result = run_code(
        req.code,
        stdin=req.stdin,
        visualize=req.visualize,
        is_lab=True,
    )
    return {
        "ok": result.get("ok", False),
        "output": result.get("output", ""),
        "error": result.get("error"),
        "steps": result.get("steps", []),
        "input_request": result.get("input_request"),
        "timeout": bool(result.get("timeout")),
        "elapsed_ms": result.get("elapsed_ms", 0),
    }


@router.post("/visualize")
async def api_visualize(req: RunRequest):
    result = run_code(req.code, stdin=req.stdin, visualize=True, is_lab=False)
    return {
        "ok": result.get("ok", False),
        "output": result.get("output", ""),
        "error": result.get("error"),
        "steps": result.get("steps", []),
        "input_request": result.get("input_request"),
    }


@router.get("/health")
async def api_health():
    return {"status": "ok"}