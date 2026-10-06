"""WAVE 6.1 — VerifiedContinuityMemory on live Omni continuity path."""

from __future__ import annotations

from types import SimpleNamespace

from app.codirector.verified_continuity_memory import (
    packet_parse_ok,
    read_verified_continuity,
    record_verified_continuity_from_packet,
    resolve_continuity_keys_from_batch,
)


class _Pkt:
    def __init__(self, *, parse_ok: bool, summary: str, packet_id: str = "pkt1"):
        self.parseOk = parse_ok
        self.summary = summary
        self.packetId = packet_id
        self.characterActions = []
        self.speechSegments = []

    def is_ready(self) -> bool:
        return bool(self.parseOk)


def test_resolve_keys_from_batch_and_master():
    batch = SimpleNamespace(currentTakeId="take_abc", order=1, activeTakeId=None)
    master = SimpleNamespace(revision=3)
    keys = resolve_continuity_keys_from_batch(
        project_id="proj",
        scene_id="scene",
        batch=batch,
        master=master,
    )
    assert keys["take_id"] == "take_abc"
    assert keys["revision"] == "3"
    assert keys["batch_index"] == 1


def test_record_from_packet_writes_vcm_json(tmp_path, monkeypatch):
    monkeypatch.setenv("ADEPT_VERIFIED_CONTINUITY_DIR", str(tmp_path))
    batch = SimpleNamespace(currentTakeId="take_live", order=0, activeTakeId=None)
    master = SimpleNamespace(revision=2)
    pkt = _Pkt(parse_ok=True, summary="Salt flats aerial holds horizon line.")
    rec = record_verified_continuity_from_packet(
        pkt,
        project_id="p-rebuild",
        scene_id="s-salt",
        batch=batch,
        master=master,
    )
    assert rec is not None
    assert rec["parseOk"] is True
    assert any("Salt flats" in f["text"] for f in rec["verifiedFacts"])
    loaded = read_verified_continuity(
        project_id="p-rebuild",
        scene_id="s-salt",
        take_id="take_live",
        revision="2",
        batch_index=0,
    )
    assert loaded is not None
    assert loaded["sourcePacketId"] == "pkt1"
    # File exists on disk
    files = list(tmp_path.rglob("batch_0.json"))
    assert len(files) == 1


def test_record_parse_ok_false_never_canon(tmp_path, monkeypatch):
    monkeypatch.setenv("ADEPT_VERIFIED_CONTINUITY_DIR", str(tmp_path))
    batch = SimpleNamespace(currentTakeId="take_x", order=0)
    master = SimpleNamespace(revision=1)
    pkt = _Pkt(parse_ok=False, summary="Should not canon")
    assert packet_parse_ok(pkt) is False
    rec = record_verified_continuity_from_packet(
        pkt,
        project_id="p",
        scene_id="s",
        batch=batch,
        master=master,
    )
    assert rec["verifiedFacts"] == []
    assert (
        read_verified_continuity(
            project_id="p", scene_id="s", take_id="take_x", revision="1", batch_index=0
        )
        is None
    )


def test_omni_continuity_qc_imports_helper():
    """Wire: continuity QC module contains WAVE 6.1 hook import path."""
    from app.director_timeline_w46.generation import omni_continuity_qc as mod
    import inspect

    src = inspect.getsource(mod.run_omni_continuity_qc)
    assert "record_verified_continuity_from_packet" in src
    assert "WAVE 6.1" in src
