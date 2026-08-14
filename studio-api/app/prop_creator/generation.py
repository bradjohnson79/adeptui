"""Prop Creator candidate routing — User Control Law + generation-mode labels."""

from __future__ import annotations

import random
from typing import Any

from ..scene_creator.generation import hosted_image_generation_available, list_local_generator_families

CandidatePlan = dict[str, Any]


def build_prop_candidate_plans(
    *,
    local_enabled: bool,
    api_enabled: bool,
    local_family: str = "",
    api_model: str = "",
    has_reference: bool = False,
    candidate_count: int = 4,
    seed: int | None = None,
) -> list[CandidatePlan]:
    """Build up to four plans. Unchecked source = zero jobs.

    Do not auto-disable txt2img families when a reference exists.
    Label each plan Reference Conditioned or Description Guided.
    """
    count = max(1, min(int(candidate_count or 4), 4))
    if not local_enabled and not api_enabled:
        raise ValueError("Enable a Local or API generator to create prop images.")

    api_ok = hosted_image_generation_available()
    if api_enabled and not api_ok:
        raise ValueError("API Generation — Not Available")

    local_families = [m for m in list_local_generator_families(has_reference=False) if m.get("executable")]
    selected_local = (local_family or "").strip()
    if selected_local and local_enabled:
        preferred = [m for m in local_families if m.get("id") == selected_local]
        rest = [m for m in local_families if m.get("id") != selected_local]
        local_families = preferred + rest

    sources: list[CandidatePlan] = []
    if local_enabled:
        if not local_families:
            raise ValueError("No local image generator is ready. Open Source Manager to install a Certified generator.")
        for fam in local_families:
            supports_ref = bool(fam.get("supportsReferences"))
            conditioned = has_reference and supports_ref
            sources.append(
                {
                    "source": "local",
                    "family": fam["id"],
                    "model": fam["id"],
                    "label": fam.get("label") or fam["id"],
                    "supports_references": supports_ref,
                    "conditioning": "reference_conditioned" if conditioned else "description_guided",
                }
            )
    if api_enabled and api_ok:
        sources.append(
            {
                "source": "api",
                "family": "hosted",
                "model": (api_model or "").strip() or "hosted",
                "label": (api_model or "").strip() or "Cloud generator",
                "supports_references": False,
                "conditioning": "description_guided",
            }
        )

    if not sources:
        raise ValueError("Enable a Local or API generator to create prop images.")

    rng = random.Random(seed if seed is not None else random.randint(1, 2_147_483_647))
    plans: list[CandidatePlan] = []
    for i in range(count):
        src = sources[i % len(sources)]
        mode = src["conditioning"]
        mode_label = "Reference Conditioned" if mode == "reference_conditioned" else "Description Guided"
        prefix = "LOCAL" if src["source"] == "local" else "API"
        plans.append(
            {
                **src,
                "index": i,
                "seed": rng.randint(1, 2_147_483_647),
                "provenance_label": f"{prefix} — {src['label']} — {mode_label}",
            }
        )
    return plans
