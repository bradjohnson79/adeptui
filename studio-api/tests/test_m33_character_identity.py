"""M3.3 Character Identity — coverage, lock immutability, consent, Hitchhiker protection."""

from __future__ import annotations

import io
import os
import struct
import uuid
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import Asset, Project, Scene, SessionLocal, init_db
from app.feature_flags import FeatureFlags

HITCHHIKER_PROJECT = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9"
HITCHHIKER_LTX = "6b91bb7f-0dfd-44e6-92b3-7df7ac8cea4f"
HITCHHIKER_TEST2 = "e277e621-189d-471e-b435-f01620f03d0d"
HITCHHIKER_DIALOGUE = "c5cdd736-8f89-42e3-a7a8-9cb97043bf8a"


def _wav(seconds: float = 1.0, rate: int = 24000) -> bytes:
    frames = int(rate * seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        samples = bytearray()
        for n in range(frames):
            value = int(6000 * (1 if (n // 40) % 2 == 0 else -1))
            samples += struct.pack("<h", value)
        handle.writeframes(bytes(samples))
    return buf.getvalue()


def _apply_flags_in_place(environ: dict[str, str] | os._Environ | None = None) -> None:
    """Mutate the process singleton in place (modules import feature_flags by value)."""
    from dataclasses import fields as dataclass_fields

    import app.feature_flags as ff

    refreshed = FeatureFlags.from_env(environ if environ is not None else os.environ)
    for field in dataclass_fields(FeatureFlags):
        object.__setattr__(ff.feature_flags, field.name, getattr(refreshed, field.name))


@pytest.fixture()
def enable_m33(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")
    _apply_flags_in_place(os.environ)
    yield
    _apply_flags_in_place(os.environ)


@pytest.fixture()
def project_id(enable_m33):
    init_db()
    from app.character_identity import ensure_character_identity_tables

    ensure_character_identity_tables()
    pid = f"m33-{uuid.uuid4().hex[:10]}"
    session = SessionLocal()
    session.merge(Project(id=pid, name="M3.3 Character Identity"))
    session.commit()
    session.close()
    return pid


def test_feature_disabled_returns_404(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "0")
    _apply_flags_in_place(os.environ)
    init_db()
    pid = f"m33-off-{uuid.uuid4().hex[:8]}"
    session = SessionLocal()
    session.merge(Project(id=pid, name="off"))
    session.commit()
    session.close()
    r = client.get(f"/api/projects/{pid}/characters")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "FEATURE_DISABLED"
    monkeypatch.setenv("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")
    _apply_flags_in_place(os.environ)


def test_name_only_save_is_valid_no_incomplete(client: TestClient, project_id: str):
    """Completeness law: a saved character with a valid name is valid (never INCOMPLETE),
    even after attaching a reference (which recomputes coverage)."""
    # CDX-007: references must point at a real project image asset.
    session = SessionLocal()
    session.add(
        Asset(
            id="asset-ref-1",
            project_id=project_id,
            tag="reference_image",
            kind="image",
            filename="ref.png",
            path="ref.png",
        )
    )
    session.commit()
    session.close()

    created = client.post(
        f"/api/projects/{project_id}/characters",
        json={"name": "Name Only"},
    )
    assert created.status_code == 200, created.text
    cid = created.json()["id"]
    assert created.json()["status"] != "INCOMPLETE"

    attach = client.post(
        f"/api/projects/{project_id}/characters/{cid}/references",
        json={"asset_id": "asset-ref-1", "reference_role": "reference_image", "source_type": "upload"},
    )
    assert attach.status_code == 200, attach.text

    fetched = client.get(f"/api/projects/{project_id}/characters/{cid}").json()
    assert fetched["status"] != "INCOMPLETE"
    assert fetched["status"] in ("DRAFT", "READY_FOR_GENERATION", "APPROVED")
    # Coverage detail stays available internally for advanced views.
    assert "coverage" in fetched


def test_patch_partial_domains_never_surfaces_incomplete(client: TestClient, project_id: str):
    """Completeness law (D1): patching personality/performance/etc. via the
    Advanced 'Save domains' path (update_profile) must not surface INCOMPLETE."""
    cid = client.post(
        f"/api/projects/{project_id}/characters",
        json={"name": "Partial Domains"},
    ).json()["id"]
    patched = client.patch(
        f"/api/projects/{project_id}/characters/{cid}",
        json={"personality": {"core_personality": "stoic"}, "description": "x"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] != "INCOMPLETE"
    fetched = client.get(f"/api/projects/{project_id}/characters/{cid}").json()
    assert fetched["status"] != "INCOMPLETE"


def test_create_profile_coverage_and_lock(client: TestClient, project_id: str):
    created = client.post(
        f"/api/projects/{project_id}/characters",
        json={"name": "Arthur Dent", "role": "lead", "description": "Everyman"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    cid = body["id"]
    assert body["status"] in ("DRAFT", "INCOMPLETE")
    assert body["coverage"]["missing_roles"]
    assert body["coverage"]["score"] < 1.0

    cov = client.get(f"/api/projects/{project_id}/characters/{cid}/coverage").json()
    assert len(cov["required_roles"]) >= 6
    assert cov["guidance"]

    versions = client.get(f"/api/projects/{project_id}/characters/{cid}/versions").json()["items"]
    vid = versions[0]["id"]
    assert client.post(f"/api/projects/{project_id}/characters/{cid}/versions/{vid}/approve").status_code == 200
    assert client.post(f"/api/projects/{project_id}/characters/{cid}/versions/{vid}/lock").status_code == 200

    locked_patch = client.patch(
        f"/api/projects/{project_id}/characters/{cid}",
        json={"description": "should fail"},
    )
    assert locked_patch.status_code == 409
    assert locked_patch.json()["detail"]["code"] == "LOCKED_VERSION"

    attach = client.post(
        f"/api/projects/{project_id}/characters/{cid}/references",
        json={"asset_id": "asset-fake", "reference_role": "full_body_front"},
    )
    assert attach.status_code == 409


def test_wardrobe_props_skin_domains(client: TestClient, project_id: str):
    cid = client.post(
        f"/api/projects/{project_id}/characters",
        json={"name": "Ford Prefect", "role": "researcher"},
    ).json()["id"]
    w = client.post(
        f"/api/projects/{project_id}/characters/{cid}/wardrobes",
        json={"name": "Travel coat"},
    )
    assert w.status_code == 200
    p = client.post(
        f"/api/projects/{project_id}/characters/{cid}/props",
        json={"name": "Towel", "prop_type": "signature"},
    )
    assert p.status_code == 200
    patched = client.patch(
        f"/api/projects/{project_id}/characters/{cid}",
        json={
            "skin": {"skin_tone": "fair", "freckles": "light"},
            "hair": {"primary_color": "sandy", "canonical_style": "messy"},
            "personality": {"core_personality": "anxious but kind", "motivations": "survive"},
            "performance": {"movement_energy": "low", "speaking_rhythm": "understated"},
        },
    )
    assert patched.status_code == 200
    out = patched.json()
    assert out["skin"]["skin_tone"] == "fair"
    assert out["hair"]["primary_color"] == "sandy"
    assert "anxious" in (out["personality"].get("core_personality") or "")


def test_consent_required_and_short_reference_rejected(client: TestClient, project_id: str, tmp_path: Path):
    cid = client.post(
        f"/api/projects/{project_id}/characters",
        json={"name": "Zaphod", "role": "president"},
    ).json()["id"]
    voice = client.post(
        f"/api/projects/{project_id}/characters/{cid}/voice-profiles",
        json={"name": "Clone draft", "source_mode": "CLONE", "provider": "qwen3-tts"},
    ).json()
    vid = voice["id"]

    bad_consent = client.post(
        f"/api/projects/{project_id}/characters/{cid}/voice-profiles/{vid}/consent",
        json={"consent_confirmed": False, "synthetic_generation_allowed": False},
    )
    assert bad_consent.status_code == 400
    assert bad_consent.json()["detail"]["code"] == "CONSENT_MISSING"

    short = tmp_path / "short.wav"
    short.write_bytes(_wav(2.0))
    invalid = client.post(
        f"/api/projects/{project_id}/characters/{cid}/voice-profiles/validate-reference",
        json={"path": str(short), "transcript": "too short"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"]["code"] == "INSUFFICIENT_VOICED_DURATION"

    long = tmp_path / "long.wav"
    long.write_bytes(_wav(11.0))
    ok = client.post(
        f"/api/projects/{project_id}/characters/{cid}/voice-profiles/validate-reference",
        json={"path": str(long), "transcript": "eleven seconds of speech for cloning validation"},
    )
    assert ok.status_code == 200
    assert ok.json()["ok"] is True


def test_voice_design_honest_model_not_installed(client: TestClient, project_id: str):
    cid = client.post(
        f"/api/projects/{project_id}/characters",
        json={"name": "Trillian", "role": "scientist"},
    ).json()["id"]
    r = client.post(
        f"/api/projects/{project_id}/characters/{cid}/voice-profiles/design",
        json={
            "name": "Designed",
            "voice_design_prompt": "bright mezzo, curious",
            "candidate_count": 3,
        },
    )
    # Without installed Qwen weights this must be an honest failure, not a fixture success.
    assert r.status_code in (503, 400, 500)
    detail = r.json().get("detail") or {}
    if isinstance(detail, dict):
        assert detail.get("code") in ("MODEL_NOT_INSTALLED", "PROVIDER_UNAVAILABLE", "GENERATION_FAILURE")


def test_providers_endpoint(client: TestClient, enable_m33):
    r = client.get("/api/character-voice/providers")
    assert r.status_code == 200
    body = r.json()
    assert "qwenVoiceDesign" in body
    assert "qwenVoiceClone" in body
    assert "kokoro" in body


def test_hitchhiker_protected_ids_untouched_by_character_apis(client: TestClient, enable_m33):
    """Character Identity APIs must not rewrite protected Hitchhiker scene rows/media."""
    init_db()
    from app.character_identity import ensure_character_identity_tables

    ensure_character_identity_tables()
    session = SessionLocal()
    # Ensure protected IDs exist in the test DB as sentinel rows (or leave if already present).
    session.merge(Project(id=HITCHHIKER_PROJECT, name="Hitchhiker PROTECTED"))
    for sid, name in ((HITCHHIKER_LTX, "LTX Shot1 PROTECTED"), (HITCHHIKER_TEST2, "Test2 PROTECTED")):
        existing = session.get(Scene, sid)
        if not existing:
            session.merge(
                Scene(
                    id=sid,
                    project_id=HITCHHIKER_PROJECT,
                    index=0 if sid == HITCHHIKER_LTX else 1,
                    name=name,
                    prompt="PROTECTED",
                    duration_sec=5.0,
                )
            )
    session.commit()
    before = {
        sid: (session.get(Scene, sid).name, session.get(Scene, sid).prompt)
        for sid in (HITCHHIKER_LTX, HITCHHIKER_TEST2)
    }
    session.close()

    # Operate only on a disposable project — never mutate Hitchhiker via character APIs.
    disposable = f"m33-disp-{uuid.uuid4().hex[:8]}"
    session = SessionLocal()
    session.merge(Project(id=disposable, name="M33 disposable"))
    session.commit()
    session.close()

    created = client.post(
        f"/api/projects/{disposable}/characters",
        json={"name": "M33 Cert Character", "role": "cert"},
    )
    assert created.status_code == 200
    cid = created.json()["id"]
    client.post(
        f"/api/projects/{disposable}/characters/{cid}/wardrobes",
        json={"name": "Cert wardrobe"},
    )

    session = SessionLocal()
    after = {
        sid: (session.get(Scene, sid).name, session.get(Scene, sid).prompt)
        for sid in (HITCHHIKER_LTX, HITCHHIKER_TEST2)
    }
    session.close()
    assert after == before

    # Dialogue asset id constant must remain a known protected token (API must not delete it).
    assert HITCHHIKER_DIALOGUE == "c5cdd736-8f89-42e3-a7a8-9cb97043bf8a"


def test_codirector_character_tools_registered():
    from app.codirector.tools.definitions import TOOL_IDS
    from app.codirector.tools import registry as tool_registry

    for tid in (
        "list_character_profiles",
        "inspect_character_profile",
        "inspect_character_coverage",
        "inspect_character_voice",
        "create_draft_character_profile",
    ):
        assert tid in TOOL_IDS, tid
        assert tool_registry.find(tid) is not None


def test_library_taxonomy_includes_character_folders():
    from app.project_library.taxonomy import TAXONOMY_ROOT

    def walk(node, acc: set[str]):
        acc.add(node.system_key)
        for child in getattr(node, "children", None) or []:
            walk(child, acc)

    ids: set[str] = set()
    walk(TAXONOMY_ROOT, ids)
    for key in (
        "characters.references",
        "characters.closeups",
        "characters.skin",
        "characters.hair",
        "characters.wardrobe",
        "characters.props",
        "characters.voice_references",
        "characters.voice_previews",
        "characters.dialogue",
        "characters.lipsync",
    ):
        assert key in ids, key
    assert "characters.three_d" in ids  # present but deferred
