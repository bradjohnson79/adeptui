from app.production_control.model_registry import (
    _registry_status_to_label,
    list_models,
)


def test_registry_status_maps_honestly():
    assert _registry_status_to_label("Certified") == "Certified"
    assert _registry_status_to_label("Built") == "Testing"
    assert _registry_status_to_label("Blocked") == "Unavailable"
    assert _registry_status_to_label("Retired") == "Unsupported"


def test_ltx_25_and_fal_are_not_silently_certified():
    by_id = {m.id: m for m in list_models("video")}
    for mid in ("ltx-2.5-full", "ltx-2.5-distilled", "ltx-2.5-comfy"):
        assert by_id[mid].capabilityLabel != "Certified"
        assert by_id[mid].defaultEligible is False
    for mid in ("kling-fal", "seedance-fal", "veo-fal"):
        assert by_id[mid].capabilityLabel != "Certified"
        assert by_id[mid].defaultEligible is False


def test_illustrious_is_present_and_sensenova_is_absent():
    from app.production_control.model_registry import filter_for_action

    by_id = {m.id: m for m in list_models("image")}
    assert "illustrious-local" in by_id
    assert "sensenova-u15-local" not in by_id
    dock = {row["id"] for row in filter_for_action("image", "generate")}
    assert "sensenova-u15-local" not in dock
    assert "qwen-image-edit-2509-local" not in dock
    assert "qwen-image-2512-local" in dock
    assert "flux-local" in dock
    assert "zimage-local" in dock
    assert "krea2-turbo-local" in dock
    edit = by_id["qwen-image-edit-2509-local"]
    assert edit.capabilityLabel == "Draft"


def test_default_eligible_requires_certified_and_ready():
    for model in list_models():
        if model.defaultEligible:
            assert model.capabilityLabel == "Certified"
            assert model.executable is True
