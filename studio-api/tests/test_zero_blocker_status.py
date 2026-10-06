"""Zero-blocker Setup / System Status aggregation law."""

from __future__ import annotations

from app.readiness.contract import apply_files_ready_gate
from app.setup.catalog import public_components


def test_public_setup_excludes_obsolete_wonder3d() -> None:
    ids = {item.id for item in public_components()}
    assert "wonder3d_multiview" not in ids
    assert "wan_models" not in ids
    assert "infinitetalk-local" not in ids


def test_pathless_ready_kinds_do_not_false_error() -> None:
    assert apply_files_ready_gate("ready", None, kind="local_service") == "ready"
    assert apply_files_ready_gate("ready", None, kind="detect_only") == "ready"
    assert apply_files_ready_gate("ready", None) == "error"


def test_setup_counts_treat_optional_gaps_as_non_blocking() -> None:
    from app.setup.status import build_status

    payload = build_status(persist=False)
    counts = payload["counts"]
    required = [item for item in payload["components"] if item["required"]]
    optional = [item for item in payload["components"] if not item["required"]]
    assert counts["not_installed"] == sum(
        item["status"] in ("not_installed", "download_unavailable") for item in required
    )
    assert counts["needs_attention"] == sum(item["status"] == "error" for item in required)
    assert counts["optional_not_installed"] == sum(
        item["status"] in ("not_installed", "download_unavailable") for item in optional
    )
    assert "wonder3d_multiview" not in {item["id"] for item in payload["components"]}
    if counts["required_needs_attention"] == 0 and counts["required_not_installed"] == 0:
        assert payload["overall_status"] in ("ready", "preparing")
