"""Temporal Continuity capability: VideoChat3 required, InternVideo3 optional."""

from __future__ import annotations

from app.capabilities.models import CapabilityStatus
from app.capabilities.probes import ProbeSnapshot
from app.capabilities.registry import get_definition
from app.capabilities.service import _eval_video_intelligence
from app.codirector.video_intelligence.paths import VIDEOCHAT3_REVISION


def _snapshot(*, videochat3: str, internvideo3: str = "not_installed") -> ProbeSnapshot:
    return ProbeSnapshot(
        setup_components={
            "videochat3_4b": {"status": videochat3, "name": "VideoChat3 4B"},
            "internvideo3_8b": {"status": internvideo3, "name": "InternVideo3 8B"},
        }
    )


def _certified_receipt() -> dict:
    return {
        "ok": True,
        "liveInfer": True,
        "revision": VIDEOCHAT3_REVISION,
        "modelId": "videochat3-4b",
    }


def test_videochat3_checking_with_certify_receipt_is_verified(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.codirector.video_intelligence.certify.load_receipt",
        _certified_receipt,
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.certify.receipt_is_ready",
        lambda receipt=None: True,
    )
    evaluation = _eval_video_intelligence(
        get_definition("codirector.video_intelligence.ready"),
        _snapshot(videochat3="checking", internvideo3="not_installed"),
    )
    assert evaluation.status == CapabilityStatus.LOCALLY_VERIFIED
    assert evaluation.healthy is True
    assert evaluation.details.get("setupStatusDuringCertify") == "checking"
    assert "Not installed" not in (evaluation.message or "")


def test_missing_internvideo3_does_not_degrade_certified_videochat3(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.codirector.video_intelligence.certify.load_receipt",
        _certified_receipt,
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.certify.receipt_is_ready",
        lambda receipt=None: True,
    )
    evaluation = _eval_video_intelligence(
        get_definition("codirector.video_intelligence.ready"),
        _snapshot(videochat3="ready", internvideo3="not_installed"),
    )
    assert evaluation.status == CapabilityStatus.LOCALLY_VERIFIED
    assert evaluation.healthy is True
    assert evaluation.details["optionalDeepReviewInstalled"] is False
    assert evaluation.details["missingOptionalComponentIds"] == ["internvideo3_8b"]
    assert "internvideo3_8b" not in (evaluation.component_ids or ())
    assert "optional" in evaluation.message.lower()


def test_videochat3_disk_only_is_not_locally_verified(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.codirector.video_intelligence.certify.load_receipt",
        lambda: {"ok": False, "liveInfer": False},
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.certify.receipt_is_ready",
        lambda receipt=None: False,
    )
    evaluation = _eval_video_intelligence(
        get_definition("codirector.video_intelligence.ready"),
        _snapshot(videochat3="ready", internvideo3="not_installed"),
    )
    assert evaluation.status == CapabilityStatus.DEGRADED
    assert evaluation.healthy is False
    assert evaluation.reason_code == "MODEL_UNVERIFIED"
    assert "live" in evaluation.message.lower()


def test_batch_video_path_prefers_current_take(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.codirector.video_intelligence.service import _batch_video_path

    seen: list[str] = []

    def _fake_asset_path(_db, asset_id: str):
        seen.append(asset_id)
        return f"C:/takes/{asset_id}.mp4"

    monkeypatch.setattr("app.codirector.video_intelligence.service._asset_path", _fake_asset_path)
    monkeypatch.setattr(
        "app.director_timeline_w46.current_take.current_take_asset_id",
        lambda _batch: "current-take-asset",
    )
    batch = SimpleNamespace(approvedClip=SimpleNamespace(assetId="legacy-approved"))
    assert _batch_video_path(object(), "proj", batch) == "C:/takes/current-take-asset.mp4"
    assert seen == ["current-take-asset"]


def test_missing_videochat3_still_blocks(monkeypatch) -> None:
    evaluation = _eval_video_intelligence(
        get_definition("codirector.video_intelligence.ready"),
        _snapshot(videochat3="not_installed", internvideo3="not_installed"),
    )
    assert evaluation.status in {CapabilityStatus.BLOCKED, CapabilityStatus.NOT_CONFIGURED}
    assert evaluation.healthy is False
    assert "videochat3" in evaluation.message.lower() or "VideoChat3" in evaluation.message
    assert list(evaluation.component_ids or ()) == ["videochat3_4b"]
