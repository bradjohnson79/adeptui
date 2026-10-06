"""Spatial Map dual-route: design vs reconstruct vs supplied vs style reference."""

from __future__ import annotations

import uuid

from app.codirector.capabilities.handlers import atlas_generate
from app.codirector.routing.spatial_environment_route import (
    classify_spatial_environment_route,
    geometry_source_for_route,
)
from app.spatial_map.atlas_design import (
    compile_atlas_design_prompt,
    compile_local_atlas_design_prompt,
    packet_alignment_report,
)
from app.spatial_map.atlas_provider import (
    resolve_atlas_design_provider,
    resolve_local_atlas_design_provider,
)
from app.spatial_map.local_reconstruct import is_generated_asset, observed_asset_ids
from app.spatial_map.scene_intent import build_scene_intent, compile_environment_design


def test_routing_design_new_environment() -> None:
    assert classify_spatial_environment_route("Create a new underground lab environment.") == "design"
    assert geometry_source_for_route("design") == "designed"


def test_routing_reconstruct_from_image() -> None:
    assert classify_spatial_environment_route("Reconstruct this corridor from the image.") == "reconstruct"
    assert geometry_source_for_route("reconstruct") == "reconstructed"


def test_routing_supplied_atlas() -> None:
    assert classify_spatial_environment_route("Use this Atlas as-is.") == "supplied"
    assert geometry_source_for_route("supplied") == "supplied"


def test_routing_designed_with_reference() -> None:
    assert classify_spatial_environment_route("Make the new Atlas look like this reference.") == "designed_with_reference"
    assert geometry_source_for_route("designed_with_reference") == "designed"


def test_preserve_exact_layout_is_reconstruct() -> None:
    assert classify_spatial_environment_route("Preserve this exact visible layout.") == "reconstruct"


def test_observed_image_beats_generic_design_wording() -> None:
    assert (
        classify_spatial_environment_route(
            "Design a new environment; here is the location image.",
            has_observed_image=True,
            has_style_reference=False,
        )
        == "reconstruct"
    )


def test_explicit_user_choice_wins() -> None:
    assert classify_spatial_environment_route(
        "Create a new lab.",
        explicit_route="reconstruct",
    ) == "reconstruct"


def test_generation_method_aliases() -> None:
    assert classify_spatial_environment_route("A lab.", explicit_route="local") == "reconstruct"
    assert classify_spatial_environment_route("A lab.", explicit_route="api") == "design"
    assert (
        classify_spatial_environment_route(
            "A lab.",
            explicit_route="api",
            has_style_reference=True,
        )
        == "designed_with_reference"
    )


def test_generated_assets_never_count_as_observed() -> None:
    class _Asset:
        tag = "environment_supplementary_view"
        prompt_meta_json = '{"purpose":"environment_supplementary_view"}'
        project_id = "p1"
        path = ""

    assert is_generated_asset(_Asset()) is True


def test_observed_filter_drops_generated(monkeypatch) -> None:
    class _Asset:
        def __init__(self, tag: str, path: str = "/tmp/x.png") -> None:
            self.tag = tag
            self.prompt_meta_json = "{}"
            self.project_id = "p1"
            self.path = path

    class _Db:
        def get(self, _cls, asset_id: str):
            return {
                "obs": _Asset("environment_reference"),
                "gen": _Asset("environment_supplementary_view"),
            }.get(asset_id)

    monkeypatch.setattr("app.spatial_map.local_reconstruct.Path.is_file", lambda self: True)
    assert observed_asset_ids(_Db(), "p1", ["obs", "gen"]) == ["obs"]


def test_design_packet_compiles_dimensions_and_anchors() -> None:
    packet = compile_environment_design(
        "a silver metallic underground research corridor 3 meters wide and 20 meters long with an elevator on the east wall"
    )
    assert packet.dimensions.widthMeters == 3
    assert packet.dimensions.depthMeters == 20
    assert any(a.type == "elevator" for a in packet.anchors)
    intent = build_scene_intent(
        "a silver metallic underground research corridor for Spatial Map",
        environment_design=packet,
    )
    prompt = compile_atlas_design_prompt(intent)
    assert "orthographic top-down" in prompt.lower()
    assert "3" in prompt
    assert "elevator" in prompt.lower()
    assert packet_alignment_report(packet, prompt=prompt)["ok"] is True


def test_atlas_provider_does_not_silent_swap_to_qwen() -> None:
    resolved = resolve_atlas_design_provider(explicit="qwen2512", configured=True)
    assert resolved["ok"] is False
    assert resolved["code"] == "ATLAS_PROVIDER_NOT_CERTIFIED"


def test_atlas_provider_unavailable_is_honest() -> None:
    resolved = resolve_atlas_design_provider(configured=False)
    assert resolved["ok"] is False
    assert "GPT Image 2 is required" in resolved["message"]
    assert "local reconstruction" not in resolved["message"].lower()


def test_local_atlas_candidates_are_not_production_selectable() -> None:
    from app.spatial_map.atlas_provider import LOCAL_ATLAS_CANDIDATES

    assert LOCAL_ATLAS_CANDIDATES == ()
    resolved = resolve_local_atlas_design_provider(require_ready=False)
    assert resolved["ok"] is False
    assert resolved["code"] == "LOCAL_ATLAS_NOT_PRODUCTION_CERTIFIED"
    assert resolved.get("certified") is False


def _patch_enqueue(monkeypatch, captured: list[dict]):
    class _Job:
        id = "job-atlas-1"

    def _fake(db, project_id, body, scene_id=None):
        captured.append(dict(body))
        return _Job()

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake)


def test_design_route_uses_gpt_image_2_t2i(monkeypatch) -> None:
    captured: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    atlas_generate.handle(
        db=None,
        project_id=f"proj-{uuid.uuid4()}",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt="Create a new underground lab environment.",
        scene_description="a silver underground research corridor for Spatial Map",
        generation_route="designed",
    )
    assert captured
    body = captured[0]
    assert body["creativeContext"]["workflowKey"] == "gpt-image-2-text-to-image"
    assert body["creativeContext"]["geometrySource"] == "designed"
    assert "zimage.txt2img" not in str(body)
    assert "qwen2512" not in str(body)


def test_style_reference_is_not_reconstruction(monkeypatch) -> None:
    captured: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.ers_generate._public_asset_url",
        lambda asset_id: f"https://example.test/assets/{asset_id}",
    )
    source = "4d3062e8-8c30-4230-8376-bc25d1d4f735"
    atlas_generate.handle(
        db=None,
        project_id=f"proj-{uuid.uuid4()}",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt="Make the new Atlas look like this reference.",
        scene_description="a silver underground research corridor for Spatial Map",
        generation_route="designed_with_reference",
        attachment_asset_ids=[source],
    )
    body = captured[0]
    assert body["creativeContext"]["geometrySource"] == "designed"
    assert body["creativeContext"]["styleReferenceAssetId"] == source
    assert body["creativeContext"].get("authoritativeSourceAssetId") in {"", None}
    assert "qwen2512.atlas" not in str(body)


def test_reconstruct_route_does_not_enqueue_qwen(monkeypatch) -> None:
    captured: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    jobs: list[dict] = []

    class _Job:
        id = "job-recon-1"

    def _recon(db, project_id, body):
        jobs.append(body)
        return _Job()

    monkeypatch.setattr("app.spatial_map.local_reconstruct.enqueue_spatial_reconstruct_job", _recon)
    source = "4d3062e8-8c30-4230-8376-bc25d1d4f735"
    result = atlas_generate.handle(
        db=None,
        project_id=f"proj-{uuid.uuid4()}",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt="Reconstruct this corridor from the image.",
        generation_route="reconstruct",
        require_source=True,
        attachment_asset_ids=[source],
    )
    assert captured == []
    assert jobs
    assert jobs[0]["geometrySource"] == "reconstructed"
    assert result["geometrySource"] == "reconstructed"
    assert result["generationRoute"] == "reconstruct"


def test_generation_method_local_designs_with_certified_local_workflow(monkeypatch) -> None:
    captured: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    jobs: list[dict] = []

    class _Job:
        id = "job-recon-local"

    monkeypatch.setattr(
        "app.spatial_map.local_reconstruct.enqueue_spatial_reconstruct_job",
        lambda db, project_id, body: jobs.append(body) or _Job(),
    )
    source = "4d3062e8-8c30-4230-8376-bc25d1d4f735"
    result = atlas_generate.handle(
        db=None,
        project_id=f"proj-{uuid.uuid4()}",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt="Create a new underground lab environment.",
        scene_description="Long silver metallic corridor with an elevator door at the end.",
        generationMethod="local",
        mode="express",
        referenceAssetId=source,
        attachment_asset_ids=[source],
    )
    assert jobs == []
    assert captured
    body = captured[0]
    assert result["geometrySource"] == "designed"
    assert result["generationRoute"] == "designed_with_reference"
    leak = str(body).lower()
    assert "gpt-image-2" in leak
    assert body.get("forceWorkflowKey") not in {
        "qwen2512.atlas_layout",
        "qwen2512.atlas",
        "qwen2512.atlas_direct",
        "flux.txt2img",
        "flux.atlas_layout_control",
    }
    assert body.get("hostedModelId") == "gpt-image-2-kie" or "gpt-image-2" in leak
    assert "qwen2512.atlas_layout" not in leak


def test_generation_method_local_description_only(monkeypatch) -> None:
    captured: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    result = atlas_generate.handle(
        db=None,
        project_id=f"proj-{uuid.uuid4()}",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt="A compact medical lab with an exam table and a glass cabinet.",
        scene_description="A compact medical lab with an exam table and a glass cabinet.",
        generationMethod="local",
        mode="express",
    )
    assert captured
    body = captured[0]
    leak = str(body).lower()
    assert result["generationRoute"] in {"design", "designed"}
    assert "gpt-image-2" in leak
    assert body.get("forceWorkflowKey") not in {"qwen2512.atlas_layout", "flux.txt2img"}
    meta = result["child_jobs"][0]["metadata"]
    assert "gpt" in str(meta).lower() or meta.get("hostedModelId") == "gpt-image-2-kie"
    assert meta["geometrySource"] == "designed"


def test_explicit_reconstruct_still_uses_moge(monkeypatch) -> None:
    captured: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    jobs: list[dict] = []

    class _Job:
        id = "job-recon-explicit"

    monkeypatch.setattr(
        "app.spatial_map.local_reconstruct.enqueue_spatial_reconstruct_job",
        lambda db, project_id, body: jobs.append(body) or _Job(),
    )
    source = "4d3062e8-8c30-4230-8376-bc25d1d4f735"
    result = atlas_generate.handle(
        db=None,
        project_id=f"proj-{uuid.uuid4()}",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt="Reconstruct this corridor from the image.",
        generationMethod="local",
        generation_route="reconstruct",
        require_source=True,
        attachment_asset_ids=[source],
    )
    assert captured == []
    assert jobs
    assert result["generationRoute"] == "reconstruct"
    assert result["geometrySource"] == "reconstructed"


def test_generation_method_api_refuses_when_gpt_missing(monkeypatch) -> None:
    captured: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    monkeypatch.setattr(
        "app.spatial_map.atlas_provider.resolve_atlas_design_provider",
        lambda **_kwargs: {
            "ok": False,
            "code": "GPT_IMAGE_2_NOT_CONFIGURED",
            "message": (
                "GPT Image 2 is required for API Spatial Map generation. "
                "Configure GPT Image 2 in your API settings to continue."
            ),
        },
    )
    try:
        atlas_generate.handle(
            db=None,
            project_id=f"proj-{uuid.uuid4()}",
            execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            prompt="A silver underground research corridor for Spatial Map",
            scene_description="A silver underground research corridor for Spatial Map",
            generationMethod="api",
        )
        raise AssertionError("API generation must refuse when GPT Image 2 is not configured")
    except RuntimeError as exc:
        assert "GPT Image 2 is required" in str(exc)
    assert captured == []
