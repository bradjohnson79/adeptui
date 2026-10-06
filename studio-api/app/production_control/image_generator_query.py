"""Canonical image-generator query for Co-Director AUTO.

Production Control owns inventory. This module queries list_models("image")
and ranks compatible executable generators. It is not a second catalog.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Sequence

from .contracts import ModelDescriptor
from .model_registry import is_ordinary_picker_hidden, list_models
from .runtime_map import image_family_for_dock_model

logger = logging.getLogger(__name__)

ImageTask = Literal["text_to_image", "reference", "edit", "inpaint"]

_TASK_SUPPORTS: dict[str, tuple[str, ...]] = {
    "text_to_image": ("text_to_image",),
    "reference": ("reference_conditioning", "identity_reference"),
    "edit": ("edit",),
    "inpaint": ("inpaint",),
}

_LABEL_RANK: dict[str, int] = {
    "Certified": 4,
    "Available": 3,
    "Testing": 2,
    "Draft": 1,
}

_EDIT_RE = re.compile(r"\b(edit|inpaint|outpaint|in-paint)\b", re.I)
_INPAINT_RE = re.compile(r"\b(inpaint|in-paint|masked?)\b", re.I)

HOSTED_APPROVAL_ASK = (
    "No compatible local image generator is currently available. I can use fal.ai instead—proceed?"
)


@dataclass(frozen=True)
class ImageGeneratorCandidate:
    model_id: str
    family: str
    locality: str
    executable: bool
    installed: bool
    runtime_ready: bool
    supports: tuple[str, ...]
    supports_reference: bool
    supports_edit: bool
    provider: str
    model_family: str
    capability_label: str
    default_eligible: bool
    label: str
    lifecycle: str = ""
    quality_status: str = ""

    @property
    def is_local(self) -> bool:
        return self.locality == "local"

    def as_observability(self) -> dict[str, Any]:
        return {
            "modelId": self.model_id,
            "family": self.family,
            "locality": self.locality,
            "executable": self.executable,
            "installed": self.installed,
            "runtimeReady": self.runtime_ready,
            "supports": list(self.supports),
            "provider": self.provider,
            "capabilityLabel": self.capability_label,
            "defaultEligible": self.default_eligible,
        }


@dataclass
class AutoImageSelection:
    selected: ImageGeneratorCandidate | None
    task: str
    route: str = "AUTO"
    source: str = "auto"
    why: str = ""
    local_candidates: list[ImageGeneratorCandidate] = field(default_factory=list)
    hosted_candidates: list[ImageGeneratorCandidate] = field(default_factory=list)
    hosted_evaluated: bool = False
    needs_hosted_approval: bool = False
    hosted_ask: str = ""

    @property
    def selected_model_id(self) -> str:
        return self.selected.model_id if self.selected else ""

    @property
    def selected_family(self) -> str:
        return self.selected.family if self.selected else ""

    @property
    def locality(self) -> str:
        return self.selected.locality if self.selected else ""

    def as_observability(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "task": self.task,
            "source": self.source,
            "why": self.why,
            "selectedModelId": self.selected_model_id,
            "selectedFamily": self.selected_family,
            "locality": self.locality,
            "localCandidates": [c.model_id for c in self.local_candidates],
            "hostedCandidates": [c.model_id for c in self.hosted_candidates],
            "hostedEvaluated": self.hosted_evaluated,
            "needsHostedApproval": self.needs_hosted_approval,
        }


def infer_image_task(*, prompt: str = "", reference_asset_id: str | None = None) -> ImageTask:
    if reference_asset_id:
        return "reference"
    blob = prompt or ""
    if _INPAINT_RE.search(blob):
        return "inpaint"
    if _EDIT_RE.search(blob):
        return "edit"
    return "text_to_image"


def required_supports_for_task(task: str) -> tuple[str, ...]:
    return _TASK_SUPPORTS.get(task or "text_to_image", _TASK_SUPPORTS["text_to_image"])


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _supports_task(supports: Sequence[str], task: str) -> bool:
    required = required_supports_for_task(task)
    have = {str(item or "").strip() for item in supports}
    return any(tag in have for tag in required)


def _installed(model: ModelDescriptor) -> bool:
    lifecycle = str(getattr(model, "lifecycle", "") or "")
    return bool(model.executable) or lifecycle in {"Installed", "Loading", "Loaded"}


def _candidate_from_model(
    model: ModelDescriptor,
    *,
    runtime_ready: bool = False,
) -> ImageGeneratorCandidate | None:
    if getattr(model, "modality", None) != "image":
        return None
    if is_ordinary_picker_hidden(model.id):
        return None
    family = image_family_for_dock_model(model.id) or ""
    supports = tuple(str(item) for item in (model.supports or []))
    locality = str(model.locality or "local")
    if locality not in {"local", "hosted"}:
        locality = "hosted" if locality == "hosted" else "local"
    return ImageGeneratorCandidate(
        model_id=model.id,
        family=family,
        locality=locality,
        executable=bool(model.executable),
        installed=_installed(model),
        runtime_ready=runtime_ready,
        supports=supports,
        supports_reference=any(
            tag in supports for tag in ("reference_conditioning", "identity_reference")
        ),
        supports_edit="edit" in supports or "inpaint" in supports,
        provider=str(model.providerId or ""),
        model_family=family,
        capability_label=str(model.capabilityLabel or ""),
        default_eligible=bool(getattr(model, "defaultEligible", False)),
        label=str(model.label or model.id),
        lifecycle=str(getattr(model, "lifecycle", "") or ""),
        quality_status=str(model.capabilityLabel or ""),
    )


def observe_warm_image_model_ids() -> set[str]:
    """Read-only residency peek. Empty when warm state cannot be observed."""

    return set()


def _dock_preferred_image_model_id(project_id: str) -> str:
    try:
        from .store import get_project_preferences, get_user_preferences

        if project_id and project_id != "_global":
            proj = get_project_preferences(project_id)
            mid = getattr(proj, "activeImageModelId", None)
            if mid:
                return str(mid)
        user = get_user_preferences()
        mid = getattr(getattr(user, "image", None), "activeModelId", None)
        return str(mid or "")
    except Exception:
        return ""


def _iter_image_models(models: Iterable[ModelDescriptor] | None) -> list[ModelDescriptor]:
    if models is not None:
        return [m for m in models if getattr(m, "modality", None) == "image"]
    return list(list_models("image"))


def list_compatible_image_generators(
    task: str = "text_to_image",
    locality: str | None = None,
    *,
    models: Iterable[ModelDescriptor] | None = None,
    executable_only: bool = True,
    warm_model_ids: set[str] | None = None,
) -> list[ImageGeneratorCandidate]:
    """Return catalog rows that can perform `task`. Not a second inventory."""

    warm = warm_model_ids if warm_model_ids is not None else observe_warm_image_model_ids()
    out: list[ImageGeneratorCandidate] = []
    for model in _iter_image_models(models):
        if locality and str(model.locality) != locality:
            continue
        if executable_only and not bool(model.executable):
            continue
        if not _supports_task(model.supports or [], task):
            continue
        ready = model.id in warm or (image_family_for_dock_model(model.id) or "") in warm
        candidate = _candidate_from_model(model, runtime_ready=ready)
        if candidate is None:
            continue
        out.append(candidate)
    return out


def _rank_key(
    candidate: ImageGeneratorCandidate,
    *,
    dock_model_id: str,
    warm_model_ids: set[str],
) -> tuple[int, int, int, int]:
    warm = candidate.model_id in warm_model_ids or candidate.family in warm_model_ids
    return (
        1 if candidate.default_eligible else 0,
        _LABEL_RANK.get(candidate.capability_label, 0),
        1 if dock_model_id and candidate.model_id == dock_model_id else 0,
        1 if warm else 0,
    )


def _rank(
    candidates: Sequence[ImageGeneratorCandidate],
    *,
    dock_model_id: str = "",
    warm_model_ids: set[str] | None = None,
) -> list[ImageGeneratorCandidate]:
    warm = warm_model_ids or set()
    return sorted(
        candidates,
        key=lambda c: _rank_key(c, dock_model_id=dock_model_id, warm_model_ids=warm),
        reverse=True,
    )


def _why(
    candidate: ImageGeneratorCandidate,
    *,
    task: str,
    dock_model_id: str,
    warm_model_ids: set[str],
    pool_size: int,
) -> str:
    parts = [
        f"task={task}",
        f"locality={candidate.locality}",
        f"capability={candidate.capability_label}",
    ]
    if candidate.default_eligible:
        parts.append("defaultEligible")
    if dock_model_id and candidate.model_id == dock_model_id:
        parts.append("dockPreference")
    if candidate.model_id in warm_model_ids or candidate.family in warm_model_ids:
        parts.append("warmResident")
    parts.append(f"pool={pool_size}")
    return "; ".join(parts)


def hosted_approval_ask(candidate: ImageGeneratorCandidate | None) -> str:
    label = "fal.ai"
    if candidate is not None:
        provider = (candidate.provider or "").lower()
        if provider == "fal" or "fal" in (candidate.model_id or ""):
            label = "fal.ai"
        elif candidate.label:
            label = candidate.label
        elif provider:
            label = provider
    return (
        f"No compatible local image generator is currently available. "
        f"I can use {label} instead—proceed?"
    )


def _executable_mapped(
    candidates: Sequence[ImageGeneratorCandidate],
) -> list[ImageGeneratorCandidate]:
    return [c for c in candidates if c.executable and c.family]


def match_explicit_image_generator(
    name: str,
    *,
    models: Iterable[ModelDescriptor] | None = None,
    warm_model_ids: set[str] | None = None,
) -> ImageGeneratorCandidate | None:
    """Resolve a creator-named generator against the live catalog. No CD inventory."""

    needle = _norm(name).removesuffix("local")
    if len(needle) < 3:
        return None
    warm = warm_model_ids if warm_model_ids is not None else observe_warm_image_model_ids()
    matches: list[ImageGeneratorCandidate] = []
    for model in _iter_image_models(models):
        ready = model.id in warm or (image_family_for_dock_model(model.id) or "") in warm
        candidate = _candidate_from_model(model, runtime_ready=ready)
        if candidate is None:
            continue
        haystacks = (
            _norm(candidate.model_id),
            _norm(candidate.label),
            _norm(candidate.family),
        )
        if any(
            hay and (needle == hay or needle in hay or hay.startswith(needle) or needle.startswith(hay))
            for hay in haystacks
        ):
            matches.append(candidate)
    if not matches:
        return None
    local = [c for c in matches if c.is_local]
    if local:
        pool = local
    else:
        executable = [c for c in matches if c.executable]
        pool = executable or matches
    ranked = _rank(pool, warm_model_ids=warm)
    return ranked[0]


def select_auto_image_generator(
    task: str = "text_to_image",
    *,
    project_id: str = "",
    models: Iterable[ModelDescriptor] | None = None,
    warm_model_ids: set[str] | None = None,
    dock_model_id: str | None = None,
) -> AutoImageSelection:
    """AUTO: local && executable && compatible first. Hosted only if that pool is empty."""

    warm = warm_model_ids if warm_model_ids is not None else observe_warm_image_model_ids()
    dock = dock_model_id if dock_model_id is not None else _dock_preferred_image_model_id(project_id)
    catalog = list(_iter_image_models(models))

    local_all = list_compatible_image_generators(
        task,
        locality="local",
        models=catalog,
        executable_only=True,
        warm_model_ids=warm,
    )
    local_mapped = _executable_mapped(local_all)
    if local_mapped:
        ranked = _rank(local_mapped, dock_model_id=dock, warm_model_ids=warm)
        chosen = ranked[0]
        why = _why(
            chosen,
            task=task,
            dock_model_id=dock,
            warm_model_ids=warm,
            pool_size=len(ranked),
        )
        logger.info(
            "image AUTO selected local %s (%s) why=%s candidates=%s",
            chosen.model_id,
            chosen.family,
            why,
            [c.model_id for c in ranked],
        )
        return AutoImageSelection(
            selected=chosen,
            task=task,
            route="AUTO",
            source="auto",
            why=why,
            local_candidates=ranked,
            hosted_candidates=[],
            hosted_evaluated=False,
            needs_hosted_approval=False,
        )

    hosted_all = list_compatible_image_generators(
        task,
        locality="hosted",
        models=catalog,
        executable_only=True,
        warm_model_ids=warm,
    )
    hosted_mapped = _executable_mapped(hosted_all)
    ranked_hosted = _rank(hosted_mapped, dock_model_id=dock, warm_model_ids=warm)
    chosen = ranked_hosted[0] if ranked_hosted else None
    ask = hosted_approval_ask(chosen) if ranked_hosted else HOSTED_APPROVAL_ASK
    why = (
        _why(chosen, task=task, dock_model_id=dock, warm_model_ids=warm, pool_size=len(ranked_hosted))
        if chosen
        else f"task={task}; no compatible executable local or hosted generator"
    )
    logger.info(
        "image AUTO no local candidate; hosted_evaluated=true hosted=%s selected=%s",
        [c.model_id for c in ranked_hosted],
        chosen.model_id if chosen else "",
    )
    return AutoImageSelection(
        selected=chosen,
        task=task,
        route="AUTO",
        source="auto",
        why=why,
        local_candidates=[],
        hosted_candidates=ranked_hosted,
        hosted_evaluated=True,
        needs_hosted_approval=True,
        hosted_ask=ask,
    )


def hosted_execution_binding(candidate: ImageGeneratorCandidate) -> dict[str, str]:
    """Compiler enqueue fields for a hosted catalog row. Translation, not inventory."""

    family = candidate.family or ""
    provider = (candidate.provider or "").lower()
    mid = candidate.model_id or ""
    fal_id = ""
    if provider == "fal" or "fal" in mid:
        from ..fal_catalog import fal_image_model_id_for_dock

        fal_id = fal_image_model_id_for_dock(mid) or ""
        if mid == "flux-fal" and not fal_id:
            fal_id = "fal-ai/flux/dev"
    if fal_id:
        return {
            "family": family,
            "workflowKey": f"fal:{fal_id}",
            "hostedModelId": mid,
            "falImageModelId": fal_id,
        }
    return {
        "family": family,
        "workflowKey": f"{family}.txt2img" if family else "",
        "hostedModelId": mid,
        "falImageModelId": "",
    }
