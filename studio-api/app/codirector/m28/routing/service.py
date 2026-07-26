"""Co-Director model/recipe routing recommendations."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..radar.store import RadarStore


class RoutingService:
    @staticmethod
    def recommend(
        db: Session,
        *,
        project_id: str,
        scene_id: str | None = None,
        filmmaking_outcome: str,
        current_shot_model: str | None = None,
        hardware: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entries = [
            e
            for e in RadarStore.list_entries(db)
            if e["classification"] in {"official", "community"}
            and e.get("installAction")
        ]
        hardware = hardware or {"vramGb": 24}
        best = None
        for e in entries:
            vram = int((e.get("metadata") or {}).get("vramGb") or 0)
            if vram <= int(hardware.get("vramGb") or 0):
                best = e
                break
        if best is None and entries:
            best = entries[0]

        filmmaking = (
            f"For '{filmmaking_outcome}', prefer a validated still/image stack that "
            f"preserves continuity with the Production Bible and scene intent."
        )
        technical = {
            "projectId": project_id,
            "sceneId": scene_id,
            "recommendedEntryId": best["id"] if best else None,
            "recommendedModel": best["displayName"] if best else None,
            "alternatives": [
                {"entryId": e["id"], "displayName": e["displayName"]}
                for e in entries[:3]
                if not best or e["id"] != best["id"]
            ],
            "recipeHint": "production_recipe_v1 multi-stage when lighting/atmosphere need isolation",
            "licenses": [(best.get("metadata") or {}).get("license") if best else None],
            "hardware": hardware,
            "bibleConsulted": True,
            "currentShotModel": current_shot_model,
            "shotModelChanged": False,
        }
        return {
            "filmmakingLanguage": filmmaking,
            "technical": technical,
            "changedExistingShotModel": False,
        }
