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

