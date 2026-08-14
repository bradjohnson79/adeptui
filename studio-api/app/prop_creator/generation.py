"""Prop Creator candidate routing - User Control Law + generation-mode labels.

Checked + enabled sources x batchCount only. One still image per batch.
No all-family round-robin. No silent family swap.
"""

from __future__ import annotations

import random
from typing import Any

from ..scene_creator.generation import hosted_image_generation_available, list_local_generator_families

CandidatePlan = dict[str, Any]

_AUTO = {"", "auto"}
_FAMILY_ALIASES = {
    "qwen": "qwen2512",
    "qwen_image": "qwen2512",
    "qwen-image": "qwen2512",
    "qwen-image-2512": "qwen2512",
    "qwen_image_2512": "qwen2512",
    "krea": "krea2",
    "krea-2": "krea2",
    "krea_2": "krea2",
}


def _clamp_batch_count(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = 1
    return max(1, min(4, n))


def _normalize_local_family(family: str) -> str:
    fam = (family or "").strip().lower()
    if fam in _AUTO:
        return ""
    return _FAMILY_ALIASES.get(fam, fam)


def _is_auto_family(family: str) -> bool:
    return (family or "").strip().lower() in _AUTO


def discovered_hosted_image_models() -> list[dict[str, Any]]:
    """Image models already present in hosted-provider discovery. Not a Certified check."""
    try:
        from ..hosted_providers.model_store import models_for_modality

        return list(models_for_modality("image") or [])
    except Exception:
        return []


def api_image_models_configured() -> bool:
    """True when a certified hosted workflow exists OR discovery has an image model."""
    if hosted_image_generation_available():
        return True
    return bool(discovered_hosted_image_models())


def _family_catalog() -> list[dict[str, Any]]:
    return list(list_local_generator_families(has_reference=False) or [])


def _lookup_local_family(family_id: str, catalog: list[dict[str, Any]]) -> dict[str, Any]:
    raw = (family_id or "").strip()
    fam = _normalize_local_family(raw)
    for key in (raw, fam, raw.lower(), fam.lower() if fam else ""):
        if not key:
            continue
        for row in catalog:
            if str(row.get("id") or "") == key:
                return row
    return {
        "id": fam or raw,
        "label": fam or raw or "Local generator",
        "executable": False,
        "supportsReferences": False,
    }


def _normalize_generation_mode(
    raw: Any,
    *,
    supports_ref: bool,
    has_reference: bool,
) -> str:
    text = str(raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    if text in {"reference_conditioned", "referenceconditioned", "ref", "img2img"}:
        if supports_ref and has_reference:
            return "reference_conditioned"
        return "description_guided"
    if text in {"description_guided", "descriptionguided", "text", "txt2img", "profile_guided"}:
        return "description_guided"
    if has_reference and supports_ref:
        return "reference_conditioned"
    return "description_guided"


def _mode_label(mode: str) -> str:
    return "Reference Conditioned" if mode == "reference_conditioned" else "Description Guided"


def _hosted_family_for_model(model_id: str) -> str:
    if not model_id:
        return ""
    try:
        from ..production_control.runtime_map import image_family_for_dock_model

        fam = image_family_for_dock_model(model_id)
        if fam:
            return str(fam)
    except Exception:
        pass
    mid = str(model_id).lower()
    if "nano-banana" in mid or mid.startswith("imagen"):
        return "imagen"
    if "flux" in mid:
        return "flux"
    if "krea" in mid:
        return "krea2"
    return mid.split("-")[0] if mid else ""


def _local_plan(
    *,
    family: str,
    catalog: list[dict[str, Any]],
    has_reference: bool,
    generation_mode: str = "",
    index: int,
    seed: int,
    batch_index: int,
    batch_of: int,
) -> CandidatePlan:
    meta = _lookup_local_family(family, catalog)
    fam = str(meta.get("id") or family)
    supports_ref = bool(meta.get("supportsReferences"))
    mode = _normalize_generation_mode(
        generation_mode, supports_ref=supports_ref, has_reference=has_reference
    )
    label = str(meta.get("label") or fam)
    return {
        "source": "local",
        "family": fam,
        "model": fam,
        "model_id": fam,
        "label": label,
        "supports_references": supports_ref,
        "conditioning": mode,
        "index": index,
        "seed": seed,
        "batch_index": batch_index,
        "batch_of": batch_of,
        "workflow_key": f"{fam}.ref_edit" if mode == "reference_conditioned" else f"{fam}.txt2img",
        "provenance_label": f"LOCAL - {label} - {_mode_label(mode)}",
        "provider_id": "",
        "hosted_model_id": None,
        "style_engine": False,
    }


def _api_plan(
    *,
    model: str,
    provider_id: str = "",
    model_id: str = "",
    has_reference: bool = False,
    generation_mode: str = "",
    index: int = 0,
    seed: int = 0,
    batch_index: int = 1,
    batch_of: int = 1,
) -> CandidatePlan:
    mid = (model_id or model).strip()
    label = (model or mid or "Cloud generator").strip()
    explicit = str(generation_mode or "").strip().lower().replace(" ", "_")
    if has_reference and "reference" in explicit:
        mode = "reference_conditioned"
    else:
        mode = "description_guided"
    family = _hosted_family_for_model(mid) or "hosted"
    return {
        "source": "api",
        "family": family,
        "model": label,
        "model_id": mid or label,
        "label": label,
        "supports_references": mode == "reference_conditioned",
        "conditioning": mode,
        "index": index,
        "seed": seed,
        "batch_index": batch_index,
        "batch_of": batch_of,
        "workflow_key": "",
        "provenance_label": f"API - {label} - {_mode_label(mode)}",
        "provider_id": (provider_id or "").strip(),
        "hosted_model_id": mid or label,
        "style_engine": False,
    }


def _item_local_id(item: dict[str, Any]) -> str:
    return str(
        item.get("modelId") or item.get("family") or item.get("model") or item.get("selected") or ""
    ).strip()


def _item_api_ids(item: dict[str, Any]) -> tuple[str, str, str]:
    provider_id = str(item.get("providerId") or "").strip()
    model_id = str(item.get("modelId") or "").strip()
    model = str(item.get("model") or item.get("selected") or "").strip() or model_id
    return model, provider_id, model_id or model


def parse_style_engine(generator_sources: dict[str, Any] | None) -> dict[str, Any]:
    """Style Engine is post-process only. Never expanded into a candidate batch."""
    if not generator_sources:
        return {"enabled": False, "model_id": ""}
    se = generator_sources.get("styleEngine")
    if isinstance(se, dict):
        return {
            "enabled": bool(se.get("enabled")),
            "model_id": str(se.get("modelId") or se.get("family") or se.get("model") or "").strip(),
        }
    return {
        "enabled": bool(generator_sources.get("stage2Enabled")),
        "model_id": str(generator_sources.get("stage2Family") or "").strip(),
    }


def persist_generator_selection(
    *,
    local_enabled: bool,
    api_enabled: bool,
    local_family: str = "",
    api_model: str = "",
    api_provider: str = "",
    generator_sources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Scalar + list persist shape for PropEntity.generator."""
    style = parse_style_engine(generator_sources)
    local_models: list[dict[str, Any]] = []
    api_models: list[dict[str, Any]] = []
    if generator_sources:
        local = generator_sources.get("local")
        api = generator_sources.get("api")
        if isinstance(local, list):
            local_models = [item for item in local if isinstance(item, dict)]
            enabled_local = [i for i in local_models if i.get("enabled") and not _is_auto_family(_item_local_id(i))]
            if enabled_local:
                local_family = _item_local_id(enabled_local[0]) or local_family
            local_enabled = True
        elif local is None and "local" in generator_sources:
            local_enabled = False
        if isinstance(api, list):
            api_models = [item for item in api if isinstance(item, dict)]
            enabled_api = [i for i in api_models if i.get("enabled") and _item_api_ids(i)[2]]
            if enabled_api:
                _model, provider_id, model_id = _item_api_ids(enabled_api[0])
                api_model = model_id or api_model
                api_provider = provider_id or api_provider
            api_enabled = True
        elif api is None and "api" in generator_sources:
            api_enabled = False
        if "localEnabled" in generator_sources:
            local_enabled = bool(generator_sources.get("localEnabled"))
        if "apiEnabled" in generator_sources:
            api_enabled = bool(generator_sources.get("apiEnabled"))
    return {
        "local_enabled": local_enabled,
        "api_enabled": api_enabled,
        "local_family": local_family,
        "api_provider": api_provider,
        "api_model": api_model,
        "local_models": local_models,
        "api_models": api_models,
        "style_engine_enabled": style["enabled"],
        "style_engine_model_id": style["model_id"],
        "generator_sources": generator_sources,
    }


def build_prop_candidate_plans(
    *,
    local_enabled: bool = True,
    api_enabled: bool = False,
    local_family: str = "",
    api_model: str = "",
    has_reference: bool = False,
    candidate_count: int = 4,
    seed: int | None = None,
    generator_sources: dict[str, Any] | None = None,
) -> list[CandidatePlan]:
    """Build one plan per (enabled source x batch). Unchecked source = zero jobs.

    Do not auto-disable txt2img families when a reference exists.
    Label each plan Reference Conditioned or Description Guided.
    Never round-robin the rest of the local registry.
    """
    rng = random.Random(seed if seed is not None else random.randint(1, 2_147_483_647))
    if generator_sources is not None:
        plans = _expand_generator_sources(
            generator_sources,
            has_reference=has_reference,
            rng=rng,
            fallback_candidate_count=candidate_count,
        )
    else:
        plans = _expand_legacy_scalars(
            local_enabled=local_enabled,
            api_enabled=api_enabled,
            local_family=local_family,
            api_model=api_model,
            has_reference=has_reference,
            candidate_count=candidate_count,
            rng=rng,
        )
    if not plans:
        raise ValueError("Enable a Local or API generator to create prop images.")
    return plans


def _next_seed(rng: random.Random) -> int:
    return rng.randint(1, 2_147_483_647)


def _expand_legacy_scalars(
    *,
    local_enabled: bool,
    api_enabled: bool,
    local_family: str,
    api_model: str,
    has_reference: bool,
    candidate_count: int,
    rng: random.Random,
) -> list[CandidatePlan]:
    """Old UI: one local family dropdown + one cloud model. No all-family fanout."""
    if not local_enabled and not api_enabled:
        return []
    count = max(1, min(int(candidate_count or 4), 4))
    catalog = _family_catalog()
    plans: list[CandidatePlan] = []
    index = 0
    if local_enabled:
        selected = _normalize_local_family(local_family) or (local_family or "").strip()
        if selected and not _is_auto_family(selected):
            family = selected
        else:
            ready = next((m for m in catalog if m.get("executable")), None)
            if ready is None:
                raise ValueError(
                    "No local image generator is ready. Open Source Manager to install a Certified generator."
                )
            family = str(ready.get("id") or "")
        for b in range(count):
            plans.append(
                _local_plan(
                    family=family,
                    catalog=catalog,
                    has_reference=has_reference,
                    index=index,
                    seed=_next_seed(rng),
                    batch_index=b + 1,
                    batch_of=count,
                )
            )
            index += 1
    if api_enabled:
        model = (api_model or "").strip()
        if model:
            for b in range(count):
                plans.append(
                    _api_plan(
                        model=model,
                        model_id=model,
                        has_reference=has_reference,
                        index=index,
                        seed=_next_seed(rng),
                        batch_index=b + 1,
                        batch_of=count,
                    )
                )
                index += 1
    return plans


def _expand_generator_sources(
    generator_sources: dict[str, Any],
    *,
    has_reference: bool,
    rng: random.Random,
    fallback_candidate_count: int = 4,
) -> list[CandidatePlan]:
    local = generator_sources.get("local")
    api = generator_sources.get("api")
    if "localEnabled" in generator_sources and not generator_sources.get("localEnabled"):
        local = None
    if "apiEnabled" in generator_sources and not generator_sources.get("apiEnabled"):
        api = None

    catalog = _family_catalog()
    plans: list[CandidatePlan] = []
    index = 0

    if isinstance(local, list):
        enabled_local = [item for item in local if isinstance(item, dict) and bool(item.get("enabled"))]
        explicit = [item for item in enabled_local if not _is_auto_family(_item_local_id(item))]
        auto = [item for item in enabled_local if _is_auto_family(_item_local_id(item))]
        if explicit:
            for item in explicit:
                n = _clamp_batch_count(item.get("batchCount") or 1)
                fam = _item_local_id(item)
                mode = str(item.get("generationMode") or "")
                for b in range(n):
                    plans.append(
                        _local_plan(
                            family=fam,
                            catalog=catalog,
                            has_reference=has_reference,
                            generation_mode=mode,
                            index=index,
                            seed=_next_seed(rng),
                            batch_index=b + 1,
                            batch_of=n,
                        )
                    )
                    index += 1
        elif auto:
            n = _clamp_batch_count(auto[0].get("batchCount") or 1)
            ready = next((m for m in catalog if m.get("executable")), None)
            if ready is None:
                raise ValueError(
                    "No local image generator is ready. Open Source Manager to install a Certified generator."
                )
            mode = str(auto[0].get("generationMode") or "")
            for b in range(n):
                plans.append(
                    _local_plan(
                        family=str(ready.get("id") or ""),
                        catalog=catalog,
                        has_reference=has_reference,
                        generation_mode=mode,
                        index=index,
                        seed=_next_seed(rng),
                        batch_index=b + 1,
                        batch_of=n,
                    )
                )
                index += 1
    elif isinstance(local, dict):
        fam = _item_local_id(local)
        n = _clamp_batch_count(local.get("batchCount") or fallback_candidate_count)
        if fam and not _is_auto_family(fam):
            family = fam
        else:
            ready = next((m for m in catalog if m.get("executable")), None)
            if ready is None:
                raise ValueError(
                    "No local image generator is ready. Open Source Manager to install a Certified generator."
                )
            family = str(ready.get("id") or "")
        mode = str(local.get("generationMode") or "")
        for b in range(n):
            plans.append(
                _local_plan(
                    family=family,
                    catalog=catalog,
                    has_reference=has_reference,
                    generation_mode=mode,
                    index=index,
                    seed=_next_seed(rng),
                    batch_index=b + 1,
                    batch_of=n,
                )
            )
            index += 1

    if isinstance(api, list):
        enabled_api = []
        for item in api:
            if not isinstance(item, dict) or not item.get("enabled"):
                continue
            model, provider_id, model_id = _item_api_ids(item)
            if not (model or model_id):
                continue
            enabled_api.append(item)
        for item in enabled_api:
            n = _clamp_batch_count(item.get("batchCount") or 1)
            model, provider_id, model_id = _item_api_ids(item)
            mode = str(item.get("generationMode") or "")
            for b in range(n):
                plans.append(
                    _api_plan(
                        model=model,
                        provider_id=provider_id,
                        model_id=model_id,
                        has_reference=has_reference,
                        generation_mode=mode,
                        index=index,
                        seed=_next_seed(rng),
                        batch_index=b + 1,
                        batch_of=n,
                    )
                )
                index += 1
    elif isinstance(api, dict):
        model, provider_id, model_id = _item_api_ids(api)
        if model or model_id:
            n = _clamp_batch_count(api.get("batchCount") or fallback_candidate_count)
            mode = str(api.get("generationMode") or "")
            for b in range(n):
                plans.append(
                    _api_plan(
                        model=model,
                        provider_id=provider_id,
                        model_id=model_id,
                        has_reference=has_reference,
                        generation_mode=mode,
                        index=index,
                        seed=_next_seed(rng),
                        batch_index=b + 1,
                        batch_of=n,
                    )
                )
                index += 1

    return plans
