"""Provider-neutral generation reference packages for timeline images."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..db import Scene
from ..director_timeline import parse_director_timeline
from ..director_references.tags import ensure_tags
from ..feature_flags import feature_flags
from .errors import FeatureDisabled, TimelineItemNotFound
from .influence import INFLUENCE_TO_STRENGTH_PRESET
from .store import ReferenceStore


def _ic_lora_ready() -> bool:
    """Honest probe — never claim ready without the shared references probe."""
    try:
        from ..references.ic_lora_status import probe_ic_lora_ready

        result = probe_ic_lora_ready()
        if isinstance(result, dict):
            return bool(result.get("ready") or result.get("status") == "ready")
        return bool(result)
    except Exception:
        try:
            from ..capabilities.service import evaluate_capability

            # Best-effort: if registry marks ic_lora ready
            return False
        except Exception:
            return False


class ReferencePackageBuilder:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.store = ReferenceStore(db)

    def require_flag(self) -> None:
        if not feature_flags.timeline_references_v1:
            raise FeatureDisabled()

    def build(
        self, project_id: str, scene_id: str, item_id: str
    ) -> dict[str, Any]:
        self.require_flag()
        scene = self.db.get(Scene, scene_id)
        if not scene or scene.project_id != project_id:
            raise TimelineItemNotFound(item_id)
        tl = ensure_tags(
            parse_director_timeline(
                scene.director_json,
                fallback_duration=scene.duration_sec or 5.0,
                fallback_prompt=scene.prompt or "",
            )
        )
        clip = next((c for c in tl.image_clips if c.id == item_id), None)
        if not clip:
            raise TimelineItemNotFound(item_id)

        primary = {
            "timelineItemId": clip.id,
            "displayTag": clip.display_tag,
            "assetId": clip.asset_id,
            "role": "primary_frame",
        }

        ref_set = self.store.load_active_set(project_id, scene_id, item_id)
        bindings_out: list[dict[str, Any]] = []
        unsupported: list[dict[str, Any]] = []
        ic_ready = _ic_lora_ready()

        if ref_set and ref_set.version and ref_set.version.bindings:
            for b in ref_set.version.bindings:
                entry = {
                    "bindingId": b.id,
                    "referenceAssetId": b.reference_asset_id,
                    "role": b.role,
                    "influence": b.influence,
                    "source": b.source,
                    "label": b.label,
                    "notes": b.notes,
                    "sortOrder": b.sort_order,
                    "bibleEntityStableId": b.bible_entity_stable_id,
                    "bibleVersionId": b.bible_version_id,
                    "sourceTimelineItemId": b.source_timeline_item_id,
                }
                strength = INFLUENCE_TO_STRENGTH_PRESET.get(b.influence)
                if ic_ready and strength:
                    entry["icLoraStrengthPreset"] = strength
                elif not ic_ready:
                    unsupported.append(
                        {
                            "bindingId": b.id,
                            "role": b.role,
                            "reason": "references.ic_lora.ready is not available; influence kept semantic only",
                        }
                    )
                bindings_out.append(entry)

            reference_set: Optional[dict[str, Any]] = {
                "id": ref_set.id,
                "version": ref_set.active_version,
                "bindings": bindings_out,
            }
        else:
            reference_set = None

        support_status = "ready"
        if unsupported and reference_set is not None:
            support_status = "degraded"
        if reference_set is None:
            support_status = "ready"  # empty refs never block Run

        return {
            "primaryFrame": primary,
            "referenceSet": reference_set,
            "support": {
                "status": support_status,
                "unsupportedBindings": unsupported,
                "icLoraReady": ic_ready,
            },
        }

    def validate_package(
        self, project_id: str, scene_id: str, item_id: str, *, provider_hints: dict | None = None
    ) -> dict[str, Any]:
        """Capability/support check — not M2.5 pixel validation."""
        pkg = self.build(project_id, scene_id, item_id)
        support = pkg["support"]
        return {
            "ok": support["status"] in ("ready", "degraded"),
            "blocksRun": False,
            "package": pkg,
            "providerHints": provider_hints or {},
            "notes": [
                "References are optional; Run is never blocked by an empty or degraded reference set.",
                "IC-LoRA strength mapping applies only when references.ic_lora.ready is true.",
            ],
        }
