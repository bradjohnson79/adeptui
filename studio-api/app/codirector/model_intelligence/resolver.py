"""Resolve active packs and version compatibility."""

from __future__ import annotations

from typing import Any, Optional

from .loader import PackLoadError, discover_packs, load_pack_dir, PACKS_DIR
from .registry import BINDINGS, binding_for_engine, binding_for_model
from .schemas import PackStatus


class ResolveError(ValueError):
    pass


def resolve_pack(
    *,
    model_id: Optional[str] = None,
    engine_id: Optional[str] = None,
    runtime_model_version: Optional[str] = None,
    allow_non_active: bool = False,
) -> dict[str, Any]:
    binding = None
    if model_id:
        binding = binding_for_model(model_id)
    elif engine_id:
        binding = binding_for_engine(engine_id)
    if binding is None:
        raise ResolveError("MODEL_KNOWLEDGE_UNAVAILABLE: unknown model/engine")

    packs = discover_packs()
    pack = packs.get(binding.modelId)
    if pack is None:
        raise ResolveError(
            f"MODEL_KNOWLEDGE_UNAVAILABLE: no knowledge pack for {binding.modelId}"
        )

    manifest = pack["manifest"]
    warnings: list[str] = []
    confidence_scale = 1.0

    if manifest.status == PackStatus.QUARANTINED:
        raise ResolveError(
            f"MODEL_KNOWLEDGE_UNAVAILABLE: pack {binding.modelId} is QUARANTINED"
        )
    if not allow_non_active and manifest.status not in (
        PackStatus.ACTIVE,
        PackStatus.VERIFIED,
    ):
        raise ResolveError(
            f"MODEL_KNOWLEDGE_UNAVAILABLE: pack {binding.modelId} status={manifest.status.value}"
        )

    if runtime_model_version and runtime_model_version != manifest.modelVersion:
        warnings.append(
            f"Runtime model version {runtime_model_version!r} does not match "
            f"knowledge pack version {manifest.modelVersion!r}; unsafe rules withheld."
        )
        confidence_scale = 0.4
        pack = dict(pack)
        # Withhold parameter mutation rules on mismatch
        params = dict(pack.get("parameters") or {})
        params["_versionMismatch"] = True
        params["unsafeRulesWithheld"] = True
        pack["parameters"] = params

    pack = dict(pack)
    pack["binding"] = binding
    pack["resolveWarnings"] = warnings
    pack["confidenceScale"] = confidence_scale
    return pack


def try_resolve(**kwargs: Any) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    try:
        return resolve_pack(**kwargs), None
    except (ResolveError, PackLoadError) as exc:
        return None, str(exc)
