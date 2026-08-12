"""MAGI Command proposal parsing (UI helper mirrored in API tests)."""

from __future__ import annotations


def propose_from_command(text: str) -> dict | None:
    t = (text or "").strip().lower()
    if not t:
        return None
    if any(w in t for w in ("remove", "erase", "delete", "inpaint")) and any(
        w in t for w in ("object", "person", "people", "background", "thing")
    ):
        return {"operation": "image.object_remove", "requiresMask": True}
    if "outpaint" in t or "extend" in t:
        return {"operation": "image.outpaint", "requiresMask": False}
    if "upscale" in t:
        return {"operation": "image.upscale", "requiresMask": False}
    if "reference" in t:
        return {"operation": "image.reference_edit", "requiresMask": False}
    return {"operation": "image.inpaint", "requiresMask": True}


def test_command_remove_person():
    p = propose_from_command("Remove the person in the background.")
    assert p and p["operation"] == "image.object_remove"
    assert p["requiresMask"] is True


def test_command_upscale():
    p = propose_from_command("Upscale this still 2x")
    assert p and p["operation"] == "image.upscale"


def test_command_empty():
    assert propose_from_command("") is None
