"""Hosted image availability + fail-forward orchestration (matrix A–J)."""

from __future__ import annotations

from app.codirector.conversation.foundation.image_generation_defaults import (
    parse_image_generation_overrides,
)
from app.codirector.generation_memory.contracts import CanonicalGenerationRequest
from app.codirector.generation_memory.inherit import apply_typed_inheritance, overrides_from_utterance
from app.codirector.image_route.contracts import ProviderAvailability, RouteLock
from app.codirector.image_route.lock import parse_route_lock
from app.codirector.image_route.orchestrator import plan_image_route
from app.production_control.image_generator_query import AutoImageSelection, ImageGeneratorCandidate

BRIEF = (
    "Create a Silver metallic Venture corridor scene where we see an elevator door "
    "at the end of the corridor."
)
RETRY_GPT = "Retry with same prompt again and use GPT Image 2."
RETRY_GPT_ONLY = "Retry with the same prompt and use GPT Image 2 only."


def _cand(
    model_id: str,
    *,
    family: str,
    locality: str,
    provider: str,
    executable: bool = True,
    supports: tuple[str, ...] = ("text_to_image",),
    label: str = "",
    capability: str = "Available",
    default_eligible: bool = False,
) -> ImageGeneratorCandidate:
    return ImageGeneratorCandidate(
        model_id=model_id,
        family=family,
        locality=locality,
        executable=executable,
        installed=locality == "local",
        runtime_ready=False,
        supports=supports,
        supports_reference="reference_conditioning" in supports,
        supports_edit="edit" in supports or "inpaint" in supports,
        provider=provider,
        model_family=family,
        capability_label=capability,
        default_eligible=default_eligible,
        label=label or model_id,
    )


GPT_KIE = _cand(
    "gpt-image-2-kie",
    family="imagen",
    locality="hosted",
    provider="kie",
    executable=False,
    supports=("text_to_image", "edit"),
    label="GPT Image 2 (Kie)",
    capability="Testing",
)
GPT_KIE_OK = _cand(
    "gpt-image-2-kie",
    family="imagen",
    locality="hosted",
    provider="kie",
    executable=True,
    supports=("text_to_image", "edit"),
    label="GPT Image 2 (Kie)",
    capability="Testing",
)
GPT_FAL = _cand(
    "gpt-image-2-fal",
    family="gptimage2",
    locality="hosted",
    provider="fal",
    executable=True,
    supports=("text_to_image", "edit", "reference_conditioning"),
    label="GPT Image 2 (fal.ai)",
    capability="Available",
)
FLUX_FAL = _cand("flux-fal", family="flux", locality="hosted", provider="fal", label="FLUX (fal.ai)")
FLUX_KIE = _cand(
    "flux-kie",
    family="flux",
    locality="hosted",
    provider="kie",
    executable=True,
    label="FLUX (Kie)",
    capability="Testing",
)
QWEN = _cand(
    "qwen-image-2512-local",
    family="qwen2512",
    locality="local",
    provider="comfy",
    supports=("text_to_image", "edit", "inpaint", "reference_conditioning"),
    label="Qwen",
    capability="Certified",
    default_eligible=True,
)
FLUX_LOCAL = _cand("flux-local", family="flux", locality="local", provider="comfy", label="Flux Local")


def _state(
    pid: str,
    *,
    configured: bool = True,
    reachable: bool = True,
    funded: bool = True,
    funding: str = "unknown",
    failure: str = "",
) -> ProviderAvailability:
    return ProviderAvailability(
        provider_id=pid,
        provider_configured=configured,
        provider_reachable=reachable,
        provider_funded=funded,
        funding_state=funding,  # type: ignore[arg-type]
        failure_class=failure,  # type: ignore[arg-type]
        probe={"balance": None if funding == "unknown" else 0},
    )


def _plan(
    *,
    lock: RouteLock,
    catalog: list[ImageGeneratorCandidate],
    states: dict[str, ProviderAvailability],
    explicit_name: str = "",
    task: str = "text_to_image",
    local_ready: bool = True,
    auto: ImageGeneratorCandidate | None = None,
) -> object:
    by_id = {item.model_id: item for item in catalog}

    def match(name: str, **_kwargs):
        token = (name or "").lower().replace(" ", "").replace("-", "")
        if "gpt" in token:
            return by_id.get("gpt-image-2-fal") or by_id.get("gpt-image-2-kie")
        if token in {"fluxfal", "flux"} and "flux-fal" in by_id and not token.endswith("local"):
            return by_id.get("flux-fal") or by_id.get("flux-local")
        if "flux" in token:
            return by_id.get("flux-local") or by_id.get("flux-fal")
        if "qwen" in token:
            return by_id.get("qwen-image-2512-local")
        return by_id.get(name)

    def listing(task="text_to_image", locality=None, executable_only=True, **_kwargs):
        rows = []
        for item in catalog:
            if locality and item.locality != locality:
                continue
            if executable_only and not item.executable:
                continue
            rows.append(item)
        return rows

    chosen = auto
    if chosen is None:
        locals_ok = [item for item in catalog if item.is_local and item.executable]
        chosen = locals_ok[0] if locals_ok else None

    def select(task="text_to_image", project_id="", **_kwargs):
        return AutoImageSelection(selected=chosen, task=task, why="test-auto")

    return plan_image_route(
        task=task,
        lock=lock,
        explicit_name=explicit_name,
        requested_provider=lock.requested_provider,
        requested_model_id=lock.requested_model_id,
        catalog=catalog,
        provider_states=states,
        local_runtime_ready=local_ready,
        match_explicit=match,
        list_compatible=listing,
        select_auto=select,
        observe_provider=lambda pid: states.get(pid) or _state(pid, configured=False, reachable=False),
    )


def test_named_model_wins_over_generic_hosted() -> None:
    lock = parse_route_lock("Let's use fal.ai API with GPT Image 2.")
    assert lock.requested_model_id == "gptimage2"
    assert lock.level == "PREFERRED"
    assert lock.scope == "model"
    assert lock.requested_provider == "fal"


def test_fal_plus_gpt_image_2_selects_fal_row() -> None:
    """fal.ai + GPT Image 2 is a composed route on gpt-image-2-fal. Not Flux/Qwen/Kie."""

    lock = parse_route_lock(
        "Let's create the corridor image closer to the image that is attached "
        "through fal.ai, GPT Image 2, 16:9 ratio."
    )
    assert lock.requested_model_id == "gptimage2"
    assert lock.requested_provider == "fal"
    plan = _plan(
        lock=lock,
        explicit_name="gptimage2",
        task="reference",
        catalog=[GPT_KIE, GPT_FAL, FLUX_FAL, QWEN],
        states={"kie": _state("kie"), "fal": _state("fal")},
    )
    assert plan.blocked is False
    assert plan.selected is not None
    assert plan.selected.model_id == "gpt-image-2-fal"
    assert plan.selected.provider == "fal"
    assert plan.step == "exact"


def test_fal_plus_gpt_image_2_fails_closed_without_fal_row() -> None:
    """If only the Kie GPT Image 2 row exists, fal.ai + GPT Image 2 fails closed."""

    lock = parse_route_lock(
        "Let's create the corridor image closer to the image that is attached "
        "through fal.ai, GPT Image 2, 16:9 ratio."
    )
    plan = _plan(
        lock=lock,
        explicit_name="gptimage2",
        task="reference",
        catalog=[GPT_KIE, FLUX_FAL, QWEN],
        states={"kie": _state("kie"), "fal": _state("fal")},
    )
    assert plan.blocked is True
    assert plan.selected is None
    assert "GPT Image 2" in plan.error
    assert "fal.ai" in plan.error
    assert "can't generate" in plan.error.lower()
    assert plan.step == "exact"


def test_strict_without_name_still_strict() -> None:
    lock = parse_route_lock("Do not switch.")
    assert lock.level == "STRICT"
    assert lock.restated is True
    assert lock.blocks_other_models() is True
    assert lock.blocks_other_providers() is True


def test_silent_retry_inherits_strict_lock() -> None:
    prior = CanonicalGenerationRequest(
        requestId="req-strict",
        projectId="proj-a",
        originalUserInstructions=BRIEF,
        lockLevel="STRICT",
        lockScope="model",
        requestedModelId="gptimage2",
        modelId="gptimage2",
    )
    nxt, audit = apply_typed_inheritance(
        prior,
        overrides=overrides_from_utterance("Retry the same prompt."),
        project_id="proj-a",
    )
    assert nxt.lockLevel == "STRICT"
    assert nxt.lockScope == "model"
    assert nxt.requestedModelId == "gptimage2"
    assert nxt.fallbackAudit == {}
    assert "lockLevel" in audit.inherited
    plan = _plan(
        lock=RouteLock(
            level=nxt.lockLevel,  # type: ignore[arg-type]
            scope=nxt.lockScope,  # type: ignore[arg-type]
            requested_model_id=nxt.requestedModelId,
        ),
        explicit_name=nxt.requestedModelId,
        catalog=[GPT_KIE, FLUX_FAL, QWEN],
        states={"kie": _state("kie"), "fal": _state("fal")},
    )
    assert plan.blocked is True
    assert plan.selected is None
    assert "only that model" in plan.error


def test_unlocked_auto_ignores_leftover_gpt_image_2_name() -> None:
    """H-P1-04: UNLOCKED AUTO must not treat a leftover gptimage2 name as exact fal."""

    lock = parse_route_lock("Create an image of the corridor.")
    assert lock.level == "UNLOCKED"
    plan = _plan(
        lock=lock,
        explicit_name="gptimage2",
        catalog=[GPT_FAL, QWEN],
        states={"fal": _state("fal")},
        auto=QWEN,
    )
    assert plan.blocked is False
    assert plan.selected is not None
    assert plan.selected.model_id == "qwen-image-2512-local"
    assert plan.selected.is_local is True
    assert plan.step == "auto_local"
    assert plan.hosted is False
    assert plan.disclose == ""


def test_unlocked_auto_ignores_leftover_requested_model_and_fal_provider() -> None:
    lock = RouteLock(level="UNLOCKED", requested_model_id="gptimage2", requested_provider="fal")
    plan = _plan(
        lock=lock,
        explicit_name="gpt-image-2-fal",
        catalog=[GPT_FAL, FLUX_FAL, QWEN],
        states={"fal": _state("fal")},
        auto=QWEN,
    )
    assert plan.selected is not None
    assert plan.selected.model_id == "qwen-image-2512-local"
    assert plan.step == "auto_local"


def test_unlocked_auto_uses_hosted_only_when_local_pool_empty() -> None:
    lock = parse_route_lock("Create an image of the corridor.")
    plan = _plan(
        lock=lock,
        explicit_name="gptimage2",
        catalog=[GPT_FAL, FLUX_FAL],
        states={"fal": _state("fal")},
        auto=GPT_FAL,
    )
    assert plan.selected is not None
    assert plan.selected.model_id == "gpt-image-2-fal"
    assert plan.step == "other_hosted"
    assert plan.hosted is True


def test_lock_parse_preferred_and_strict() -> None:
    preferred = parse_route_lock(RETRY_GPT)
    assert preferred.level == "PREFERRED"
    assert preferred.scope == "model"
    assert preferred.requested_model_id == "gptimage2"
    assert preferred.requested_provider == ""
    assert preferred.restated is True
    strict = parse_route_lock(RETRY_GPT_ONLY)
    assert strict.level == "STRICT"
    assert strict.scope == "model"
    assert parse_route_lock("Create an image of the corridor.").level == "UNLOCKED"
    fal = parse_route_lock("Generate this with fal.ai only.")
    assert fal.level == "STRICT"
    assert fal.scope == "provider"
    assert fal.requested_provider == "fal"


def test_gpt_image_2_is_not_classified_as_fal() -> None:
    parsed = parse_image_generation_overrides(RETRY_GPT)
    assert parsed["explicit_provider"] == "gptimage2"
    assert "provider_kind" not in parsed


def test_a_funded_exact_gpt_image_2() -> None:
    lock = parse_route_lock(RETRY_GPT)
    plan = _plan(
        lock=lock,
        explicit_name="gptimage2",
        catalog=[GPT_KIE_OK, FLUX_FAL, QWEN],
        states={"kie": _state("kie", funding="sufficient"), "fal": _state("fal")},
    )
    assert plan.blocked is False
    assert plan.selected is not None
    assert plan.selected.model_id == "gpt-image-2-kie"
    assert plan.step == "exact"
    assert plan.disclose == ""
    assert plan.audit.funding_state in {"sufficient", "unknown"}


def test_b_funded_model_miss_uses_next_api() -> None:
    lock = parse_route_lock(RETRY_GPT)
    plan = _plan(
        lock=lock,
        explicit_name="gptimage2",
        catalog=[GPT_KIE, FLUX_FAL, QWEN],
        states={"kie": _state("kie"), "fal": _state("fal")},
    )
    assert plan.blocked is False
    assert plan.selected is not None
    assert plan.selected.model_id == "flux-fal"
    assert plan.step == "other_hosted"
    assert "GPT Image 2" in plan.disclose
    assert "next available image API" in plan.disclose
    assert "gpt-image-2-kie" in plan.attempted
    assert plan.audit.funding_state == "unknown"


def test_c_exhausted_provider_skips_only_that_api() -> None:
    lock = parse_route_lock("Generate this with fal.ai.")
    plan = _plan(
        lock=lock,
        explicit_name="fal",
        catalog=[FLUX_FAL, FLUX_KIE, QWEN],
        states={
            "fal": _state("fal", funded=False, funding="exhausted", failure="insufficient_funds"),
            "kie": _state("kie", funding="sufficient"),
        },
    )
    assert plan.blocked is False
    assert plan.selected is not None
    assert plan.selected.model_id == "flux-kie"
    assert plan.selected.provider == "kie"
    assert plan.step == "other_hosted"
    assert "fal.ai" in plan.disclose.lower() or "next available" in plan.disclose


def test_d_second_api_when_first_unconfigured() -> None:
    lock = parse_route_lock("Generate this with fal.ai.")
    plan = _plan(
        lock=lock,
        catalog=[FLUX_FAL, FLUX_KIE, QWEN],
        states={
            "fal": _state("fal", configured=False, reachable=False, failure="provider_unavailable"),
            "kie": _state("kie"),
        },
    )
    assert plan.selected is not None
    assert plan.selected.provider == "kie"
    assert plan.blocked is False


def test_e_all_apis_down_uses_qwen() -> None:
    lock = parse_route_lock(RETRY_GPT)
    plan = _plan(
        lock=lock,
        explicit_name="gptimage2",
        catalog=[GPT_KIE, FLUX_FAL, QWEN],
        states={
            "fal": _state("fal", configured=False, reachable=False),
            "kie": _state("kie", configured=False, reachable=False),
        },
        auto=QWEN,
    )
    assert plan.selected is not None
    assert plan.selected.model_id == "qwen-image-2512-local"
    assert plan.step == "auto_local"
    assert "locally instead" in plan.disclose


def test_f_all_apis_down_uses_flux() -> None:
    lock = parse_route_lock(RETRY_GPT)
    plan = _plan(
        lock=lock,
        explicit_name="gptimage2",
        catalog=[GPT_KIE, FLUX_FAL, FLUX_LOCAL],
        states={
            "fal": _state("fal", configured=False, reachable=False),
            "kie": _state("kie", configured=False, reachable=False),
        },
        auto=FLUX_LOCAL,
    )
    assert plan.selected is not None
    assert plan.selected.model_id == "flux-local"
    assert plan.step == "auto_local"


def test_g_strict_provider_blocks() -> None:
    lock = parse_route_lock("Generate this with fal.ai only.")
    plan = _plan(
        lock=lock,
        catalog=[FLUX_FAL, FLUX_KIE, QWEN],
        states={
            "fal": _state("fal", configured=False, reachable=False),
            "kie": _state("kie"),
        },
    )
    assert plan.blocked is True
    assert plan.selected is None
    assert "only that API" in plan.error
    assert plan.audit.selected_model_id == ""


def test_h_strict_model_blocks() -> None:
    lock = parse_route_lock(RETRY_GPT_ONLY)
    plan = _plan(
        lock=lock,
        explicit_name="gptimage2",
        catalog=[GPT_KIE, FLUX_FAL, QWEN],
        states={"kie": _state("kie"), "fal": _state("fal")},
    )
    assert plan.blocked is True
    assert plan.selected is None
    assert "only that model" in plan.error
    assert "GPT Image 2" in plan.error


def test_i_reference_edit_skips_t2i_only_hosted() -> None:
    lock = parse_route_lock("Edit this with Flux.")
    flux_t2i = _cand("flux-fal", family="flux", locality="hosted", provider="fal", supports=("text_to_image",))
    plan = _plan(
        lock=lock,
        explicit_name="flux",
        task="edit",
        catalog=[flux_t2i, QWEN],
        states={"fal": _state("fal")},
        auto=QWEN,
    )
    assert plan.blocked is False
    assert plan.selected is not None
    assert plan.selected.model_id == "qwen-image-2512-local"
    assert plan.selected.supports_edit is True


def test_j_memory_retry_keeps_brief_and_fail_forwards() -> None:
    prior = CanonicalGenerationRequest(
        requestId="req-1",
        projectId="proj-a",
        originalUserInstructions=BRIEF,
        compiledGeneratorPrompt="COMPILED-SHOULD-NOT-COPY",
        route="AUTO",
        provider="local",
        modelId="qwen2512",
        lockLevel="UNLOCKED",
    )
    nxt, audit = apply_typed_inheritance(
        prior,
        overrides=overrides_from_utterance(RETRY_GPT),
        project_id="proj-a",
    )
    assert nxt.originalUserInstructions == BRIEF
    assert nxt.compiledGeneratorPrompt == ""
    assert nxt.modelId == "gptimage2"
    assert nxt.lockLevel == "PREFERRED"
    assert nxt.requestedModelId == "gptimage2"
    assert "originalUserInstructions" in audit.inherited
    assert "modelId" in audit.overridden
    lock = parse_route_lock(RETRY_GPT)
    plan = _plan(
        lock=lock,
        explicit_name=nxt.modelId,
        catalog=[GPT_KIE, FLUX_FAL, QWEN],
        states={"kie": _state("kie"), "fal": _state("fal")},
    )
    assert plan.blocked is False
    assert plan.selected is not None
    assert plan.selected.model_id == "flux-fal"
    assert nxt.originalUserInstructions == BRIEF


def test_hosted_binding_resolves_gpt_image_2_fal() -> None:
    from app.production_control.image_generator_query import hosted_execution_binding

    binding = hosted_execution_binding(GPT_FAL)
    assert binding["hostedModelId"] == "gpt-image-2-fal"
    assert binding["falImageModelId"] == "openai/gpt-image-2"
    assert binding["workflowKey"] == "fal:openai/gpt-image-2"
    flux = hosted_execution_binding(FLUX_FAL)
    assert flux["falImageModelId"] == "fal-ai/flux/dev"
