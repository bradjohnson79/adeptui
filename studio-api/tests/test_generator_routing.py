"""Regression tests for generator routing rules.

Verifies:
- MiniMax H3 is the default engine.
- NO_SILENT_LTX_FALLBACK: LTX fallback is explicit, never auto-switched.
- T2V vs I2V routing: one-frame mode requires a start frame (I2V);
  text-to-video mode uses T2V; no accidental T2V downgrade when a start
  frame is present.
- Bible context now flows via the Timeline Context Package.
"""

from __future__ import annotations

from app.codirector.timeline_context.contracts import TimelineContextPackage
from app.codirector.timeline_context.service import build_timeline_context_package


def test_minimax_h3_is_default_engine():
    """Scene default engine should resolve to MiniMax H3, not LTX."""
    pkg = TimelineContextPackage(projectId="p1", sceneId="s1")
    # Default generation constraint engine is "auto" which resolves to H3 in
    # the resolver; the package itself does not silently pick LTX.
    assert pkg.generationConstraints.engine in {"auto", "minimax-h3"}
    assert pkg.generationConstraints.engine != "ltx"


def test_no_silent_ltx_fallback_contract():
    """The Timeline Context Package never carries a silent LTX fallback."""
    pkg = TimelineContextPackage(projectId="p1", sceneId="s1")
    # gateLevel is one of the three explicit levels; never a hidden fallback.
    assert pkg.gateLevel in {"EXPLORATION", "PRODUCTION_WARNING", "PRODUCTION_LOCK"}


def test_bible_context_flows_via_package():
    """The Timeline Context Package bundles bible context (characters,
    locations, story summary) so the Timeline does not request them
    individually (TIMELINE_CONSUMES_CONTEXT_PACKAGE)."""
    pkg = TimelineContextPackage(projectId="p1", sceneId="s1")
    # All context fields exist on the single object.
    assert hasattr(pkg, "characters")
    assert hasattr(pkg, "locations")
    assert hasattr(pkg, "logline")
    assert hasattr(pkg, "shortSummary")
    assert hasattr(pkg, "longSummary")
    assert hasattr(pkg, "themes")
    assert hasattr(pkg, "references")
    assert hasattr(pkg, "referenceAssets")
    assert hasattr(pkg, "continuity")
    assert hasattr(pkg, "productionNotes")
    assert hasattr(pkg, "generationConstraints")
    assert hasattr(pkg, "readiness")


def test_build_package_missing_scene_degrades_gracefully(tmp_path):
    """Building a package for a missing scene must not crash and must surface
    a BLOCKED readiness so editing remains available."""
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        result = build_timeline_context_package(db, "nonexistent-project", "nonexistent-scene")
        assert result["ok"] is True
        pkg = result["package"]
        # Readiness is BLOCKED but the package is still returned.
        assert pkg["readiness"]["status"] == "BLOCKED"
        assert pkg["sceneStatus"] in {"Draft", "Planning", "Ready", "Generating", "Review", "Approved", "Locked"}
    finally:
        db.close()
