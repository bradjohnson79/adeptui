"""ElevenLabs stays on the direct API. Aggregator keys never become the route."""

from app.character_identity.service import provider_voice_binding
from app.hosted_providers.adapters.elevenlabs_adapter import provenance
from app.hosted_providers.elevenlabs_capability import resolve_capability


def test_missing_key_does_not_select_fal(monkeypatch):
    def fake_secret(name: str):
        if name == "fal_api_key":
            return "fal-user-key"
        if name == "kie_api_key":
            return "kie-user-key"
        return None

    monkeypatch.setattr("app.hosted_providers.elevenlabs_capability.get_secret", fake_secret)
    monkeypatch.setattr(
        "app.hosted_providers.elevenlabs_capability.secret_status",
        lambda _name: {"state": "missing", "configured": False},
    )
    result = resolve_capability("elevenlabs.voice")
    assert result["ok"] is False
    assert result["status"] == "unavailable"
    assert result["aggregatorsUsed"] is False
    assert result["selected"] is None


def test_verified_key_selects_direct_elevenlabs(monkeypatch):
    monkeypatch.setattr(
        "app.hosted_providers.elevenlabs_capability.get_secret",
        lambda name: "present" if name == "elevenlabs_api_key" else None,
    )
    monkeypatch.setattr(
        "app.hosted_providers.elevenlabs_capability.secret_status",
        lambda _name: {"state": "verified", "configured": True},
    )
    result = resolve_capability("elevenlabs.sfx")
    assert result["ok"] is True
    assert result["selected"]["providerId"] == "elevenlabs"
    assert result["directApi"] is True
    assert "fal" not in str(result["selected"])


def test_invalid_key_is_not_available(monkeypatch):
    monkeypatch.setattr(
        "app.hosted_providers.elevenlabs_capability.get_secret",
        lambda name: "present" if name == "elevenlabs_api_key" else None,
    )
    monkeypatch.setattr(
        "app.hosted_providers.elevenlabs_capability.secret_status",
        lambda _name: {"state": "invalid", "configured": True},
    )
    result = resolve_capability("elevenlabs.music")
    assert result["ok"] is False
    assert result["status"] == "invalid"


def test_binary_provenance_does_not_invent_provider_asset_id():
    row = provenance(asset_type="sfx", model_id="eleven_text_to_sound_v2", request_id="req-1")
    assert row["provider"] == "elevenlabs"
    assert row["providerAssetType"] == "sfx"
    assert row["providerAssetId"] is None
    assert row["providerRequestId"] == "req-1"
    assert "apiKey" not in row
    assert "elevenlabs_api_key" not in row


def test_character_voice_uses_saved_id_not_display_name():
    voice = {
        "provider": "elevenlabs",
        "name": "Renkoka",
        "lineage": {
            "providerBinding": {
                "provider": "elevenlabs",
                "providerVoiceId": "21m00Tcm4TlvDq8ikWAM",
                "voiceName": "Rachel",
            }
        },
    }
    binding = provider_voice_binding(voice)
    assert binding["providerVoiceId"] == "21m00Tcm4TlvDq8ikWAM"
    assert binding["providerVoiceId"] != "Renkoka"


def test_elevenlabs_generation_module_does_not_call_aggregators():
    from pathlib import Path

    source = Path("app/hosted_providers/adapters/elevenlabs_routed.py").read_text(encoding="utf-8")
    lowered = source.lower()
    assert "api.elevenlabs.io" not in lowered or "direct_el" in source
    for banned in ("fal.ai", "api.kie.ai", "wavespeed.ai", "fal_api_key", "kie_api_key", "wavespeed_api_key"):
        assert banned not in lowered


def test_takes_send_authored_line_to_elevenlabs_and_cap_at_four():
    from pathlib import Path

    from app.voice_performance.m410_schemas import GenerateTakesBody

    source = Path("app/voice_performance/m410_service.py").read_text(encoding="utf-8")
    assert "dialogue_text=row.dialogue_text or \"\"" in source
    assert GenerateTakesBody(count=9).count == 4
    assert GenerateTakesBody(count=0).count == 1


def test_missing_voice_id_does_not_guess_from_name():
    voice = {"provider": "elevenlabs", "name": "Renkoka", "lineage": {}}
    assert provider_voice_binding(voice) is None
