"""M3.0c B19 regression: reject-band approval requires an explicit override."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def test_reject_band_requires_override(monkeypatch):
    from app.codirector.vision import approval as approval_module

    session = MagicMock(reportId="report-b19-separate", assetId=None)
    report = MagicMock(band="reject")
    monkeypatch.setattr(
        approval_module.VisionStore,
        "get_session",
        lambda db, sid, project_id=None: session,
    )
    monkeypatch.setattr(
        approval_module.VisionStore,
        "get_report",
        lambda db, rid, project_id=None: report,
    )

    with pytest.raises(ValueError, match="override"):
        approval_module.record_decision(
            MagicMock(),
            project_id="project-b19-separate",
            session_id="session-b19-separate",
            decision="approved",
            override=False,
        )
