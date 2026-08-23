from app.production_control.model_registry import (
    CATALOG_ONLY_HIDDEN_FROM_PICKER,
    is_ordinary_picker_hidden,
)


def test_catalog_only_families_are_hidden_from_ordinary_picker():
    assert is_ordinary_picker_hidden("cogview-4-local") is True
    assert is_ordinary_picker_hidden("hidream-local") is True
    assert is_ordinary_picker_hidden("flux1-kontext-dev-local") is False
    assert "cogview-4-local" in CATALOG_ONLY_HIDDEN_FROM_PICKER
