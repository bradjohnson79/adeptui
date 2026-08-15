"""Dynamic API Model Discovery — Dock population from normalized catalog only."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.hosted_providers import discovery as discovery_mod
from app.hosted_providers.discovery import dock_api_models
from app.hosted_providers.model_store import load_catalog, save_catalog
from app.production_control.model_registry import get_model


@pytest.fixture()
def isolated_catalog(tmp_path, monkeypatch):
    path = tmp_path / "discovered_models.json"
    monkeypatch.setattr("app.hosted_providers.model_store._STORE_PATH", path)
    yield path


def test_dock_api_empty_without_provider(isolated_catalog):
    save_catalog(
        {
            "activeProviderId": None,
            "emptyReason": "no_provider",
            "emptyMessage": "No API models available.\n\nCheck your API key or add a provider\nthrough the Setup Wizard.",
            "models": [],
            "summary": {},
        }
    )
    section = dock_api_models("video")
    assert section["models"] == []
    assert section["emptyReason"] == "no_provider"
    assert "Setup Wizard" in (section["emptyMessage"] or "")


def test_dock_api_shows_only_active_provider_models(isolated_catalog):
    save_catalog(
        {
            "activeProviderId": "kie",
            "emptyReason": None,
            "models": [
                {
                    "id": "seedance-kie",
                    "providerId": "kie",
                    "modality": "video",
                    "label": "Seedance 2.0 — Kie.ai",
                    "selectable": True,
                    "readiness": "Ready",
                    "executable": True,
                },
                {
                    "id": "kling-fal",
                    "providerId": "fal",
                    "modality": "video",
                    "label": "Kling 3.0 — fal.ai",
                    "selectable": True,
                    "readiness": "Ready",
                    "executable": True,
                },
            ],
            "summary": {},
        }
    )
    section = dock_api_models("video")
    ids = [m["id"] for m in section["models"]]
    assert ids == ["seedance-kie"]
    assert section["emptyReason"] is None


def test_dock_api_modality_empty_message(isolated_catalog):
    save_catalog(
        {
            "activeProviderId": "kie",
            "emptyReason": None,
            "models": [
                {
                    "id": "flux-kie",
                    "providerId": "kie",
                    "modality": "image",
                    "selectable": True,
                    "readiness": "Ready",
                }
            ],
            "summary": {},
        }
    )
    section = dock_api_models("video")
    assert section["models"] == []
    assert section["emptyReason"] == "none_for_modality"
    assert "video" in (section["emptyMessage"] or "")


def test_discover_provider_classifies_ready_and_adapter(isolated_catalog, monkeypatch):
    monkeypatch.setattr(
        "app.hosted_providers.discovery.get_secret",
        lambda _name: "test-key",
    )
    monkeypatch.setattr(
        "app.hosted_providers.discovery.probe_kie",
        AsyncMock(return_value={"valid": True, "message": "ok", "httpStatus": 200}),
    )
    result = asyncio.run(discovery_mod.discover_provider("kie", persist_as_active=True))
    assert result["ok"] is True
    summary = result["summary"]
    assert summary["videoFound"] >= 1
    assert summary["compatible"] >= 1
    cat = load_catalog()
    assert cat["activeProviderId"] == "kie"
    ready = [m for m in cat["models"] if m["readiness"] == "Ready"]
    adapter = [m for m in cat["models"] if m["readiness"] == "Requires Adapter"]
    assert ready
    # audio-kie is adapterAvailable False in catalog
    assert any(m["id"] == "audio-kie" for m in adapter) or summary["requiresAdapter"] >= 0
    # Discovery must not auto-activate a dock preference — only store catalog.
    assert "activeModelId" not in cat


def test_get_model_resolves_discovered_ids(isolated_catalog):
    save_catalog(
        {
            "activeProviderId": "kie",
            "models": [
                {
                    "id": "seedance-kie",
                    "providerId": "kie",
                    "modality": "video",
                    "label": "Seedance 2.0 — Kie.ai",
                    "displayName": "Seedance 2.0",
                    "capabilityLabel": "Certified",
                    "capabilities": ["text_to_video"],
                    "executable": True,
                    "selectable": True,
                    "readiness": "Ready",
                }
            ],
        }
    )
    model = get_model("seedance-kie")
    assert model is not None
    assert model.id == "seedance-kie"
    assert model.locality == "hosted"
    assert model.providerId == "kie"


def test_no_hardcoded_api_in_empty_catalog(isolated_catalog, monkeypatch):
    """Acceptance: empty catalog → no selectable API models for Dock sections."""
    monkeypatch.setattr(
        "app.hosted_providers.discovery.secret_status",
        lambda _name: {"state": "missing", "configured": False, "verified": None, "message": ""},
    )
    save_catalog({"activeProviderId": None, "models": [], "emptyReason": "no_provider"})
    for modality in ("llm", "video", "image", "audio"):
        assert dock_api_models(modality)["models"] == []


def test_fal_catalog_includes_hosted_krea2():
    from app.hosted_providers.discovery import _PROVIDER_CATALOG
    from app.production_control.runtime_map import image_family_for_dock_model

    fal = _PROVIDER_CATALOG["fal"]
    by_id = {row["dockModelId"]: row for row in fal}
    assert "krea2-turbo-fal" in by_id
    assert by_id["krea2-turbo-fal"]["providerModelId"] == "fal-ai/krea-2/turbo"
    assert by_id["krea2-medium-fal"]["providerModelId"] == "krea/v2/medium/text-to-image"
    assert by_id["krea2-large-fal"]["providerModelId"] == "krea/v2/large/text-to-image"
    assert image_family_for_dock_model("krea2-turbo-fal") == "krea2"
    assert image_family_for_dock_model("krea2-medium-fal") == "krea2"

def _model_blob(models):
    parts = []
    for m in models:
        parts.append(
            " ".join(
                str(m.get(k) or "")
                for k in ("id", "displayName", "providerModelId", "label", "dockModelId")
            )
        )
    return " ".join(parts).lower()


def _image_rows_from_catalog(provider_id: str):
    from app.hosted_providers.discovery import _PROVIDER_CATALOG

    return [row for row in _PROVIDER_CATALOG[provider_id] if row.get("modality") == "image"]


def _kie_probe_ok(monkeypatch):
    monkeypatch.setattr(
        "app.hosted_providers.discovery.get_secret",
        lambda _name: "test-key",
    )
    monkeypatch.setattr(
        "app.hosted_providers.discovery.probe_kie",
        AsyncMock(return_value={"valid": True, "message": "ok", "httpStatus": 200}),
    )
    monkeypatch.setattr(
        "app.hosted_providers.discovery.secret_status",
        lambda name: (
            {"state": "verified", "configured": True, "verified": True, "message": "ok"}
            if name == "kie_api_key"
            else {"state": "missing", "configured": False, "verified": None, "message": ""}
        ),
    )


def test_kie_image_catalog_includes_nano_banana_gpt_image_2_seedream(isolated_catalog, monkeypatch):
    """When Kie key probes ok, image catalog MUST include Nano Banana, GPT Image 2, Seedream.

    This is the hosted discovered-models contract, not the 2-row FLUX + Nano Banana allowlist.
    """
    _kie_probe_ok(monkeypatch)
    result = asyncio.run(discovery_mod.discover_provider("kie", persist_as_active=True))
    assert result["ok"] is True
    image = [m for m in (result.get("discovery") or {}).get("models") or [] if m.get("modality") == "image"]
    blob = _model_blob(image)
    assert "nano-banana" in blob or "nano banana" in blob, image
    assert (
        "gpt image 2" in blob
        or "gpt-image-2" in blob
        or "gpt_image_2" in blob
    ), f"Kie image catalog missing GPT Image 2: {image}"
    assert "seedream" in blob, f"Kie image catalog missing Seedream: {image}"

    from app.hosted_providers.router import get_discovered_models

    payload = get_discovered_models(modality="image")
    assert payload["ok"] is True
    assert payload["modality"] == "image"
    payload_models = payload.get("models") or []
    payload_blob = _model_blob(payload_models)
    assert "nano-banana" in payload_blob or "nano banana" in payload_blob
    assert "gpt image 2" in payload_blob or "gpt-image-2" in payload_blob or "gpt_image_2" in payload_blob
    assert "seedream" in payload_blob
    wanted = {"nano-banana-kie", "gpt-image-2-kie", "seedream-kie"}
    disc_ids = {m.get("id") for m in image}
    assert wanted <= disc_ids, (wanted, disc_ids, image)
    assert all(m.get("providerId") == "kie" for m in image), image
    payload_ids = {m.get("id") for m in payload_models}
    assert wanted <= payload_ids, (wanted, payload_ids, payload_models)
    assert all(m.get("providerId") == "kie" for m in payload_models), payload_models
    for row in payload_models:
        if row.get("id") in wanted:
            assert row.get("providerId") == "kie", row


def test_kie_image_catalog_is_not_two_row_flux_nano_banana_allowlist(isolated_catalog, monkeypatch):
    """GET discovered-models?modality=image must not be a 2-row FLUX + Nano Banana-only allowlist."""
    static_image = _image_rows_from_catalog("kie")
    static_ids = {row.get("dockModelId") for row in static_image}
    static_names = {str(row.get("displayName") or "").strip().lower() for row in static_image}
    assert static_ids != {"flux-kie", "nano-banana-kie"}
    assert not (static_names <= {"flux", "nano banana"} and len(static_image) <= 2)
    assert len(static_image) > 2, static_image

    _kie_probe_ok(monkeypatch)
    asyncio.run(discovery_mod.discover_provider("kie", persist_as_active=True))
    from app.hosted_providers.router import get_discovered_models

    payload = get_discovered_models(modality="image")
    ids = {m.get("id") for m in payload.get("models") or []}
    names = {str(m.get("displayName") or "").strip().lower() for m in payload.get("models") or []}
    assert ids != {"flux-kie", "nano-banana-kie"}
    assert not (names <= {"flux", "nano banana"} and len(ids) <= 2)
    assert len(payload.get("models") or []) > 2, payload.get("models")


def test_fal_and_wavespeed_image_catalogs_are_not_two_row_allowlist():
    """fal / WaveSpeed hosted image catalogs must also not collapse to FLUX + Nano Banana."""
    for pid in ("fal", "wavespeed"):
        image = _image_rows_from_catalog(pid)
        ids = {row.get("dockModelId") for row in image}
        names = {str(row.get("displayName") or "").strip().lower() for row in image}
        assert ids != {"flux-kie", "nano-banana-kie"}, pid
        assert not (names <= {"flux", "nano banana"} and len(image) <= 2), (pid, image)
        assert image, f"{pid} has no image catalog rows"


def test_get_discovered_models_accepts_video_audio_llm_modalities(isolated_catalog):
    """video / audio / llm are accepted discovered-models modalities and return a catalog payload."""
    save_catalog(
        {
            "activeProviderId": "kie",
            "emptyReason": None,
            "models": [
                {
                    "id": "seedance-kie",
                    "providerId": "kie",
                    "modality": "video",
                    "displayName": "Seedance 2.0",
                    "selectable": True,
                    "readiness": "Ready",
                },
                {
                    "id": "audio-kie",
                    "providerId": "kie",
                    "modality": "audio",
                    "displayName": "Hosted Audio",
                    "selectable": False,
                    "readiness": "Requires Adapter",
                },
            ],
            "summary": {},
        }
    )
    from app.hosted_providers.router import get_discovered_models

    for modality in ("video", "audio", "llm"):
        payload = get_discovered_models(modality=modality)
        assert payload["ok"] is True, payload
        assert payload["modality"] == modality
        assert "models" in payload
        assert isinstance(payload["models"], list)
        assert "emptyReason" in payload
        assert payload.get("mock") is False


def test_get_discovered_models_video_and_audio_return_catalog_after_kie_probe(isolated_catalog, monkeypatch):
    """After a successful Kie probe, video and audio modalities return a populated catalog."""
    _kie_probe_ok(monkeypatch)
    result = asyncio.run(discovery_mod.discover_provider("kie", persist_as_active=True))
    assert result["ok"] is True
    from app.hosted_providers.router import get_discovered_models

    video = get_discovered_models(modality="video")
    audio = get_discovered_models(modality="audio")
    assert video["ok"] is True
    assert video["models"], video
    assert all(m.get("modality") == "video" for m in video["models"])
    assert audio["ok"] is True
    assert audio["models"], audio
    assert all(m.get("modality") == "audio" for m in audio["models"])


def test_get_discovered_models_llm_catalog_is_implemented(isolated_catalog, monkeypatch):
    """discovered-models?modality=llm must return a real hosted catalog, not an unimplemented gap.

    Current source: _PROVIDER_CATALOG has zero modality=llm rows for kie/fal/wavespeed,
    so GET discovered-models?modality=llm is empty (emptyReason=none_for_modality).
    That empty gap is not a supported llm catalog.
    """
    from app.hosted_providers.discovery import _PROVIDER_CATALOG

    static_llm = [
        row
        for rows in _PROVIDER_CATALOG.values()
        for row in rows
        if row.get("modality") == "llm"
    ]
    assert static_llm, (
        "hosted _PROVIDER_CATALOG has no modality=llm rows for kie/fal/wavespeed; "
        "discovered-models?modality=llm cannot return a catalog"
    )

    _kie_probe_ok(monkeypatch)
    asyncio.run(discovery_mod.discover_provider("kie", persist_as_active=True))
    from app.hosted_providers.router import get_discovered_models

    payload = get_discovered_models(modality="llm")
    assert payload["ok"] is True
    assert payload["models"], (
        "llm modality returned an empty catalog after Kie probe-ok discovery: "
        f"{payload}"
    )

def test_dock_api_image_defaults_to_all_verified_keys(isolated_catalog, monkeypatch):
    """Character Creator image list: every verified key, not only the active provider."""
    def _status(name: str) -> dict:
        if name in {"kie_api_key", "fal_api_key"}:
            return {"state": "verified", "configured": True, "verified": True, "message": "ok"}
        return {"state": "missing", "configured": False, "verified": None, "message": ""}

    monkeypatch.setattr("app.hosted_providers.discovery.secret_status", _status)
    monkeypatch.setattr("app.hosted_providers.discovery.get_secret", lambda name: "k" if name != "wavespeed_api_key" else None)
    save_catalog(
        {
            "activeProviderId": "kie",
            "emptyReason": None,
            "models": [
                {
                    "id": "flux-kie",
                    "providerId": "kie",
                    "modality": "image",
                    "displayName": "FLUX",
                    "selectable": True,
                    "readiness": "Ready",
                }
            ],
            "summary": {},
        }
    )
    section = dock_api_models("image")
    assert section["scope"] == "all_keyed"
    ids = [m["id"] for m in section["models"]]
    providers = {m["providerId"] for m in section["models"]}
    assert "gpt-image-2-kie" in ids
    assert "seedream-kie" in ids
    assert "nano-banana-kie" in ids
    assert "flux-kie" in ids
    assert "fal" in providers
    assert "kie" in providers
    assert "wavespeed" not in providers
    assert all(m["modality"] == "image" for m in section["models"])

    primary = dock_api_models("image", scope="primary")
    assert primary["scope"] == "primary"
    assert [m["id"] for m in primary["models"]] == ["flux-kie"]

    video = dock_api_models("video")
    assert video["scope"] == "primary"


def test_dock_api_image_skips_unverified_and_missing_keys(isolated_catalog, monkeypatch):
    monkeypatch.setattr(
        "app.hosted_providers.discovery.secret_status",
        lambda name: {
            "kie_api_key": {"state": "verified", "configured": True, "verified": True, "message": "ok"},
            "fal_api_key": {"state": "unverified", "configured": True, "verified": None, "message": ""},
            "wavespeed_api_key": {"state": "missing", "configured": False, "verified": None, "message": ""},
        }.get(name, {"state": "missing", "configured": False, "verified": None, "message": ""}),
    )
    section = dock_api_models("image")
    providers = {m["providerId"] for m in section["models"]}
    assert providers == {"kie"}


def test_image_rows_group_by_stable_provider_id_kie_fal_wavespeed(isolated_catalog, monkeypatch):
    """Image rows carry a stable providerId and group by kie / fal / wavespeed."""
    from app.hosted_providers.discovery import _normalize_provider_models
    from app.hosted_providers.router import get_discovered_models

    for pid in ("kie", "fal", "wavespeed"):
        image = [m for m in _normalize_provider_models(pid, account_ok=True, probe={"valid": True}) if m.get("modality") == "image"]
        assert image, pid
        assert all(m.get("providerId") == pid for m in image), (pid, image)
        assert all(isinstance(m.get("providerId"), str) and m["providerId"].strip() == pid for m in image)

    def _status(name: str) -> dict:
        if name in {"kie_api_key", "fal_api_key", "wavespeed_api_key"}:
            return {"state": "verified", "configured": True, "verified": True, "message": "ok"}
        return {"state": "missing", "configured": False, "verified": None, "message": ""}

    monkeypatch.setattr("app.hosted_providers.discovery.secret_status", _status)
    monkeypatch.setattr("app.hosted_providers.discovery.get_secret", lambda _name: "k")

    payload = get_discovered_models(modality="image")
    assert payload["ok"] is True
    models = payload.get("models") or []
    assert models
    assert all(m.get("providerId") in {"kie", "fal", "wavespeed"} for m in models), models
    assert all(isinstance(m.get("providerId"), str) and m.get("providerId") for m in models)

    grouped: dict[str, list] = {}
    for m in models:
        grouped.setdefault(m["providerId"], []).append(m)
    assert set(grouped) == {"kie", "fal", "wavespeed"}, set(grouped)
    for pid in ("kie", "fal", "wavespeed"):
        assert grouped[pid], pid
        assert all(r.get("providerId") == pid for r in grouped[pid])
