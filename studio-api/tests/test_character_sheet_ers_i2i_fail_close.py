"""G1: Character Sheet / CRS must not resolve ERS I2I (qwen2512.ref)."""

from __future__ import annotations

import pytest

from app.image_product.compile import (
    CHARACTER_SHEET_ERS_I2I_UNSUPPORTED,
    compile_image_request,
    refuse_character_sheet_ers_i2i,
)
from app.image_product.resolve import resolve_image_capability


def _crs_body(**extra):
    body = {
        "prompt": "Create Korri's Character Reference Sheet.",
        "purpose": "character_sheet",
        "operation": "image.generate",
        "modelFamilyPreference": "qwen2512",
        "lockModelFamily": True,
        "source": "local",
        "referenceImage": "b6ab91dd-9d0a-4e4b-98b4-b26d268950dc",
        "referenceIds": ["b6ab91dd-9d0a-4e4b-98b4-b26d268950dc"],
        "width": 2560,
        "height": 2560,
    }
    body.update(extra)
    return body


def test_refuse_character_sheet_ers_i2i_force_key():
    msg = refuse_character_sheet_ers_i2i(
        _crs_body(forceWorkflowKey="qwen2512.ref"),
        purpose="character_sheet",
        force_key="qwen2512.ref",
    )
    assert msg == CHARACTER_SHEET_ERS_I2I_UNSUPPORTED
    assert "environment-ref" in msg
    assert "qwen2512.ref" in msg
    assert "zimage.ref_edit" not in msg


def test_refuse_character_reference_sheet_alias_official_id():
    msg = refuse_character_sheet_ers_i2i(
        {"purpose": "character_reference_sheet", "officialModelId": "environment-ref"},
        purpose="character_reference_sheet",
        official="environment-ref",
    )
    assert msg == CHARACTER_SHEET_ERS_I2I_UNSUPPORTED
    assert "environment-ref" in msg
    assert "qwen2512.ref" in msg


def test_refuse_character_sheet_does_not_fire_without_ers_pin():
    """Qwen + attached picture without ERS pin stays legal (PROFILE_GUIDED)."""
    assert refuse_character_sheet_ers_i2i(_crs_body(), purpose="character_sheet") == ""


def test_character_sheet_force_qwen2512_ref_does_not_resolve_ers_i2i():
    body = _crs_body(forceWorkflowKey="qwen2512.ref", allow_force_workflow_key=True)
    cap = resolve_image_capability(body)
    assert cap["canExecute"] is False
    assert cap.get("workflowKey") != "qwen2512.ref"
    assert cap.get("officialModelId") != "environment-ref"
    assert cap.get("workflowKey") != "zimage.ref_edit"
    assert "zimage.ref_edit" not in str(cap.get("reason") or "")
    assert "qwen2512.ref" in str(cap.get("reason") or "")
    assert str(cap.get("reason") or "") == CHARACTER_SHEET_ERS_I2I_UNSUPPORTED

    with pytest.raises(RuntimeError, match="environment-ref") as exc:
        compile_image_request("crs-no-ers-i2i", body)
    assert "zimage.ref_edit" not in str(exc.value)
    assert str(exc.value) == CHARACTER_SHEET_ERS_I2I_UNSUPPORTED


def test_character_reference_sheet_alias_force_ers_i2i_refuses():
    body = _crs_body(
        purpose="character_reference_sheet",
        forceWorkflowKey="qwen2512.ref",
        allow_force_workflow_key=True,
    )
    cap = resolve_image_capability(body)
    assert cap["canExecute"] is False
    assert cap.get("workflowKey") != "qwen2512.ref"
    assert cap.get("workflowKey") != "zimage.ref_edit"
    with pytest.raises(RuntimeError, match="qwen2512.ref") as exc:
        compile_image_request("crs-alias-no-ers-i2i", body)
    assert str(exc.value) == CHARACTER_SHEET_ERS_I2I_UNSUPPORTED


def test_character_sheet_official_environment_ref_refuses():
    body = _crs_body(officialModelId="environment-ref")
    cap = resolve_image_capability(body)
    assert cap["canExecute"] is False
    assert cap.get("officialModelId") != "environment-ref" or cap["canExecute"] is False
    assert cap.get("workflowKey") != "qwen2512.ref"
    assert cap.get("workflowKey") != "zimage.ref_edit"
    with pytest.raises(RuntimeError, match="environment-ref") as exc:
        compile_image_request("crs-official-env-ref", body)
    assert str(exc.value) == CHARACTER_SHEET_ERS_I2I_UNSUPPORTED


def test_character_sheet_qwen_refs_resolve_txt2img_not_ers_or_zimage():
    """No ERS pin: Qwen + CRS reference stays qwen2512.txt2img, not zimage."""
    cap = resolve_image_capability(_crs_body())
    assert cap["canExecute"] is True
    assert cap.get("workflowKey") != "qwen2512.ref"
    assert cap.get("workflowKey") != "zimage.ref_edit"
    assert cap.get("officialModelId") != "environment-ref"
    compiled = compile_image_request("crs-profile-guided", _crs_body())
    runtime = compiled.get("imageRuntime") or {}
    selected = str(runtime.get("workflowKey") or "")
    assert selected != "qwen2512.ref"
    assert selected != "zimage.ref_edit"
    assert selected == "qwen2512.txt2img" or selected.endswith(".txt2img")


def test_image_product_compile_character_sheet_ers_i2i_is_http_400(client):
    """POST /api/image-product/compile returns 400 with the CRS ERS sentence,
    not a generic 500 Internal Server Error."""
    resp = client.post(
        "/api/image-product/compile",
        json={
            "projectId": "crs-ers-i2i-http-400",
            "prompt": "Create Korri's Character Reference Sheet.",
            "purpose": "character_sheet",
            "operation": "image.generate",
            "modelFamilyPreference": "qwen2512",
            "lockModelFamily": True,
            "source": "local",
            "referenceImage": "b6ab91dd-9d0a-4e4b-98b4-b26d268950dc",
            "referenceIds": ["b6ab91dd-9d0a-4e4b-98b4-b26d268950dc"],
            "forceWorkflowKey": "qwen2512.ref",
            "allow_force_workflow_key": True,
            "width": 2560,
            "height": 2560,
        },
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail == CHARACTER_SHEET_ERS_I2I_UNSUPPORTED
    assert "environment-ref" in detail
    assert "qwen2512.ref" in detail
    assert "Character" in detail
    assert "zimage.ref_edit" not in detail
    assert resp.text != "Internal Server Error"


def test_visual_sheet_qwen_plus_ref_does_not_route_ers_i2i():
    from app.character_identity.visual_sheet import (
        CONDITIONING_PROFILE_GUIDED,
        QWEN_REF_WORKFLOW_KEY,
        _build_candidate_routing_plan,
    )

    plan = _build_candidate_routing_plan(
        candidate_count=1,
        reference_asset_id="sheet-1",
        generator_sources={"local": {"family": "qwen2512"}, "api": None},
    )
    stage1 = plan[0]["stage1"]
    assert stage1["workflowKey"] != QWEN_REF_WORKFLOW_KEY
    assert stage1["workflowKey"] != "zimage.ref_edit"
    assert stage1["workflowKey"] == "qwen2512.txt2img"
    assert stage1["source_asset_id"] is None
    assert stage1["conditioningMode"] == CONDITIONING_PROFILE_GUIDED


def test_recommend_character_sheet_does_not_keep_ers_pref_as_family():
    from app.image_product.recommend import recommend_image_family

    rec = recommend_image_family(
        prompt="Create Korri's CRS",
        purpose="character_sheet",
        model_family_preference="environment-ref",
        reference_asset_id="sheet-1",
    )
    assert rec.get("recommendedFamily") != "environment-ref"
    assert rec.get("recommendedFamily") != "qwen2512.ref"
    assert rec.get("executionFamily") != "zimage"
    rec2 = recommend_image_family(
        prompt="Create Korri's CRS",
        purpose="character_reference_sheet",
        model_family_preference="qwen2512.ref",
        reference_asset_id="sheet-1",
    )
    assert rec2.get("recommendedFamily") != "qwen2512.ref"
    assert rec2.get("executionFamily") != "zimage"
