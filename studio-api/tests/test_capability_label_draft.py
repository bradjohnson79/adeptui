"""Draft is a valid Production Control capabilityLabel — not Certified."""

from app.production_control.contracts import ModelDescriptor


def test_draft_capability_label_constructs():
    model = ModelDescriptor(
        id="qwen-image-edit-2509-local",
        modality="image",
        label="Qwen Image Edit 2509 (Local)",
        locality="local",
        capabilityLabel="Draft",
        executable=False,
    )
    assert model.capabilityLabel == "Draft"
    assert model.executable is False
    assert model.capabilityLabel != "Certified"


def test_catalog_qwen_edit_draft_imports():
    from app.production_control.model_registry import _CATALOG

    qwen_edit = next(item for item in _CATALOG if item.id == "qwen-image-edit-2509-local")
    assert qwen_edit.capabilityLabel == "Draft"
    assert qwen_edit.executable is False
