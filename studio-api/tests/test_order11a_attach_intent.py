"""Order 11A — CD attach intent: Timeline visual/background, not ERS lecture."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
ATTACH_INTENT = ROOT / "app" / "codirector" / "conversation" / "attach_intent.py"


def _load_attach_intent():
    name = "order11a_attach_intent"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ATTACH_INTENT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_cafe_photo_as_background_is_timeline_background_ref():
    m = _load_attach_intent()
    r = m.classify_attach_intent(
        "Use this café photo as the background for Schnick Coffee @Korri",
        mime_type="image/jpeg",
    )
    assert r.intent == "timeline_background_ref"
    assert r.role == "background"
    assert r.suppress_ers_lecture is True
    assert r.propose_timeline_attach is True


def test_timeline_visual_language():
    m = _load_attach_intent()
    r = m.classify_attach_intent(
        "Keep this as a Timeline visual reference for the set",
        mime_type="image/png",
    )
    assert r.intent == "timeline_visual_ref"
    assert r.suppress_ers_lecture is True


def test_ordinary_image_defaults_to_reference_image_not_ers_not_attach():
    """Intelligence mission RC8 (2026-09-19): attachment existence alone does not
    decide a Timeline action. A bare image is a referenced image — never ERS
    lecture bait and never an automatic attach proposal."""
    m = _load_attach_intent()
    r = m.classify_attach_intent("here is a photo", mime_type="image/jpeg")
    assert r.intent == "reference_image"
    assert r.suppress_ers_lecture is True
    assert r.propose_timeline_attach is False


def test_discussion_language_on_image_is_visual_discussion():
    """Intelligence mission RC8 / Probe 9: 'I like the lighting in this. What do
    you think?' is visual conversation — no Timeline attach proposal."""
    m = _load_attach_intent()
    r = m.classify_attach_intent(
        "I like the lighting in this café photo. What do you think?",
        mime_type="image/jpeg",
    )
    assert r.intent == "visual_discussion"
    assert r.propose_timeline_attach is False
    assert r.suppress_ers_lecture is True


def test_explicit_ers_still_routes_to_sheet_validate():
    m = _load_attach_intent()
    r = m.classify_attach_intent(
        "Please generate an ERS / environment reference sheet for this location",
        mime_type="image/jpeg",
    )
    assert r.intent == "ers_sheet_validate"
    assert r.suppress_ers_lecture is False


def test_dual_layer_reply_has_companion_and_916_plan_and_tags():
    m = _load_attach_intent()
    r = m.classify_attach_intent(
        "Use as background @Korri @Cade — Schnick Coffee comedy beat",
        mime_type="image/jpeg",
    )
    handoff = m.build_timeline_attach_handoff(
        asset_ids=["asset-cafe-1"],
        intent=r,
        scene_id="scene-1",
    )
    assert handoff["approvalRequired"] is True
    assert handoff["silentMutation"] is False
    assert handoff["toolId"] in {
        "timeline.attach_optional_reference",
        "references.attach",
    }
    reply = m.build_dual_layer_attach_reply(
        "Use as background @Korri @Cade — Schnick Coffee comedy beat",
        r,
        handoff=handoff,
    )
    assert "@Korri" in reply
    assert "9:16" in reply
    assert "background" in reply.lower()
    assert "ERS" in reply or "Environment Reference Sheet" in reply


def test_long_screenplay_plus_attachment_flagged():
    m = _load_attach_intent()
    screenplay = (
        "FADE IN:\nINT. SCHNICK COFFEE - DAY\n"
        + ("Korri and Cade banter over espresso. " * 40)
        + "\nUse the attached café photo as the look of the place / background."
    )
    r = m.classify_attach_intent(screenplay, mime_type="image/jpeg")
    assert r.intent == "timeline_background_ref"
    assert r.has_long_creative is True
    assert r.suppress_ers_lecture is True


def test_m214_classify_content_honors_user_text():
    # Load m214 attachments via path to avoid full app import chain when possible.
    path = ROOT / "app" / "codirector" / "m214" / "attachments.py"
    # Ensure package stubs for relative imports used by classify_content's try-import.
    sys.path.insert(0, str(ROOT))
    try:
        from app.codirector.m214.attachments import classify_content
    except Exception as exc:  # pragma: no cover - env without deps
        import pytest

        pytest.skip(f"m214 import unavailable: {exc}")
    kind, conf, signals = classify_content(
        mime_type="image/jpeg",
        filename="cafe.jpg",
        user_text="use as background for the Timeline",
    )
    assert kind == "timeline_background_ref"
    assert conf >= 0.5
    assert any("attach_intent" in s or "background" in s or "user:" in s for s in signals)


def test_attachment_context_stamps_timeline_intent():
    sys.path.insert(0, str(ROOT))
    try:
        from app.codirector.context_enrichment import attachment_context_block
    except Exception as exc:  # pragma: no cover
        import pytest

        pytest.skip(f"context_enrichment import unavailable: {exc}")

    class _FakeDb:
        def __init__(self, assets):
            self._assets = assets

        def get(self, model, key):  # noqa: ANN001
            return self._assets.get(key)

    asset = SimpleNamespace(
        id="asset-1",
        project_id="proj-1",
        kind="image",
        tag="Schnick Café",
        filename="cafe.png",
        production_approval="none",
        validation_lifecycle="not_requested",
    )
    block = attachment_context_block(
        _FakeDb({"asset-1": asset}),
        project_id="proj-1",
        attachment_ids=["asset-1"],
        user_text="Use this as the background / look of the café @Korri",
    )
    assert "timeline_background_ref" in block or "Timeline" in block
    lower = block.lower()
    assert "ers" in lower  # suppress guidance mentions ERS
    assert "timeline.attach_optional_reference" in block or "references.attach" in block
