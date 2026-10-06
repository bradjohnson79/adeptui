"""Co-Director AUTO image selection uses Production Control inventory only."""

from __future__ import annotations

import inspect
from pathlib import Path

from app.codirector.conversation.foundation.image_generation_defaults import (
    DEFAULT_ASPECT,
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    LOCAL_UNAVAILABLE_ASK,
    resolve_image_generation_profile,
)
from app.production_control.contracts import ModelDescriptor
from app.production_control.image_generator_query import (
    infer_image_task,
    list_compatible_image_generators,
    match_explicit_image_generator,
    select_auto_image_generator,
)
from app.production_control.runtime_map import IMAGE_FAMILY_BY_MODEL


REPO = Path(__file__).resolve().parents[2]
DEFAULTS_PATH = (
    REPO
    / "studio-api"
    / "app"
    / "codirector"
    / "conversation"
    / "foundation"
    / "image_generation_defaults.py"
)
HANDLER_PATH = (
    REPO / "studio-api" / "app" / "codirector" / "capabilities" / "handlers" / "image_generate.py"
)


def _model(
    model_id: str,
    *,
    locality: str = "local",
    executable: bool = True,
    supports: list[str] | None = None,
    capability: str = "Available",
    default_eligible: bool = False,
    provider: str = "comfy",
    label: str | None = None,
    lifecycle: str | None = "Installed",
) -> ModelDescriptor:
    return ModelDescriptor(
        id=model_id,
        modality="image",
        label=label or model_id,
        locality=locality,  # type: ignore[arg-type]
        providerId=provider,
        capabilityLabel=capability,  # type: ignore[arg-type]
        lifecycle=lifecycle,  # type: ignore[arg-type]
        supports=supports or ["text_to_image"],
        executable=executable,
        defaultEligible=default_eligible,
    )


def _qwen(**kwargs) -> ModelDescriptor:
    defaults = dict(
        capability="Certified",
        default_eligible=True,
        supports=["text_to_image", "edit", "inpaint", "reference_conditioning"],
        label="Qwen Image 2512 (Local)",
    )
    defaults.update(kwargs)
    return _model("qwen-image-2512-local", **defaults)


def _flux(**kwargs) -> ModelDescriptor:
    defaults = dict(
        capability="Available",
        supports=["text_to_image", "inpaint"],
        label="FLUX Dev (Local Comfy)",
    )
    defaults.update(kwargs)
    return _model("flux-local", **defaults)


def _zimage(**kwargs) -> ModelDescriptor:
    defaults = dict(capability="Testing", supports=["text_to_image"], label="Z-Image Turbo (Local)")
    defaults.update(kwargs)
    return _model("zimage-local", **defaults)


def _flux_fal(**kwargs) -> ModelDescriptor:
    defaults = dict(
        locality="hosted",
        provider="fal",
        capability="Available",
        supports=["text_to_image"],
        label="FLUX (fal.ai)",
        lifecycle=None,
    )
    defaults.update(kwargs)
    return _model("flux-fal", **defaults)


def test_a_only_qwen_auto_selects_qwen() -> None:
    catalog = [_qwen(), _flux(executable=False), _zimage(executable=False), _flux_fal()]
    selection = select_auto_image_generator("text_to_image", models=catalog)
    assert selection.selected_model_id == "qwen-image-2512-local"
    assert selection.selected_family == "qwen2512"
    assert selection.locality == "local"
    assert selection.hosted_evaluated is False
    assert selection.hosted_candidates == []
    assert selection.needs_hosted_approval is False
    profile = resolve_image_generation_profile("Generate a spaceship corridor.")
    assert profile.route == "AUTO"
    assert profile.aspect_ratio == DEFAULT_ASPECT
    assert (profile.width, profile.height) == (DEFAULT_WIDTH, DEFAULT_HEIGHT)


def test_b_flux_and_qwen_uses_production_control_rank() -> None:
    catalog = [_qwen(), _flux(), _flux_fal()]
    selection = select_auto_image_generator("text_to_image", models=catalog)
    assert selection.selected_model_id == "qwen-image-2512-local"
    assert "defaultEligible" in selection.why
    assert "Certified" in selection.why
    assert [c.model_id for c in selection.local_candidates][0] == "qwen-image-2512-local"


def test_c_explicit_flux_wins_regardless_of_rank() -> None:
    catalog = [_qwen(), _flux()]
    auto = select_auto_image_generator("text_to_image", models=catalog)
    assert auto.selected_family == "qwen2512"
    matched = match_explicit_image_generator("Flux Local", models=catalog)
    assert matched is not None
    assert matched.model_id == "flux-local"
    assert matched.family == "flux"
    profile = resolve_image_generation_profile("Generate this with Flux Local.")
    assert profile.explicit_provider == "flux"
    assert profile.route == "explicit"


def test_d_reference_task_skips_t2i_only_flux() -> None:
    catalog = [_flux(), _qwen()]
    selection = select_auto_image_generator("reference", models=catalog)
    assert selection.selected_model_id == "qwen-image-2512-local"
    assert "flux-local" not in [c.model_id for c in selection.local_candidates]
    assert infer_image_task(reference_asset_id="asset-1") == "reference"


def test_e_no_local_evaluates_hosted_and_asks() -> None:
    catalog = [_qwen(executable=False), _flux(executable=False), _flux_fal()]
    selection = select_auto_image_generator("text_to_image", models=catalog)
    assert selection.hosted_evaluated is True
    assert [c.model_id for c in selection.hosted_candidates] == ["flux-fal"]
    assert selection.needs_hosted_approval is True
    assert selection.hosted_ask
    assert "proceed" in selection.hosted_ask.lower()
    assert "fal.ai" in selection.hosted_ask


def test_f_newly_installed_model_appears_without_codirector_change() -> None:
    start = [_qwen(), _flux(executable=False)]
    first = select_auto_image_generator("text_to_image", models=start)
    assert [c.model_id for c in first.local_candidates] == ["qwen-image-2512-local"]
    refreshed = [_qwen(), _flux(executable=True)]
    second = select_auto_image_generator("text_to_image", models=refreshed)
    assert "flux-local" in [c.model_id for c in second.local_candidates]


def test_g_uninstalled_model_is_no_longer_selected() -> None:
    available = [_flux()]
    first = select_auto_image_generator("text_to_image", models=available)
    assert first.selected_model_id == "flux-local"
    gone = [_flux(executable=False), _qwen()]
    second = select_auto_image_generator("text_to_image", models=gone)
    assert second.selected_model_id == "qwen-image-2512-local"
    assert "flux-local" not in [c.model_id for c in second.local_candidates]


def test_h_explicit_unavailable_does_not_fallback() -> None:
    catalog = [_qwen(), _flux(executable=False)]
    matched = match_explicit_image_generator("Flux Local", models=catalog)
    assert matched is not None
    assert matched.model_id == "flux-local"
    assert matched.executable is False
    auto = select_auto_image_generator("text_to_image", models=catalog)
    assert auto.selected_model_id == "qwen-image-2512-local"


def test_defaults_file_has_no_model_inventory() -> None:
    src = DEFAULTS_PATH.read_text(encoding="utf-8")
    assert "_CLOUD_FAMILIES" not in src
    assert "resolve_auto_local_family" not in src
    assert "recommend_image_family" not in src
    assert "zimage" not in src
    assert "qwen2512" not in src
    assert "imagen" not in src
    assert "DEFAULT_ROUTE" in src
    assert "DEFAULT_ASPECT" in src
    assert "1920" in src
    assert "1080" in src


def test_handler_auto_does_not_import_recommend() -> None:
    src = HANDLER_PATH.read_text(encoding="utf-8")
    assert "recommend_image_family" not in src
    assert "resolve_auto_local_family" not in src
    assert "select_auto_image_generator" in src
    from app.codirector.capabilities.handlers import image_generate as handler

    assert "recommend_image_family" not in inspect.getsource(handler.handle)


def test_local_first_does_not_evaluate_hosted() -> None:
    catalog = [_qwen(), _flux_fal()]
    selection = select_auto_image_generator("text_to_image", models=catalog)
    assert selection.hosted_evaluated is False
    assert selection.hosted_candidates == []
    assert selection.locality == "local"


def test_compatibility_beats_warm_residency() -> None:
    catalog = [_flux(), _qwen()]
    selection = select_auto_image_generator(
        "reference",
        models=catalog,
        warm_model_ids={"flux-local"},
    )
    assert selection.selected_model_id == "qwen-image-2512-local"
    assert "flux-local" not in [c.model_id for c in selection.local_candidates]


def test_illustrious_family_mapping_exists() -> None:
    assert IMAGE_FAMILY_BY_MODEL.get("illustrious-local") == "illustrious"


def test_defaults_16x9_1920x1080_unchanged() -> None:
    profile = resolve_image_generation_profile("Create an image of the Venture corridor.")
    assert profile.route == "AUTO"
    assert profile.local_first is True
    assert profile.aspect_ratio == "16:9"
    assert (profile.width, profile.height) == (1920, 1080)
    assert profile.clarification_count == 0
    assert LOCAL_UNAVAILABLE_ASK.startswith("No compatible local image generator")


def test_explicit_krea_and_illustrious_resolve_from_catalog() -> None:
    catalog = [
        _model(
            "krea2-turbo-local",
            label="Krea 2 Turbo (Local)",
            supports=["text_to_image", "reference_conditioning"],
        ),
        _model("illustrious-local", label="Illustrious XL (Local)"),
        _qwen(),
    ]
    krea = match_explicit_image_generator("Krea", models=catalog)
    illustrious = match_explicit_image_generator("Illustrious", models=catalog)
    assert krea is not None and krea.model_id == "krea2-turbo-local"
    assert illustrious is not None and illustrious.model_id == "illustrious-local"
    profile = resolve_image_generation_profile("Use Illustrious for these images.")
    assert profile.explicit_provider == "illustrious"


def test_list_compatible_filters_task() -> None:
    catalog = [_flux(), _qwen(), _flux_fal()]
    local_t2i = list_compatible_image_generators("text_to_image", locality="local", models=catalog)
    local_ref = list_compatible_image_generators("reference", locality="local", models=catalog)
    assert {c.model_id for c in local_t2i} == {"flux-local", "qwen-image-2512-local"}
    assert {c.model_id for c in local_ref} == {"qwen-image-2512-local"}


def test_handler_auto_enqueues_selected_family(monkeypatch) -> None:
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.codirector.capabilities.handlers import image_generate as handler
    from app.codirector.preferences.resolver import PreferenceResolution
    from app.production_control.image_generator_query import AutoImageSelection, ImageGeneratorCandidate

    captured: list[dict] = []
    chosen = ImageGeneratorCandidate(
        model_id="qwen-image-2512-local",
        family="qwen2512",
        locality="local",
        executable=True,
        installed=True,
        runtime_ready=False,
        supports=("text_to_image",),
        supports_reference=True,
        supports_edit=True,
        provider="comfy",
        model_family="qwen2512",
        capability_label="Certified",
        default_eligible=True,
        label="Qwen",
    )
    monkeypatch.setattr(
        handler,
        "resolve_generator_preference",
        lambda *args, **kwargs: PreferenceResolution(provider="zimage", source="default", modality="image"),
    )
    monkeypatch.setattr("runtime_supervisor.health.comfy_healthy", lambda: True)
    monkeypatch.setattr(handler, "_check_runtime_admission", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        handler,
        "select_auto_image_generator",
        lambda *args, **kwargs: AutoImageSelection(
            selected=chosen,
            task="text_to_image",
            why="test-a",
            local_candidates=[chosen],
        ),
    )
    monkeypatch.setattr(
        "app.storyboard_jobs.enqueue_imagegen_job",
        lambda db, project_id, body=None, **kwargs: captured.append(dict(body or {}))
        or SimpleNamespace(id="job-auth-1"),
    )
    result = handler.handle(
        db=MagicMock(),
        project_id="proj",
        execution_id="exec-auth",
        prompt="Generate a spaceship corridor.",
        user_instructions="Generate a spaceship corridor.",
    )
    assert captured
    assert captured[0]["modelFamilyPreference"] == "qwen2512"
    assert captured[0]["width"] == 1920
    assert captured[0]["height"] == 1080
    assert captured[0]["aspectRatio"] == "16:9"
    assert captured[0]["source"] == "local"
    assert captured[0]["lockModelFamily"] is True
    obs = captured[0]["creativeContext"]["autoResolution"]
    assert obs["selectedModelId"] == "qwen-image-2512-local"
    assert obs["hostedEvaluated"] is False
    assert result["child_jobs"][0]["job_id"] == "job-auth-1"


def test_handler_no_local_fails_forward_to_hosted(monkeypatch) -> None:
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.codirector.capabilities.handlers import image_generate as handler
    from app.codirector.image_route.contracts import ProviderAvailability
    from app.codirector.preferences.resolver import PreferenceResolution
    from app.production_control.image_generator_query import AutoImageSelection, ImageGeneratorCandidate

    captured: list[dict] = []
    hosted = ImageGeneratorCandidate(
        model_id="flux-fal",
        family="flux",
        locality="hosted",
        executable=True,
        installed=False,
        runtime_ready=False,
        supports=("text_to_image",),
        supports_reference=False,
        supports_edit=False,
        provider="fal",
        model_family="flux",
        capability_label="Available",
        default_eligible=False,
        label="FLUX (fal.ai)",
    )
    monkeypatch.setattr(
        handler,
        "resolve_generator_preference",
        lambda *args, **kwargs: PreferenceResolution(provider="zimage", source="default", modality="image"),
    )
    monkeypatch.setattr("runtime_supervisor.health.comfy_healthy", lambda: True)
    monkeypatch.setattr(
        handler,
        "select_auto_image_generator",
        lambda *args, **kwargs: AutoImageSelection(
            selected=hosted,
            task="text_to_image",
            hosted_candidates=[hosted],
            hosted_evaluated=True,
            needs_hosted_approval=True,
            hosted_ask=LOCAL_UNAVAILABLE_ASK,
        ),
    )
    monkeypatch.setattr(
        handler,
        "list_compatible_image_generators",
        lambda *args, **kwargs: [hosted] if kwargs.get("locality") == "hosted" else [],
    )
    monkeypatch.setattr(
        handler,
        "observe_hosted_provider_state",
        lambda pid: ProviderAvailability(
            provider_id=pid,
            provider_configured=True,
            provider_reachable=True,
            provider_funded=True,
            funding_state="unknown",
        ),
    )
    monkeypatch.setattr(
        "app.storyboard_jobs.enqueue_imagegen_job",
        lambda db, project_id, body=None, **kwargs: captured.append(dict(body or {}))
        or SimpleNamespace(id="job-hosted-fallback"),
    )
    result = handler.handle(
        db=MagicMock(),
        project_id="proj",
        execution_id="exec-ask",
        prompt="Create an image of the Venture corridor.",
        user_instructions="Create an image of the Venture corridor.",
    )
    assert captured
    assert captured[0].get("source") == "fal"
    assert captured[0].get("hostedModelId") == "flux-fal"
    assert result["child_jobs"]
    assert "hosted image API" in (result.get("creatorAck") or "")


def test_handler_explicit_unavailable_blocks(monkeypatch) -> None:
    from unittest.mock import MagicMock

    from app.codirector.capabilities.handlers import image_generate as handler
    from app.codirector.preferences.resolver import PreferenceResolution
    from app.production_control.image_generator_query import ImageGeneratorCandidate

    captured: list[dict] = []
    monkeypatch.setattr(
        handler,
        "resolve_generator_preference",
        lambda *args, **kwargs: PreferenceResolution(
            provider="flux",
            source="explicit",
            modality="image",
            explicit=True,
            configured=True,
        ),
    )
    monkeypatch.setattr(
        handler,
        "match_explicit_image_generator",
        lambda name, **kwargs: ImageGeneratorCandidate(
            model_id="flux-local",
            family="flux",
            locality="local",
            executable=False,
            installed=False,
            runtime_ready=False,
            supports=("text_to_image",),
            supports_reference=False,
            supports_edit=False,
            provider="comfy",
            model_family="flux",
            capability_label="Requires Setup",
            default_eligible=False,
            label="FLUX Dev",
        ),
    )
    monkeypatch.setattr(
        "app.storyboard_jobs.enqueue_imagegen_job",
        lambda *args, **kwargs: captured.append({}),
    )
    result = handler.handle(
        db=MagicMock(),
        project_id="proj",
        execution_id="exec-block",
        prompt="Generate this with Flux Local only.",
        user_instructions="Generate this with Flux Local only.",
    )
    assert captured == []
    assert result["child_jobs"] == []
    assert "only that model" in (result.get("error") or "").lower()


def test_handler_visual_reference_pins_qwen_ref_pixels(monkeypatch) -> None:
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.codirector.capabilities.handlers import image_generate as handler
    from app.codirector.preferences.resolver import PreferenceResolution
    from app.production_control.image_generator_query import AutoImageSelection, ImageGeneratorCandidate

    captured: list[dict] = []
    chosen = ImageGeneratorCandidate(
        model_id="qwen-image-2512-local",
        family="qwen2512",
        locality="local",
        executable=True,
        installed=True,
        runtime_ready=True,
        supports=("text_to_image", "reference_conditioning"),
        supports_reference=True,
        supports_edit=True,
        provider="comfy",
        model_family="qwen2512",
        capability_label="Certified",
        default_eligible=True,
        label="Qwen",
    )
    monkeypatch.setattr(
        handler,
        "collect_character_references",
        lambda *args, **kwargs: ([], ["5567e90b-8038-4484-a394-ec5b3b9ac2eb"], ""),
    )
    monkeypatch.setattr(
        handler,
        "resolve_generator_preference",
        lambda *args, **kwargs: PreferenceResolution(provider="qwen2512", source="default", modality="image"),
    )
    monkeypatch.setattr("runtime_supervisor.health.comfy_healthy", lambda: True)
    monkeypatch.setattr(handler, "_check_runtime_admission", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        handler,
        "select_auto_image_generator",
        lambda *args, **kwargs: AutoImageSelection(
            selected=chosen,
            task="reference",
            why="test-ref",
            local_candidates=[chosen],
        ),
    )
    monkeypatch.setattr(
        "app.storyboard_jobs.enqueue_imagegen_job",
        lambda db, project_id, body=None, **kwargs: captured.append(dict(body or {}))
        or SimpleNamespace(id="job-ref-1"),
    )
    result = handler.handle(
        db=MagicMock(),
        project_id="proj",
        execution_id="exec-ref",
        prompt="Make it more like this.",
        user_instructions="Make it more like this.",
        original_user_instructions="Make it more like this.",
        attachment_asset_ids=["5567e90b-8038-4484-a394-ec5b3b9ac2eb"],
    )
    assert captured
    body = captured[0]
    assert body["forceWorkflowKey"] == "qwen2512.ref"
    assert body["sourceAssetId"] == "5567e90b-8038-4484-a394-ec5b3b9ac2eb"
    assert body["referenceImage"] == "5567e90b-8038-4484-a394-ec5b3b9ac2eb"
    assert "txt2img" not in str(body.get("creativeContext", {}).get("workflowKey") or "")
    assert result["child_jobs"][0]["metadata"]["reference_asset_id"] == "5567e90b-8038-4484-a394-ec5b3b9ac2eb"


def test_handler_visual_reference_pins_certified_flux_img2img(monkeypatch) -> None:
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.codirector.capabilities.handlers import image_generate as handler
    from app.codirector.preferences.resolver import PreferenceResolution
    from app.production_control.image_generator_query import AutoImageSelection, ImageGeneratorCandidate

    captured: list[dict] = []
    chosen = ImageGeneratorCandidate(
        model_id="flux-local",
        family="flux",
        locality="local",
        executable=True,
        installed=True,
        runtime_ready=True,
        supports=("text_to_image", "reference_conditioning"),
        supports_reference=True,
        supports_edit=True,
        provider="comfy",
        model_family="flux",
        capability_label="Certified",
        default_eligible=True,
        label="Flux",
    )
    monkeypatch.setattr(
        handler,
        "collect_character_references",
        lambda *args, **kwargs: ([], ["5567e90b-8038-4484-a394-ec5b3b9ac2eb"], ""),
    )
    monkeypatch.setattr(
        handler,
        "resolve_generator_preference",
        lambda *args, **kwargs: PreferenceResolution(
            provider="flux",
            source="explicit",
            modality="image",
            explicit=True,
            configured=True,
        ),
    )
    monkeypatch.setattr("runtime_supervisor.health.comfy_healthy", lambda: True)
    monkeypatch.setattr(handler, "_check_runtime_admission", lambda *args, **kwargs: None)
    monkeypatch.setattr(handler, "match_explicit_image_generator", lambda *args, **kwargs: chosen)
    monkeypatch.setattr(
        handler,
        "select_auto_image_generator",
        lambda *args, **kwargs: AutoImageSelection(
            selected=chosen,
            task="reference",
            why="test-flux-ref",
            local_candidates=[chosen],
        ),
    )
    monkeypatch.setattr(
        "app.storyboard_jobs.enqueue_imagegen_job",
        lambda db, project_id, body=None, **kwargs: captured.append(dict(body or {}))
        or SimpleNamespace(id="job-flux-ref-1"),
    )
    result = handler.handle(
        db=MagicMock(),
        project_id="proj",
        execution_id="exec-flux-ref",
        prompt="Make it more like this with Flux.",
        user_instructions="Make it more like this with Flux.",
        original_user_instructions="Make it more like this with Flux.",
        attachment_asset_ids=["5567e90b-8038-4484-a394-ec5b3b9ac2eb"],
        requested_model_id="flux",
        lock_level="PREFERRED",
    )
    assert captured
    body = captured[0]
    assert body["forceWorkflowKey"] == "flux.img2img"
    assert body["sourceAssetId"] == "5567e90b-8038-4484-a394-ec5b3b9ac2eb"
    assert "flux.reference" not in str(body)
    assert result["child_jobs"][0]["metadata"]["reference_asset_id"] == "5567e90b-8038-4484-a394-ec5b3b9ac2eb"
