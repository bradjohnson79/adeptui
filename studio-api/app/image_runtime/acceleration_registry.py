"""Quality-neutral local image acceleration — certify per hardware+family+workflow.

No optimizer is global. Keep/reject is
(hardware profile, model family, workflow class, precision/backend).
Character Creator and Prop Creator are regression boundaries, not playgrounds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional


AcceleratorKind = Literal[
    "residency",
    "attention",
    "compile",
    "h2d_cache",
    "vae",
    "approximate_cache",
]

CertificationState = Literal[
    "uncertified",
    "accepted",
    "rejected",
    "advanced_only",
]


@dataclass(frozen=True)
class HardwareProfile:
    gpu_name: str
    vram_mib: int
    cuda: str
    pytorch: str
    compute_capability: str


@dataclass(frozen=True)
class AcceleratorRecord:
    kind: AcceleratorKind
    family: str
    workflow_class: str
    precision: str
    backend: str
    hardware: str
    state: CertificationState
    reason: str
    cold_sec: Optional[float] = None
    warm_sec: Optional[float] = None
    vram_delta_mib: Optional[int] = None


# Live machine from Phase 0 (Desktop Comfy, not studio-api venv).
LIVE_HARDWARE = HardwareProfile(
    gpu_name="NVIDIA GeForce RTX 5090",
    vram_mib=32607,
    cuda="13.0",
    pytorch="2.10.0+cu130",
    compute_capability="12.0",
)


# Tuple-specific. SageAttention on FLUX T2I does not authorize Qwen Edit or CC.
# Phase 0: residency is the only candidate with a measured path (skip unload
# between same-family CD stills). Attention/compile stay uncertified until
# Comfy-side benchmarks exist — studio-api venv has no torch.
CERTIFIED: tuple[AcceleratorRecord, ...] = (
    AcceleratorRecord(
        kind="residency",
        family="*",
        workflow_class="codirector_still",
        precision="existing",
        backend="comfy_resident",
        hardware="rtx5090-32g",
        state="accepted",
        reason=(
            "Skip Comfy free_memory between consecutive same-family stills unless "
            "unload_after_render is on or the next workflow needs VRAM. "
            "Does not change steps, CFG, sampler, size, or quantization."
        ),
    ),
    AcceleratorRecord(
        kind="attention",
        family="*",
        workflow_class="*",
        precision="existing",
        backend="auto",
        hardware="rtx5090-32g",
        state="uncertified",
        reason="Studio API has no torch; attention lives in Desktop Comfy. No keep without measured wall-clock + visual compare.",
    ),
    AcceleratorRecord(
        kind="compile",
        family="*",
        workflow_class="*",
        precision="existing",
        backend="torch.compile",
        hardware="rtx5090-32g",
        state="rejected",
        reason="Windows compile startup cost is not proven to beat warm reuse for Co-Director stills. No global compile-by-default.",
    ),
    AcceleratorRecord(
        kind="approximate_cache",
        family="*",
        workflow_class="*",
        precision="existing",
        backend="teacache",
        hardware="rtx5090-32g",
        state="rejected",
        reason="Approximate caches are not Co-Director default. Advanced only after visual equivalence — not certified this pass.",
    ),
    AcceleratorRecord(
        kind="residency",
        family="qwen_image_edit_2509",
        workflow_class="character_creator_multiview",
        precision="existing",
        backend="comfy_resident",
        hardware="rtx5090-32g",
        state="uncertified",
        reason="Character Creator is a regression boundary. Same-runtime residency may ride only after same-seed visual equivalence on this exact tuple.",
    ),
    AcceleratorRecord(
        kind="residency",
        family="qwen_edit_2509",
        workflow_class="prop_creator",
        precision="existing",
        backend="comfy_resident",
        hardware="rtx5090-32g",
        state="accepted",
        reason=(
            "Phase 3 measured: Venture primary qwen_edit_2509.edit cold~85s warm~17s after "
            "skipping free_memory between same-family Prop Advanced jobs. No step/CFG/size/model change."
        ),
        cold_sec=85.4,
        warm_sec=16.9,
    ),
    AcceleratorRecord(
        kind="residency",
        family="*",
        workflow_class="prop_creator",
        precision="existing",
        backend="comfy_resident",
        hardware="rtx5090-32g",
        state="accepted",
        reason=(
            "Prop Creator residency accepted for consecutive same-family stills on RTX 5090. "
            "Does not change steps, CFG, sampler, size, or quantization."
        ),
        cold_sec=85.4,
        warm_sec=16.9,
    ),
    AcceleratorRecord(
        kind="h2d_cache",
        family="qwen_edit_2509",
        workflow_class="prop_creator",
        precision="existing",
        backend="comfy_execution_cache",
        hardware="rtx5090-32g",
        state="accepted",
        reason=(
            "Phase 4: ref-encode graph reuse across Prop Advanced multi-view angles. "
            "Keys ref asset id+size+mtime, prompt/negative hashes, model token, workflow, "
            "encode canvas params. Relies on Comfy execution_cached for identical shared "
            "encode nodes (LoadImage, neg TextEncode, loaders). No step/CFG/size/model change."
        ),
    ),
    AcceleratorRecord(
        kind="residency",
        family="qwen2512",
        workflow_class="spatial_atlas",
        precision="existing",
        backend="comfy_resident",
        hardware="rtx5090-32g",
        state="uncertified",
        reason=(
            "Spatial Atlas residency rides the shared engine after measured cold/warm "
            "on qwen2512.atlas. Not accepted until the Atlas perf bench records both."
        ),
    ),
)


PROTECTED_WORKFLOWS = frozenset(
    {
        "character_creator_multiview",
        "prop_creator",
        "qwen_image_edit_2509",
    }
)


def lookup(
    *,
    kind: AcceleratorKind,
    family: str,
    workflow_class: str,
    precision: str = "existing",
    backend: str = "",
) -> Optional[AcceleratorRecord]:
    family_l = (family or "").lower()
    workflow_l = (workflow_class or "").lower()
    exact = None
    wildcard = None
    for record in CERTIFIED:
        if record.kind != kind:
            continue
        if precision and record.precision not in {precision, "existing"}:
            continue
        if backend and record.backend not in {backend, "auto", "comfy_resident"}:
            continue
        if record.family not in {"*", family_l} and record.family != family:
            continue
        if record.workflow_class not in {"*", workflow_l} and record.workflow_class != workflow_class:
            continue
        if record.family != "*" and record.workflow_class != "*":
            exact = record
        else:
            wildcard = record
    return exact or wildcard


def is_accepted(
    *,
    kind: AcceleratorKind,
    family: str,
    workflow_class: str,
    precision: str = "existing",
    backend: str = "",
) -> bool:
    record = lookup(
        kind=kind,
        family=family,
        workflow_class=workflow_class,
        precision=precision,
        backend=backend,
    )
    return bool(record and record.state == "accepted")


def should_keep_models_resident(
    *,
    family: str,
    workflow_class: str,
    unload_after_render: bool = False,
    next_needs_vram: bool = False,
) -> bool:
    """Residency for Co-Director / Prop stills. Never override an explicit unload.

    Protected workflows (Character/Prop/Qwen Edit) keep models only when this
    exact tuple is accepted in CERTIFIED — never by wildcard alone for CC.
    """

    if unload_after_render or next_needs_vram:
        return False
    record = lookup(
        kind="residency",
        family=family,
        workflow_class=workflow_class,
    )
    if workflow_class in PROTECTED_WORKFLOWS:
        # Prefer exact family+workflow accepted records (not bare wildcard for CC).
        if record and record.state == "accepted":
            if workflow_class == "character_creator_multiview" and record.family == "*":
                return False
            return True
        return False
    return bool(record and record.state == "accepted")


def certified_summary() -> list[dict[str, Any]]:
    return [
        {
            "kind": r.kind,
            "family": r.family,
            "workflowClass": r.workflow_class,
            "precision": r.precision,
            "backend": r.backend,
            "hardware": r.hardware,
            "state": r.state,
            "reason": r.reason,
        }
        for r in CERTIFIED
    ]
