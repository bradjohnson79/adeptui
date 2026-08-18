"""Role-grouped image reference inputs + LoRA spec for image generation requests.

Krea 2 Phase C contract carriers. An ``AssetRef`` is the canonical "attach an
asset as conditioning input" record: ``assetId`` + semantic ``role``. Roles use
the Adept vocabulary (``style`` / ``identity`` / ``environment`` / ``moodboard``)
and bridge onto the existing reference systems:

- ``image_product/references.py`` UI refs (``{assetId, role}`` dicts) normalize
  into ``AssetRef`` via :func:`normalize_asset_ref`.
- ``image_pipeline/contracts.py`` ``ImageReferenceAssignment.semanticRole`` maps
  through :data:`REFERENCE_ROLE_ALIASES`.
- ``environment_reference_sheet`` ERS records bridge via
  :func:`asset_refs_from_ers_sheet`.

ERS Semantic Role Law (milestone requirement): an asset whose role is
``environment`` is NEVER reassigned to another role by normalization, grouping,
or graph building. Krea 2's open ComfyUI path exposes only a generic
reference-image interface, so the role is carried in Adept metadata (and node
labels) pending provider-native role support — see
``docs/release-gate/krea2/KREA2_IMAGE_PIPELINE_AUDIT.md`` and
``docs/architecture/environment-reference-sheet/ERS_CONTRACTS.md``.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

#: Canonical conditioning roles for the image request contract.
REFERENCE_ROLES: tuple[str, ...] = ("style", "identity", "environment", "moodboard")

#: Alias map from the wider Adept reference vocabulary
#: (``image_runtime/reference_assets.py`` REFERENCE_TYPES, director_references
#: roles, image_pipeline semanticRoles) onto the canonical conditioning roles.
#: NOTE: "environment" (and its location/env spellings) only ever map TO
#: "environment" — nothing maps environment away from itself (ERS law).
REFERENCE_ROLE_ALIASES: dict[str, str] = {
    "style": "style",
    "palette": "style",
    "lighting": "style",
    "mood": "moodboard",
    "moodboard": "moodboard",
    "character": "identity",
    "character_identity": "identity",
    "identity": "identity",
    "face": "identity",
    "wardrobe": "identity",
    "costume": "identity",
    "clothing": "identity",
    "environment": "environment",
    "env": "environment",
    "location": "environment",
    "architecture": "environment",
}

DEFAULT_LORA_STRENGTH = 0.8


def normalize_role(role: str | None) -> str | None:
    """Map a free-form reference role onto the canonical conditioning roles.

    Returns ``None`` when no role was supplied (the grouping bucket then
    decides). Unknown roles pass through unchanged — normalization never
    silently reassigns a role, and ``environment`` is alias-stable (ERS law).
    """
    if role is None:
        return None
    key = str(role).strip().lower()
    if not key:
        return None
    return REFERENCE_ROLE_ALIASES.get(key, key)


@dataclass(frozen=True)
class AssetRef:
    """One reference asset + its semantic conditioning role."""

    assetId: str
    role: str | None = None
    # ComfyUI-side image name (post-upload) for LoadImage; falls back to assetId.
    image: str | None = None
    weight: float = 1.0
    displayName: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "assetId": self.assetId,
            "role": self.role,
            "image": self.image,
            "weight": self.weight,
            "displayName": self.displayName,
        }


def normalize_asset_ref(item: Any, *, bucket_role: str | None = None) -> AssetRef | None:
    """Normalize a UI/pipeline ref (dict, str id, AssetRef) into an AssetRef.

    ``bucket_role`` is the semantic role of the list the ref arrived in
    (e.g. ``environmentReferences`` → "environment") and fills the role only
    when the ref did not declare one. A declared ``environment`` role is never
    overridden (ERS Semantic Role Law).
    """
    if item is None:
        return None
    if isinstance(item, AssetRef):
        role = normalize_role(item.role)
        if role is None:
            role = bucket_role
        elif role == "environment":
            pass  # ERS law: never reassign an environment role
        return AssetRef(
            assetId=item.assetId,
            role=role,
            image=item.image,
            weight=item.weight,
            displayName=item.displayName,
        )
    if isinstance(item, str):
        asset_id = item.strip()
        if not asset_id:
            return None
        return AssetRef(assetId=asset_id, role=bucket_role)
    if isinstance(item, Mapping):
        asset_id = str(
            item.get("assetId") or item.get("asset_id") or item.get("referenceId") or ""
        ).strip()
        if not asset_id:
            return None
        role = normalize_role(item.get("role") or item.get("semanticRole"))
        if role is None:
            role = bucket_role
        # ERS law: a declared environment role wins over the bucket.
        weight = item.get("weight")
        return AssetRef(
            assetId=asset_id,
            role=role,
            image=item.get("image") or item.get("imageName"),
            weight=float(weight) if weight is not None else 1.0,
            displayName=str(item.get("displayName") or item.get("label") or ""),
        )
    return None


@dataclass(frozen=True)
class RoleGroupedReferences:
    """Reference inputs grouped by semantic role (distinct fields per UI bucket).

    ``style`` and ``moodboard`` stay distinct so the UI can tell moodboards
    apart from explicit style references even though both condition "look".
    """

    style: tuple[AssetRef, ...] = ()
    identity: tuple[AssetRef, ...] = ()
    environment: tuple[AssetRef, ...] = ()
    moodboard: tuple[AssetRef, ...] = ()

    @classmethod
    def from_inputs(
        cls,
        *,
        styleReferences: Iterable[Any] | None = None,
        characterReferences: Iterable[Any] | None = None,
        environmentReferences: Iterable[Any] | None = None,
        moodboardReferences: Iterable[Any] | None = None,
    ) -> "RoleGroupedReferences":
        def _group(items: Iterable[Any] | None, bucket_role: str) -> tuple[AssetRef, ...]:
            out: list[AssetRef] = []
            for item in items or ():
                ref = normalize_asset_ref(item, bucket_role=bucket_role)
                if ref is not None:
                    out.append(ref)
            return tuple(out)

        return cls(
            style=_group(styleReferences, "style"),
            identity=_group(characterReferences, "identity"),
            environment=_group(environmentReferences, "environment"),
            moodboard=_group(moodboardReferences, "moodboard"),
        )

    def is_empty(self) -> bool:
        return not (self.style or self.identity or self.environment or self.moodboard)

    def flattened(self) -> list[AssetRef]:
        """All refs in a stable conditioning order, roles intact."""
        return [*self.style, *self.moodboard, *self.identity, *self.environment]

    def role_metadata(self) -> dict[str, Any]:
        """Provenance carrier for the semantic roles (ERS law evidence).

        Krea 2's open ComfyUI path consumes references through a generic
        reference-image interface, so the semantic role lives in this Adept
        metadata (and per-node labels) pending provider-native role support.
        """
        refs = []
        for ref in self.flattened():
            refs.append(
                {
                    "assetId": ref.assetId,
                    "role": ref.role,
                    "weight": ref.weight,
                    "conditioning": "generic_reference_interface",
                }
            )
        return {
            "references": refs,
            "rolePreservation": {
                "law": "ERS_SEMANTIC_ROLE",
                "environmentRolesPreserved": all(
                    r.role == "environment" for r in self.environment
                ),
                "note": (
                    "ERS assets are preserved as ENVIRONMENT conditioning; the "
                    "semantic role is carried in Adept metadata pending "
                    "provider-native role support."
                ),
            },
        }


def asset_refs_from_ers_sheet(sheet: Any) -> list[AssetRef]:
    """Bridge an Environment Reference Sheet into environment AssetRefs.

    Duck-typed against ``environment_reference_sheet.contracts
    .EnvironmentReferenceSheet``: every directional view with an approved asset
    becomes an ``environment``-role ref. Roles are never reassigned (ERS law).
    """
    refs: list[AssetRef] = []
    name = str(getattr(sheet, "name", "") or "ERS")
    for view in getattr(sheet, "directionalViews", None) or []:
        asset_id = getattr(view, "approvedAssetId", None)
        if not asset_id:
            continue
        direction = str(getattr(view, "direction", "") or "view")
        refs.append(
            AssetRef(
                assetId=str(asset_id),
                role="environment",
                displayName=f"{name} — {direction}",
            )
        )
    return refs


@dataclass(frozen=True)
class LoraSpec:
    """LoRA selection for the Krea 2 builders (train on RAW, run on Turbo)."""

    loraId: str
    strength: float = DEFAULT_LORA_STRENGTH
    # ComfyUI loras-dir-relative name emitted into LoraLoader (subdirectories
    # use os separators, matching ComfyUI's listing behavior on Windows).
    resolvedName: str | None = None
    # Absolute on-disk path when the file was found; None = unresolved (the
    # builder still emits the node so ComfyUI surfaces the honest error).
    resolvedPath: str | None = None
    resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def wire_lora_nodes(
    graph: dict[str, Any],
    *,
    lora: 'LoraSpec | None' = None,
    model_ref: list[Any],
    clip_ref: list[Any] | None = None,
    node_id: str = "20",
) -> tuple[list[Any], list[Any] | None]:
    """Append a LoRA loader node to a graph; return the new model/clip refs.

    Uses full ``LoraLoader`` when a CLIP ref is available (SDXL-style
    checkpoints expose MODEL+CLIP), ``LoraLoaderModelOnly`` otherwise
    (FLUX / Z-Image / Qwen transformer paths load CLIP separately).
    ``lora`` is a ``LoraSpec`` with ``resolvedName``/``loraId`` + ``strength``.
    """
    if lora is None:
        return model_ref, clip_ref
    strength = float(getattr(lora, "strength", 0.8) or 0.8)
    name = str(getattr(lora, "resolvedName", None) or getattr(lora, "loraId", "") or "").strip()
    if not name:
        return model_ref, clip_ref
    if clip_ref is not None:
        graph[node_id] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": list(model_ref),
                "clip": list(clip_ref),
                "lora_name": name,
                "strength_model": strength,
                "strength_clip": strength,
            },
            "_meta": {"title": f"LoRA — {name}", "adeptLora": True},
        }
        return [node_id, 0], [node_id, 1]
    graph[node_id] = {
        "class_type": "LoraLoaderModelOnly",
        "inputs": {
            "model": list(model_ref),
            "lora_name": name,
            "strength_model": strength,
        },
        "_meta": {"title": f"LoRA — {name}", "adeptLora": True},
    }
    return [node_id, 0], None


def krea2_lora_search_roots(settings: Any) -> list[Path]:
    """LoRA search roots: configured Krea 2 / Adept model roots first."""
    roots: list[Path] = []
    krea_root = getattr(settings, "krea2_model_root", None)
    if krea_root:
        roots.append(Path(str(krea_root)) / "loras")
        roots.append(Path(str(krea_root)))
    adept_root = (os.environ.get("ADEPT_MODEL_ROOT") or "").strip()
    if adept_root:
        roots.append(Path(adept_root) / "loras")
    comfy_models = getattr(settings, "comfy_models_dir", None)
    if comfy_models:
        roots.append(Path(comfy_models) / "loras")
    data_dir = getattr(settings, "data_dir", None)
    if data_dir:
        roots.append(Path(data_dir) / "models" / "loras")
    return roots


def resolve_krea2_lora(
    lora_id: str | None,
    *,
    strength: float = DEFAULT_LORA_STRENGTH,
    settings: Any = None,
) -> LoraSpec | None:
    """Resolve a LoRA id/filename against the Krea 2 / Adept model storage roots.

    Never invents a path: when the file is not found the spec is returned
    unresolved so the queue-time ComfyUI error stays honest.
    """
    if not lora_id:
        return None
    lid = str(lora_id).strip()
    if not lid:
        return None
    candidates = [lid] if lid.lower().endswith(".safetensors") else [f"{lid}.safetensors", lid]
    if settings is not None:
        for root in krea2_lora_search_roots(settings):
            for name in candidates:
                direct = root / name
                if direct.is_file() and direct.stat().st_size > 0:
                    return LoraSpec(
                        loraId=lid,
                        strength=float(strength),
                        resolvedName=str(direct.relative_to(root)),
                        resolvedPath=str(direct),
                        resolved=True,
                    )
    return LoraSpec(loraId=lid, strength=float(strength), resolvedName=candidates[0])
