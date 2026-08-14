from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def isolated_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    return tmp_path


def test_build_install_plan_requires_dual_confirm_for_large_models(isolated_lifecycle: Path) -> None:
    from app.setup.lifecycle.service import build_install_plan

    plan = build_install_plan("qwen_image_2512_models")

    assert plan.requiresRuntimeConfirmation is True
    assert plan.requiresModelDownloadConfirmation is True
    assert plan.action == "install"


def test_recipe_lookup_prefers_component_recipe(isolated_lifecycle: Path) -> None:
    from app.setup.lifecycle.service import recipe_for_component

    recipe = recipe_for_component("index_tts2")

    assert recipe is not None
    assert recipe.componentId == "index_tts2"
    assert recipe.recipeId == "index_tts2.local.certified"


def test_calibrate_and_certify_persist_record(
    isolated_lifecycle: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.setup.lifecycle.service import certify_component, get_certification

    monkeypatch.setattr(
        "app.setup.lifecycle.service.verify_component",
        lambda component_id: type(
            "Verification",
            (),
            {"healthy": True, "summary": "Ready", "version": "2026.08"},
        )(),
    )

    record = certify_component("qwen_image_2512_models")
    saved = get_certification("qwen_image_2512_models")

    assert record.certified is True
    assert saved is not None
    assert saved.certified is True
    assert saved.calibration is not None
    assert saved.status == "ready"


def test_check_updates_uses_certified_recipe_only(
    isolated_lifecycle: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.setup.lifecycle.models import ProviderCertificationRecord
    from app.setup.lifecycle.service import _now, _save_certifications, check_updates

    _save_certifications(
        {
            "index_tts2": ProviderCertificationRecord(
                componentId="index_tts2",
                componentName="IndexTTS2",
                status="ready",
                certified=True,
                certifiedVersion="2026.07",
                certifiedDate="2026-07-15T00:00:00+00:00",
                recipeId="index_tts2.local.certified",
                createdAt=_now(),
                updatedAt=_now(),
            )
        }
    )

    result = check_updates("index_tts2")

    assert result["updateAvailable"] is True
    assert result["latestCertifiedVersion"] == "2026.08"


def test_monitor_status_reports_drift_for_certified_components(
    isolated_lifecycle: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.setup.lifecycle.models import ProviderCertificationRecord
    from app.setup.lifecycle.service import _now, _save_certifications, get_monitor_status

    _save_certifications(
        {
            "qwen_image_2512_models": ProviderCertificationRecord(
                componentId="qwen_image_2512_models",
                componentName="Qwen-Image-2512 Models",
                status="ready",
                certified=True,
                certifiedVersion="2026.08",
                certifiedDate="2026-08-01T00:00:00+00:00",
                recipeId="qwen_image_2512_models.local.certified",
                createdAt=_now(),
                updatedAt=_now(),
            )
        }
    )
    monkeypatch.setattr(
        "app.setup.lifecycle.service.verify_component",
        lambda component_id: type(
            "Verification",
            (),
            {"healthy": False, "summary": "Missing required files", "version": "2026.08"},
        )(),
    )

    result = get_monitor_status()

    assert result["count"] == 1
    assert result["items"][0]["componentId"] == "qwen_image_2512_models"
    assert "Missing required files" in result["items"][0]["findings"][0]["message"]


def test_archive_component_marks_record_archived(
    isolated_lifecycle: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.setup.lifecycle.service import archive_component

    monkeypatch.setattr(
        "app.setup.lifecycle.service.verify_component",
        lambda component_id: type(
            "Verification",
            (),
            {"healthy": True, "summary": "Ready", "version": "2026.08"},
        )(),
    )

    record = archive_component("index_tts2")

    assert record.status == "archived"


def test_preview_install_does_not_execute_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.tools.handlers import setup_guided

    called = {"install": False}

    monkeypatch.setattr(
        "app.setup.lifecycle.service.install_component",
        lambda *args, **kwargs: called.__setitem__("install", True),
    )

    preview = setup_guided.preview_install_component(None, {"componentId": "index_tts2"})  # type: ignore[arg-type]

    assert "Source Manager" in preview.summary
    assert called["install"] is False




def _search_ids(query: str) -> set[str]:
    from app.setup.lifecycle.service import search_components

    return {item["componentId"] for item in search_components(query)["items"]}


def _search_reasons(query: str) -> dict[str, str]:
    from app.setup.lifecycle.service import search_components

    return {item["componentId"]: item["reason"] for item in search_components(query)["items"]}


def test_search_photoreal_character_keeps_kontext(isolated_lifecycle: Path) -> None:
    ids = _search_ids("photoreal character")
    reasons = _search_reasons("photoreal character")
    assert "flux1_kontext_dev_local" in ids
    assert "photoreal character" in reasons["flux1_kontext_dev_local"].lower()


def test_search_anime_poster_hits_image_anime_path(isolated_lifecycle: Path) -> None:
    ids = _search_ids("anime poster")
    reasons = _search_reasons("anime poster")
    assert {"sana_15_local", "qwen_image_2512_models"} & ids
    anime_hit = next(component_id for component_id in ("sana_15_local", "qwen_image_2512_models") if component_id in reasons)
    assert "anime" in reasons[anime_hit].lower()


def test_search_fast_preview_hits_schnell(isolated_lifecycle: Path) -> None:
    ids = _search_ids("fast preview")
    reasons = _search_reasons("fast preview")
    assert "flux1_schnell_local" in ids
    assert "preview" in reasons["flux1_schnell_local"].lower()


def test_search_short_film_hits_hunyuan(isolated_lifecycle: Path) -> None:
    ids = _search_ids("Make a short film")
    reasons = _search_reasons("Make a short film")
    assert "hunyuan_video_15" in ids
    assert "short-film" in reasons["hunyuan_video_15"].lower()
    assert "fal_key" not in ids


def test_search_commercial_hits_wan_not_fal_key(isolated_lifecycle: Path) -> None:
    ids = _search_ids("Make a commercial")
    reasons = _search_reasons("Make a commercial")
    assert "wan_models" in ids
    assert "fal_key" not in ids
    assert "commercial" in reasons["wan_models"].lower()
    assert "fal_key" not in _search_ids("commercial")


def test_search_branded_product_video_differs_from_commercial(isolated_lifecycle: Path) -> None:
    branded = _search_ids("Make a branded product video")
    commercial = _search_ids("Make a commercial")
    assert "wan_models" in branded
    assert "flux1_dev_local" in branded
    assert "fal_key" not in branded
    assert branded != commercial


def test_search_anime_episode_uses_video_and_image_anime(isolated_lifecycle: Path) -> None:
    ids = _search_ids("Make an anime episode")
    assert {"sana_15_local", "qwen_image_2512_models", "zimage_models"} & ids
    assert "hunyuan_video_15" in ids


def test_search_talking_presenter_hits_longcat(isolated_lifecycle: Path) -> None:
    ids = _search_ids("Create a talking presenter")
    reasons = _search_reasons("Create a talking presenter")
    assert "longcat-video-avatar-1-5-local" in ids
    assert "talking presenter" in reasons["longcat-video-avatar-1-5-local"].lower()


def test_search_storyboard_uses_existing_previs_ids(isolated_lifecycle: Path) -> None:
    ids = _search_ids("Make a storyboard")
    reasons = _search_reasons("Make a storyboard")
    assert {"flux1_dev_local", "pack_essential_cinematic", "ltx_checkpoint"} & ids
    storyboard_hit = next(
        component_id
        for component_id in ("flux1_dev_local", "pack_essential_cinematic", "ltx_checkpoint")
        if component_id in reasons
    )
    assert "storyboard" in reasons[storyboard_hit].lower()


def test_production_intent_recommendations_differ(isolated_lifecycle: Path) -> None:
    queries = [
        "Make a short film",
        "Make a commercial",
        "Make a branded product video",
        "Make an anime episode",
        "Create a talking presenter",
        "Make a storyboard",
    ]
    id_sets = [tuple(sorted(_search_ids(query))) for query in queries]
    assert len(set(id_sets)) == len(queries)
    reasons = [_search_reasons(query) for query in queries]
    primary = [
        reasons[0].get("hunyuan_video_15"),
        reasons[1].get("wan_models"),
        reasons[2].get("flux1_dev_local"),
        reasons[3].get("sana_15_local"),
        reasons[4].get("longcat-video-avatar-1-5-local"),
        reasons[5].get("flux1_dev_local") or reasons[5].get("pack_essential_cinematic") or reasons[5].get("ltx_checkpoint"),
    ]
    assert all(primary)
    assert len(set(primary)) == len(primary)


def test_search_status_label_comes_from_lifecycle_state(
    isolated_lifecycle: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.setup.diagnostics import Verification
    from app.setup.lifecycle.service import lifecycle_state, search_components

    monkeypatch.setattr(
        "app.setup.lifecycle.service.verify_component",
        lambda component_id: Verification(
            healthy=True,
            absent=False,
            issue_code=None,
            summary="Ready",
            version="2026.08",
        ),
    )
    result = search_components("Make a short film")
    assert result["items"]
    for item in result["items"]:
        state = lifecycle_state(item["componentId"])
        assert item["statusLabel"] == state.statusLabel
        assert item["statusLabel"] == "Ready"
