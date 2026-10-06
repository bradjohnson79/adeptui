"""Local Atlas Designer: design routing, no GPT fallback, no MoGe finished product."""

from __future__ import annotations

import uuid

from app.codirector.capabilities.handlers import atlas_generate
from app.spatial_map.atlas_design import (
    compile_local_atlas_design_prompt,
    local_atlas_aspect,
    packet_alignment_report,
)
from app.spatial_map.design_guide import rasterize_design_guide
from app.spatial_map.atlas_provider import (
    RETIRED_LOCAL_ATLAS_KEYS,
    resolve_atlas_design_provider,
    resolve_local_atlas_design_provider,
)
from app.spatial_map.scene_intent import build_scene_intent, compile_environment_design


CORRIDOR = (
    "Long silver metallic corridor with an elevator door at the end of the corridor. "
    "Around the middle area of the corridor is a door to the Combat chamber on the right side. "
    "Yellow strip against the wall leading to the Combat Chamber."
)


def _patch_enqueue(monkeypatch, captured: list[dict]):
    class _Job:
        id = "job-local-atlas-1"

    def _fake(db, project_id, body, scene_id=None):
        captured.append(dict(body))
        return _Job()

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake)


def test_local_resolver_never_returns_gpt() -> None:
    resolved = resolve_local_atlas_design_provider(require_ready=False)
    assert resolved["ok"] is False
    assert resolved["code"] == "LOCAL_ATLAS_NOT_PRODUCTION_CERTIFIED"
    assert not resolved.get("workflowKey")
    assert resolved.get("certified") is False


def test_local_resolver_refuses_gpt_explicit() -> None:
    resolved = resolve_local_atlas_design_provider(explicit="gpt-image-2-kie", require_ready=False)
    assert resolved["ok"] is False
    assert resolved["code"] == "LOCAL_ATLAS_NO_GPT"


def test_local_resolver_refuses_retired_atlas_i2i() -> None:
    resolved = resolve_local_atlas_design_provider(explicit="qwen2512.atlas", require_ready=False)
    assert resolved["ok"] is False


def test_api_resolver_still_gpt_only() -> None:
    resolved = resolve_atlas_design_provider(configured=True)
    assert resolved["ok"] is True
    assert resolved["hostedModelId"] == "gpt-image-2-kie"
    refused = resolve_atlas_design_provider(explicit="flux.txt2img", configured=True)
    assert refused["ok"] is False


def test_local_prompt_uses_shared_packet_and_forbids_camera() -> None:
    packet = compile_environment_design(CORRIDOR)
    intent = build_scene_intent(CORRIDOR, environment_design=packet, originating_prompt=CORRIDOR)
    prompt = compile_local_atlas_design_prompt(intent, style_reference=True)
    assert "STRICT ROOFLESS" in prompt
    assert "Combat" in prompt
    assert "yellow" in prompt.lower()
    assert "elevator" in prompt.lower()
    assert "eye-level" in prompt.lower()
    assert "vanishing-point" in prompt.lower()
    assert "appearance reference" in prompt.lower()
    assert packet_alignment_report(packet, prompt=prompt)["ok"] is True


def test_local_fail_does_not_call_gpt_or_moge(monkeypatch) -> None:
    captured: list[dict] = []
    recon: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    monkeypatch.setattr(
        "app.spatial_map.local_reconstruct.enqueue_spatial_reconstruct_job",
        lambda db, project_id, body: recon.append(body) or type("J", (), {"id": "recon"})(),
    )
    monkeypatch.setattr(
        "app.spatial_map.atlas_provider.resolve_local_atlas_design_provider",
        lambda **_kwargs: {
            "ok": False,
            "code": "LOCAL_ATLAS_NOT_READY",
            "message": "A local Atlas designer is not ready on this machine.",
        },
    )
    atlas_generate.handle(
        db=None,
        project_id=f"proj-{uuid.uuid4()}",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt=CORRIDOR,
        scene_description=CORRIDOR,
        generationMethod="local",
        mode="express",
    )
    assert captured
    leak = str(captured[0]).lower()
    assert "gpt-image-2" in leak
    assert "qwen2512.atlas_layout" not in leak
    assert recon == []


def test_local_corridor_uses_tall_plate(monkeypatch) -> None:
    captured: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    atlas_generate.handle(
        db=None,
        project_id=f"proj-{uuid.uuid4()}",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt=CORRIDOR,
        scene_description=CORRIDOR,
        generationMethod="local",
        mode="express",
    )
    body = captured[0]
    assert "gpt-image-2" in str(body).lower()
    assert body.get("forceWorkflowKey") not in {"qwen2512.atlas_layout", "flux.txt2img"}
    assert local_atlas_aspect(build_scene_intent(CORRIDOR)) == "9:16"


def test_design_guide_paints_corridor_footprint() -> None:
    packet = compile_environment_design(CORRIDOR)
    png = rasterize_design_guide(packet, description=CORRIDOR, width=256, height=256)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 200


def test_api_path_unchanged_after_local_designer(monkeypatch) -> None:
    captured: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    atlas_generate.handle(
        db=None,
        project_id=f"proj-{uuid.uuid4()}",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt="Create a new underground lab environment.",
        scene_description="a silver underground research corridor for Spatial Map",
        generationMethod="api",
        generation_route="designed",
    )
    body = captured[0]
    assert body["source"] == "api"
    assert body["hostedModelId"] == "gpt-image-2-kie"
    assert body["creativeContext"]["engineNote"] == "gpt_image_2_atlas_design"
    assert body.get("forceWorkflowKey") in {None, ""}
    assert "local_atlas_design" not in str(body)
