"""M42 W43 Character Creator gate HTTP surface."""

from __future__ import annotations

from fastapi import APIRouter

from .production_gate import evaluate_m42_character_creator_gate

router = APIRouter(tags=["m42-w43"])


@router.get("/m42-product/gate/wave43")
def wave43_gate():
    g = evaluate_m42_character_creator_gate()
    return {**g, "ok": bool(g.get("characterCreatorGo")), "passed": bool(g.get("characterCreatorGo"))}
