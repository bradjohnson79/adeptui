"""Generator roster tests — the Local Generator list is sourced from the
authoritative Certified registry (never a hardcoded Character Creator list).

Covers:
- Qwen Image 2512 (qwen2512) is present, Certified, executable, txt2img-only.
- Z-Image Turbo (zimage) is reference-capable (family-level supportsReferences).
- Illustrious XL is present, Certified, txt2img-only.
- Auto Select is always first; non-Certified families (FLUX/HiDream/SD3.5) are
  excluded from the production-safe roster.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.imagegen_workflows import build_local_generator_models  # noqa: E402


def _by_id(options):
    return {o["id"]: o for o in options}


def test_qwen_present_certified_and_txt2img_only():
    opts = _by_id(build_local_generator_models())
    assert "qwen2512" in opts, "Qwen Image 2512 must appear in the local roster"
    q = opts["qwen2512"]
    assert q["status"] == "Certified"
    assert q["executable"] is True
    assert q["supportsReferences"] is False  # txt2img-only → disabled with a reference
    assert q["label"] == "Qwen Image 2512"


def test_zimage_is_reference_capable():
    opts = _by_id(build_local_generator_models())
    assert "zimage" in opts
    # zimage.ref_edit is Certified + reference-capable → family is reference-capable.
    assert opts["zimage"]["supportsReferences"] is True
    assert opts["zimage"]["status"] == "Certified"


def test_illustrious_present_and_txt2img_only():
    opts = _by_id(build_local_generator_models())
    assert "illustrious" in opts
    il = opts["illustrious"]
    assert il["status"] == "Certified"
    assert il["supportsReferences"] is False
    assert "Illustrious" in il["label"]


def test_auto_select_is_first():
    opts = build_local_generator_models()
    assert opts[0]["id"] == "auto"
    assert opts[0]["group"] == "auto"


def test_flux_present_certified_and_editing_capable():
    """FLUX is now Certified + has a real img2img/edit workflow → visible."""
    opts = _by_id(build_local_generator_models())
    assert "flux" in opts, "FLUX must appear in the local roster after certification"
    f = opts["flux"]
    assert f["status"] == "Certified"
    assert f["executable"] is True
    assert f["supportsEditing"] is True
    assert "FLUX" in f["label"]


def test_non_certified_families_excluded():
    """HiDream / SD3.5 / custom are not Certified → excluded by default."""
    opts = _by_id(build_local_generator_models())
    for fid in ("hidream", "sd35", "custom"):
        assert fid not in opts, f"{fid} must not appear (not Certified + READY)"


def test_every_option_has_capability_metadata():
    for o in build_local_generator_models():
        if o["id"] == "auto":
            continue
        assert "supportsReferences" in o
        assert "supportsEditing" in o
        assert "status" in o
        assert "executable" in o
        assert o["group"] == "local"


def test_krea2_listed_as_local_not_auto_default():
    opts = build_local_generator_models()
    by_id = {o["id"]: o for o in opts}
    assert opts[0]["id"] == "auto"
    assert "krea2" in by_id
    krea = by_id["krea2"]
    assert krea["label"] == "Local Krea 2"
    assert krea["group"] == "local"
    assert krea["status"] in {"Draft", "Certified"}
    # Auto Select stays first; Krea is never the default slot.
    assert opts[1]["id"] != "krea2"

