"""Phase 4 ref-encode cache unit tests (Prop Creator Qwen Edit graph reuse)."""

from __future__ import annotations

from app.image_runtime.ref_encode_cache import (
    NODE_CLIP,
    NODE_LOAD_IMAGE,
    NODE_NEG_ENCODE,
    NODE_POS_ENCODE,
    NODE_VAE,
    build_ref_encode_key,
    classify_encode_cache,
    clear_ref_encode_session,
    extract_execution_cached_nodes,
    note_from_comfy_history,
)


def test_key_changes_with_prompt_but_shared_stable(tmp_path):
    img = tmp_path / "ref.png"
    img.write_bytes(b"png-bytes")
    a = build_ref_encode_key(
        ref_asset_id="asset-1",
        ref_path=img,
        prompt="front view",
        negative="blurry",
        workflow_key="qwen_edit_2509.edit",
        unet_name="u.safetensors",
        clip_name="c.safetensors",
        vae_name="v.safetensors",
        width=768,
        height=768,
    )
    b = build_ref_encode_key(
        ref_asset_id="asset-1",
        ref_path=img,
        prompt="back view",
        negative="blurry",
        workflow_key="qwen_edit_2509.edit",
        unet_name="u.safetensors",
        clip_name="c.safetensors",
        vae_name="v.safetensors",
        width=768,
        height=768,
    )
    assert a.digest() != b.digest()
    assert a.shared_digest() == b.shared_digest()


def test_key_invalidates_on_ref_mtime(tmp_path):
    img = tmp_path / "ref.png"
    img.write_bytes(b"png-bytes")
    a = build_ref_encode_key(
        ref_asset_id="asset-1",
        ref_path=img,
        prompt="front",
        negative="x",
        workflow_key="qwen_edit_2509.edit",
        width=768,
        height=768,
    )
    img.write_bytes(b"png-bytes-changed")
    b = build_ref_encode_key(
        ref_asset_id="asset-1",
        ref_path=img,
        prompt="front",
        negative="x",
        workflow_key="qwen_edit_2509.edit",
        width=768,
        height=768,
    )
    assert a.shared_digest() != b.shared_digest()


def test_extract_execution_cached_nodes():
    history = {
        "status": {
            "status_str": "success",
            "completed": True,
            "messages": [
                ["execution_start", {"prompt_id": "p"}],
                ["execution_cached", {"nodes": ["2", "3", "5", "7"], "prompt_id": "p"}],
                ["execution_success", {"prompt_id": "p"}],
            ],
        }
    }
    assert extract_execution_cached_nodes(history) == ["2", "3", "5", "7"]
    wrapped = {"abc-prompt": history}
    assert extract_execution_cached_nodes(wrapped) == ["2", "3", "5", "7"]


def test_multiview_shared_hit_then_prompt_invalidate(tmp_path):
    clear_ref_encode_session()
    img = tmp_path / "ref.png"
    img.write_bytes(b"png")
    k1 = build_ref_encode_key(
        ref_asset_id="a1",
        ref_path=img,
        prompt="front",
        negative="neg",
        workflow_key="qwen_edit_2509.edit",
        unet_name="u",
        clip_name="c",
        vae_name="v",
        width=768,
        height=768,
    )
    # First angle — cold session, no prior shared key
    r1 = classify_encode_cache(key=k1, cached_nodes=[NODE_CLIP, NODE_VAE], stage_reused=False)
    assert r1["hit"] is False
    assert r1["sharedKeyMatch"] is False

    k2 = build_ref_encode_key(
        ref_asset_id="a1",
        ref_path=img,
        prompt="back",
        negative="neg",
        workflow_key="qwen_edit_2509.edit",
        unet_name="u",
        clip_name="c",
        vae_name="v",
        width=768,
        height=768,
    )
    r2 = classify_encode_cache(
        key=k2,
        cached_nodes=[NODE_CLIP, NODE_VAE, NODE_LOAD_IMAGE, NODE_NEG_ENCODE],
        stage_reused=True,
    )
    assert r2["sharedKeyMatch"] is True
    assert r2["hit"] is True
    assert r2["strongHit"] is True
    assert r2["loadImageHit"] is True
    assert r2["negEncodeHit"] is True
    assert r2["posEncodeHit"] is False
    assert r2["fullKeyMatch"] is False  # prompt changed vs prior full key
    assert "prompt" in r2["invalidatedFor"] or r2["fullKeyMatch"] is False

    # Change model → shared miss
    k3 = build_ref_encode_key(
        ref_asset_id="a1",
        ref_path=img,
        prompt="left",
        negative="neg",
        workflow_key="qwen_edit_2509.edit",
        unet_name="OTHER",
        clip_name="c",
        vae_name="v",
        width=768,
        height=768,
    )
    r3 = classify_encode_cache(key=k3, cached_nodes=[], stage_reused=True)
    assert r3["sharedKeyMatch"] is False
    assert r3["hit"] is False
    clear_ref_encode_session()


def test_note_from_comfy_history_roundtrip(tmp_path):
    clear_ref_encode_session()
    img = tmp_path / "ref.png"
    img.write_bytes(b"x")
    k = build_ref_encode_key(
        ref_asset_id="a",
        ref_path=img,
        prompt="p",
        negative="n",
        workflow_key="qwen_edit_2509.edit",
        width=768,
        height=768,
    )
    # seed session
    classify_encode_cache(key=k, cached_nodes=[])
    k2 = build_ref_encode_key(
        ref_asset_id="a",
        ref_path=img,
        prompt="p2",
        negative="n",
        workflow_key="qwen_edit_2509.edit",
        width=768,
        height=768,
    )
    hist = {
        "status": {
            "messages": [
                ["execution_cached", {"nodes": [NODE_LOAD_IMAGE, NODE_NEG_ENCODE, NODE_CLIP]}]
            ]
        }
    }
    report = note_from_comfy_history(key=k2, history=hist, stage_reused=True)
    assert report["hit"] is True
    assert report["key"]["sharedDigest"] == k2.shared_digest()
    clear_ref_encode_session()
