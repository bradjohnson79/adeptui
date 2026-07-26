"""Scene audio plan propose/validate helpers (validate-before-execute)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

PlacementKind = Literal["dialogue", "sfx", "ambience", "music"]


@dataclass
class AudioPlacement:
    kind: PlacementKind
    prompt: str
    startSec: float = 0.0
    durationSec: float = 2.0
    registryId: str | None = None
    assetId: str | None = None
    volume: float = 1.0
    ducking: bool = False
    syncEvent: str | None = None


@dataclass
class AudioPlan:
    projectId: str
    sceneId: str | None = None
    placements: list[AudioPlacement] = field(default_factory=list)
    notes: str = ""
    validated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "projectId": self.projectId,
            "sceneId": self.sceneId,
            "placements": [asdict(p) for p in self.placements],
            "notes": self.notes,
            "validated": self.validated,
        }


_KIND_TO_CAP = {
    "dialogue": "audio.dialogue.generate",
    "sfx": "audio.sfx.generate",
    "ambience": "audio.sfx.generate",
    "music": "audio.music.generate",
}


def propose_audio_plan(
    *,
    project_id: str,
    scene_id: str | None = None,
    dialogue: list[dict[str, Any]] | None = None,
    sfx: list[dict[str, Any]] | None = None,
    ambience: list[dict[str, Any]] | None = None,
    music: list[dict[str, Any]] | None = None,
    notes: str = "",
) -> AudioPlan:
    """Build an AudioPlan from placement dicts (propose only — no side effects)."""
    placements: list[AudioPlacement] = []
    for kind, items in (
        ("dialogue", dialogue or []),
        ("sfx", sfx or []),
        ("ambience", ambience or []),
        ("music", music or []),
    ):
        for item in items:
            placements.append(
                AudioPlacement(
                    kind=kind,  # type: ignore[arg-type]
                    prompt=str(item.get("prompt") or ""),
                    startSec=float(item.get("startSec") or 0.0),
                    durationSec=float(item.get("durationSec") or 2.0),
                    registryId=item.get("registryId") or item.get("providerKey"),
                    assetId=item.get("assetId"),
                    volume=float(item.get("volume") or 1.0),
                    ducking=bool(item.get("ducking") or False),
                    syncEvent=item.get("syncEvent"),
                )
            )
    return AudioPlan(
        projectId=project_id,
        sceneId=scene_id,
        placements=placements,
        notes=notes,
        validated=False,
    )


def validate_audio_plan(plan: AudioPlan) -> dict[str, Any]:
    """Validate-before-execute: structure, kinds, timing, optional registry auth."""
    from .execution_lock import is_execution_authorized

    errors: list[str] = []
    warnings: list[str] = []
    if not plan.projectId:
        errors.append("projectId is required")
    if not plan.placements:
        warnings.append("plan has no placements")
    for i, p in enumerate(plan.placements):
        prefix = f"placements[{i}]"
        if p.kind not in _KIND_TO_CAP:
            errors.append(f"{prefix}: unsupported kind {p.kind!r}")
        if not (p.prompt or "").strip() and not p.assetId:
            errors.append(f"{prefix}: prompt or assetId required")
        if p.durationSec <= 0:
            errors.append(f"{prefix}: durationSec must be > 0")
        if p.startSec < 0:
            errors.append(f"{prefix}: startSec must be >= 0")
        if p.registryId and not is_execution_authorized(p.registryId):
            errors.append(
                f"{prefix}: registryId {p.registryId!r} is not execution-authorized"
            )
    ok = not errors
    plan.validated = ok
    return {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "plan": plan.to_dict(),
        "capabilityHints": {
            i: _KIND_TO_CAP.get(p.kind) for i, p in enumerate(plan.placements)
        },
    }
