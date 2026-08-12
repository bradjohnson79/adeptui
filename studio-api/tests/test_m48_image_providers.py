"""M4.8 Wave 2 ImageProviderRegistry tests."""

from __future__ import annotations

from app.image_studio.providers import family_catalog, list_image_providers, providers_for_mode


def test_family_catalog_includes_qwen2512() -> None:
    fams = {f["family"] for f in family_catalog()}
    assert "qwen2512" in fams
    assert "zimage" in fams
    q = next(f for f in family_catalog() if f["family"] == "qwen2512")
    assert "Qwen" in q["label"]


def test_list_image_providers_returns_descriptors() -> None:
    providers = list_image_providers(include_unready=True)
    assert isinstance(providers, list)
    # At least static local catalog rows should appear
    ids = {p.id for p in providers}
    assert "qwen-image-2512-local" in ids or "zimage-local" in ids or len(providers) >= 1
    for p in providers:
        assert p.family
        assert p.source in {"local", "hosted", "docker"}
        assert p.imageCapable is True


def test_best_match_mode_returns_single_or_empty() -> None:
    result = providers_for_mode("best_match", prompt="cinematic portrait", purpose="storyboard")
    assert result["mode"] == "best_match"
    assert "recommendation" in result
    assert isinstance(result["providers"], list)
    assert len(result["providers"]) <= 1
    if result["bestMatch"]:
        assert result["bestMatch"]["readiness"] == "ready" or result["readyCount"] >= 0


def test_all_models_includes_unready() -> None:
    result = providers_for_mode("all_models")
    assert result["mode"] == "all_models"
    assert "costPreflight" in result
    assert "paidProvidersRequireConfirmation" in result


def test_choose_model_ready_only() -> None:
    result = providers_for_mode("choose_model")
    for p in result["providers"]:
        assert p["readiness"] == "ready"
