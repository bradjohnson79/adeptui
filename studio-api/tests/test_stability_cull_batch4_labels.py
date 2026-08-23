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


def test_illustrious_is_present_and_sensenova_not_default():
    by_id = {m.id: m for m in list_models("image")}
    assert "illustrious-local" in by_id
    assert by_id["sensenova-u15-local"].defaultEligible is False
    assert by_id["sensenova-u15-local"].capabilityLabel != "Certified"


def test_default_eligible_requires_certified_and_ready():
    for model in list_models():
        if model.defaultEligible:
            assert model.capabilityLabel == "Certified"
            assert model.executable is True
