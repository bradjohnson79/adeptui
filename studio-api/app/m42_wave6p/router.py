"""M42 Wave 6P gate HTTP surface."""

from __future__ import annotations

from fastapi import APIRouter

from .production_gate import evaluate_m42_wave6p_gate

router = APIRouter(tags=["m42-wave6p"])


@router.get("/m42-product/gate/wave6p")
def wave6p_gate():
    g = evaluate_m42_wave6p_gate()
    return {**g, "ok": bool(g.get("wave6pGo")), "passed": bool(g.get("wave6pGo"))}
