"""Shared family route table — never invent `{fam}.ref_edit` / `krea2.txt2img`."""

from app.image_core.capability import (
    generate_workflow_key,
    i2i_workflow_key,
    resolve_family_image_route,
)


def test_t2i_keys_are_real() -> None:
    assert generate_workflow_key("zimage") == "zimage.txt2img"
    assert generate_workflow_key("flux") == "flux.txt2img"
    assert generate_workflow_key("qwen2512") == "qwen2512.txt2img"
    assert generate_workflow_key("krea2") == "krea2.turbo_txt2img"
    assert generate_workflow_key("krea") == "krea2.turbo_txt2img"
    assert generate_workflow_key("illustrious") == "illustrious.txt2img"
    assert generate_workflow_key("qwen_edit_2509") is None


def test_i2i_keys_never_invented() -> None:
    assert i2i_workflow_key("zimage") == "zimage.ref_edit"
    assert i2i_workflow_key("flux") == "flux.img2img"
    assert i2i_workflow_key("qwen_edit_2509") == "qwen_edit_2509.edit"
    assert i2i_workflow_key("krea2") is None
    assert i2i_workflow_key("illustrious") is None
    assert i2i_workflow_key("qwen2512", purpose="general") is None
    assert i2i_workflow_key("qwen2512", purpose="project_prop") == "qwen2512.ref"
    assert i2i_workflow_key("qwen2512", purpose="environment_reference_sheet") == "qwen2512.ref"


def test_cis_qwen2512_refs_fail_closed() -> None:
    route = resolve_family_image_route("qwen2512", has_reference=True, purpose="general")
    assert route["ok"] is False
    assert route["workflowKey"] is None


def test_prop_qwen2512_refs_use_existing_pixel_key() -> None:
    route = resolve_family_image_route("qwen2512", has_reference=True, purpose="project_prop")
    assert route["ok"] is True
    assert route["workflowKey"] == "qwen2512.ref"
    assert route["taskType"] == "IMAGE_I2I"


def test_illustrious_refs_stay_profile_guided() -> None:
    route = resolve_family_image_route("illustrious", has_reference=True, purpose="general")
    assert route["ok"] is True
    assert route["workflowKey"] == "illustrious.txt2img"
    assert route["referenceMode"] == "PROFILE_GUIDED"
    assert route["taskType"] == "IMAGE_T2I"


def test_krea2_t2i_uses_turbo_key() -> None:
    route = resolve_family_image_route("krea2", has_reference=False, purpose="project_prop")
    assert route["ok"] is True
    assert route["workflowKey"] == "krea2.turbo_txt2img"
