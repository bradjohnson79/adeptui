"""World-state index for nearest-state lookup and reference management.

Scoped to project/scene/shot/character/environment/asset lineage.
Uses simple local JSON storage — no heavyweight vector database.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .contracts import EmbeddingReference, WorldReferenceAnchor
from .paths import world_index_path


class WorldStateIndex:
    """Local world-state index for project-scoped reference management."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        path = world_index_path()
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {"anchors": [], "entries": []}
        return {"anchors": [], "entries": []}

    def _save(self) -> None:
        path = world_index_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    # ── Anchors ──────────────────────────────────────────────────────────

    def get_anchors(
        self,
        project_id: Optional[str] = None,
        scene_id: Optional[str] = None,
        active_only: bool = True,
    ) -> list[WorldReferenceAnchor]:
        """Get approved world anchors, optionally filtered."""
        anchors = []
        for raw in self._data.get("anchors", []):
            if active_only and not raw.get("isActive", True):
                continue
            if project_id and raw.get("projectId") != project_id:
                continue
            if scene_id and raw.get("sceneId") != scene_id:
                continue
            anchors.append(WorldReferenceAnchor.model_validate(raw))
        return anchors

    def add_anchor(self, anchor: WorldReferenceAnchor) -> None:
        """Add or update a world reference anchor."""
        existing = [a for a in self._data["anchors"] if a.get("anchorId") == anchor.anchorId]
        if existing:
            existing[0].update(anchor.model_dump())
        else:
            self._data["anchors"].append(anchor.model_dump())
        self._save()

    def deactivate_anchor(self, anchor_id: str) -> bool:
        """Mark an anchor as inactive (soft delete)."""
        for raw in self._data["anchors"]:
            if raw.get("anchorId") == anchor_id:
                raw["isActive"] = False
                self._save()
                return True
        return False

    # ── Entry management ─────────────────────────────────────────────────

    def add_entry(self, entry: dict[str, Any]) -> str:
        """Add a world state entry with embedding reference."""
        entry_id = entry.get("entryId") or f"wse_{len(self._data['entries']):08x}"
        entry["entryId"] = entry_id
        self._data["entries"].append(entry)
        self._save()
        return entry_id

    def find_nearest(
        self,
        embedding: list[float],
        project_id: Optional[str] = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Find nearest world state entries by cosine similarity.

        Simple linear scan. For small indices this is fast enough;
        if scaling becomes an issue, upgrade to a vector index.
        """
        import math

        def _cosine_sim(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(y * y for y in b))
            if na == 0 or nb == 0:
                return 0.0
            return dot / (na * nb)

        scored: list[tuple[float, dict]] = []
        for entry in self._data.get("entries", []):
            emb = entry.get("embedding")
            if not emb or len(emb) != len(embedding):
                continue
            if project_id and entry.get("projectId") != project_id:
                continue
            sim = _cosine_sim(embedding, emb)
            scored.append((sim, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for sim, entry in scored[:top_k]]

    def get_entries_for_project(self, project_id: str) -> list[dict]:
        """Get all entries for a project."""
        return [e for e in self._data.get("entries", []) if e.get("projectId") == project_id]

    def clear_project(self, project_id: str) -> int:
        """Remove all entries and anchors for a project. Returns count."""
        before = len(self._data["entries"]) + len(self._data["anchors"])
        self._data["entries"] = [
            e for e in self._data["entries"] if e.get("projectId") != project_id
        ]
        self._data["anchors"] = [
            a for a in self._data["anchors"] if a.get("projectId") != project_id
        ]
        self._save()
        return before - len(self._data["entries"]) - len(self._data["anchors"])

    @property
    def entry_count(self) -> int:
        return len(self._data.get("entries", []))

    @property
    def anchor_count(self) -> int:
        return len(self._data.get("anchors", []))
