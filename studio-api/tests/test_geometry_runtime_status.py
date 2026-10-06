from __future__ import annotations

from pathlib import Path


def test_moge_source_present_uses_src_layout(tmp_path: Path, monkeypatch):
    from app.spatial_map.geometry import moge2_runtime

    root = tmp_path / "moge2"
    (root / "src" / "moge").mkdir(parents=True)
    monkeypatch.setattr(moge2_runtime, "runtime_root", lambda: root)
    assert moge2_runtime.source_present() is True
    status = moge2_runtime.runtime_status()
    assert status["weightsLicense"] == "unconfirmed"
    assert status["runtimeReady"] is False
    assert status["productionCertified"] is False
    assert "MIT" not in (status.get("weightsLicense") or "")
    assert "Apache" not in (status.get("weightsLicense") or "")


def test_vggt_gated_does_not_block_moge_independence(monkeypatch):
    from app.setup import essential_agreement as ea
    from app.setup.license_metadata import is_model_access_gated

    monkeypatch.setattr(ea, "is_accepted", lambda: True)
    assert is_model_access_gated("vggt_1b_commercial") is True
    moge = ea.independence_gate("moge2_geometry")
    assert moge["ok"] is True
    assert moge["blockedByVggt"] is False
