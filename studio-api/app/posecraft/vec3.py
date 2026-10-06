"""Shared 3-vector helpers for PoseCraft scene v3."""

from __future__ import annotations


def vec3(x: float = 0.0, y: float = 0.0, z: float = 0.0) -> dict[str, float]:
    return {"x": float(x), "y": float(y), "z": float(z)}


def as_vec3(value: object, *, default_y: float = 0.0) -> dict[str, float]:
    if not isinstance(value, dict):
        return vec3(0.0, default_y, 0.0)
    return {
        "x": float(value.get("x") or 0.0),
        "y": float(value.get("y") if value.get("y") is not None else default_y),
        "z": float(value.get("z") or 0.0),
    }
