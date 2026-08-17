"""M42 Multi-Provider Hosted AI Strategy — unit tests (no mock provider success)."""

from __future__ import annotations

from app.codirector.tools.definitions import TOOL_IDS
from app.hosted_providers.capabilities import capability_matrix, provider_supports
from app.hosted_providers.models import list_canonical_models, resolve_model_mapping
from app.hosted_providers.preferences import load_preferences, save_preferences
from app.hosted_providers.registry import PRIORITY_ORDER, list_providers
from app.hosted_providers.resolver import resolve_hosted_provider
from app.hosted_providers.service import catalog, registry_snapshot


def test_recommendation_order():
    assert PRIORITY_ORDER == ("kie", "wavespeed", "fal")
    providers = list_providers()
    assert [p["provider_id"] for p in providers] == ["kie", "wavespeed", "fal"]
    assert providers[0]["recommended"] is True


def test_canonical_models_hide_provider_suffix():
    models = list_canonical_models(include_mappings=False)
    names = {m["displayName"] for m in models}
    assert "FLUX" in names
    assert not any("(" in m["displayName"] for m in models)
    mapping = resolve_model_mapping("FLUX", "kie")
    assert mapping and mapping["providerModelId"]


def test_capability_honesty_fal_video_certified():
    matrix = capability_matrix()
    assert matrix["mock"] is False
    assert matrix["providers"]["fal"]["text_to_video"] == "Certified"
    assert matrix["providers"]["fal"]["image_to_video"] == "Certified"
    # Kie/WaveSpeed generation not yet Certified in Adept queue
    assert matrix["providers"]["kie"]["text_to_video"] in ("Testing", "Available but Uncertified")
    assert provider_supports("fal", "text_to_video", min_status="Certified")
    assert not provider_supports("kie", "text_to_video", min_status="Certified")


def test_automatic_prefers_kie_when_capable():
    save_preferences(preferred_provider="automatic")
    # All verified; capability Testing on kie for t2i
    res = resolve_hosted_provider(
        capability="text_to_image",
        credential_states={"kie": "verified", "wavespeed": "verified", "fal": "verified"},
    )
    assert res["ok"] is True
    assert res["selected"]["providerId"] == "kie"
    assert res["silentSwitchForbidden"] is True
    assert res["mock"] is False


def test_automatic_falls_through_to_fal_for_certified_video():
    save_preferences(preferred_provider="automatic")
    # Only fal is Certified for t2v; kie/wavespeed are Testing so they can still win Automatic
    # if configured — use Available-but-uncertified path by requiring Certified-only via model
    res = resolve_hosted_provider(
        capability="text_to_video",
        canonical_model="Seedance",
        credential_states={"kie": "missing", "wavespeed": "missing", "fal": "verified"},
    )
    assert res["ok"] is True
    assert res["selected"]["providerId"] == "fal"


def test_no_provider_message():
    save_preferences(preferred_provider="automatic")
    res = resolve_hosted_provider(
        capability="relighting",
        credential_states={"kie": "verified", "wavespeed": "verified", "fal": "verified"},
    )
    assert res["ok"] is False
    assert "No certified hosted provider" in res["explanation"]


def test_preferred_does_not_silent_switch():
    save_preferences(preferred_provider="kie")
    res = resolve_hosted_provider(
        capability="text_to_video",
        canonical_model="Runway",  # fal-only mapping
        credential_states={"kie": "verified", "wavespeed": "verified", "fal": "verified"},
    )
    assert res["selected"] is None
    assert res["alternatives"]
    assert res["alternatives"][0]["providerId"] == "fal"
    assert "new execution option" in res["explanation"]


def test_catalog_and_preferences():
    prefs = save_preferences(preferred_provider="wavespeed")
    assert prefs["preferredProvider"] == "wavespeed"
    assert load_preferences()["preferredProvider"] == "wavespeed"
    c = catalog()
    assert c["title"] == "Hosted AI Providers"
    assert c["mock"] is False
    assert len(c["providers"]) == 3
    snap = registry_snapshot()
    assert "FLUX" in {m["modelId"] for m in snap["models"]}


def test_codirector_tools_registered():
    assert "get_cloud_render_status" in TOOL_IDS
    assert "hosted_providers.recommend" in TOOL_IDS


def test_dock_api_models_all_keyed_excludes_adapter_unavailable(monkeypatch) -> None:
    """CDX-080: api_models must not include rows the catalog marks
    adapterAvailable=False / executable=False (e.g. flux-kontext-fal)."""
    from app.hosted_providers import discovery as hp_discovery

    monkeypatch.setattr(hp_discovery, "_verified_provider_ids", lambda: ["fal"])
    payload = hp_discovery.dock_api_models("image", scope="all_keyed")
    rows = payload.get("models") or []
    ids = {str(m.get("id") or "") for m in rows}
    assert "flux-fal" in ids  # adapterAvailable=True row stays
    assert "flux-kontext-fal" not in ids  # adapterAvailable=False row excluded
    assert "nano-banana-2-fal" in ids
    for m in rows:
        assert m.get("adapterAvailable") is True
        assert m.get("executable") is True
        assert m.get("selectable") is True
