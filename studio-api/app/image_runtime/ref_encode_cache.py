"""Prop Creator Qwen Edit ref-encode cache (graph reuse / Comfy execution cache).

Phase 4 safe accelerator: key shared encode inputs across multi-view angle jobs
and record Comfy execution_cached hits. Does not change steps/CFG/size/sampler/
model or inject approximate caches. Invalidates when ref/prompt/model/workflow/
encode params change.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Qwen Edit 2509 graph node ids from build_qwen_edit_2509_i2i_workflow
NODE_UNET = "1"
NODE_CLIP = "2"
NODE_VAE = "3"
NODE_SAMPLING = "4"
NODE_LOAD_IMAGE = "5"
NODE_POS_ENCODE = "6"
NODE_NEG_ENCODE = "7"
NODE_EMPTY_LATENT = "8"

ENCODE_RELATED_NODES = frozenset(
    {
        NODE_UNET,
        NODE_CLIP,
        NODE_VAE,
        NODE_SAMPLING,
        NODE_LOAD_IMAGE,
        NODE_POS_ENCODE,
        NODE_NEG_ENCODE,
        NODE_EMPTY_LATENT,
    }
)

# Shared across multi-view when only the angle positive prompt changes.
SHARED_ENCODE_NODES = frozenset(
    {
        NODE_UNET,
        NODE_CLIP,
        NODE_VAE,
        NODE_SAMPLING,
        NODE_LOAD_IMAGE,
        NODE_NEG_ENCODE,
        NODE_EMPTY_LATENT,
    }
)


def _sha16(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def _file_stat_token(path: str | Path | None) -> dict[str, Any]:
    raw = str(path or "").strip()
    if not raw:
        return {"path": "", "size": 0, "mtime_ns": 0, "present": False}
    p = Path(raw)
    if not p.is_file():
        return {"path": raw, "size": 0, "mtime_ns": 0, "present": False}
    st = p.stat()
    return {
        "path": raw,
        "size": int(st.st_size),
        "mtime_ns": int(st.st_mtime_ns),
        "present": True,
    }


@dataclass(frozen=True)
class RefEncodeKey:
    """Encode-input fingerprint. Seed/sampler knobs that only touch KSampler are excluded."""

    ref_asset_id: str
    ref_size: int
    ref_mtime_ns: int
    prompt_hash: str
    negative_hash: str
    model_token: str
    workflow_key: str
    width: int
    height: int
    encode_params_hash: str

    def digest(self) -> str:
        payload = {
            "ref_asset_id": self.ref_asset_id,
            "ref_size": self.ref_size,
            "ref_mtime_ns": self.ref_mtime_ns,
            "prompt_hash": self.prompt_hash,
            "negative_hash": self.negative_hash,
            "model_token": self.model_token,
            "workflow_key": self.workflow_key,
            "width": self.width,
            "height": self.height,
            "encode_params_hash": self.encode_params_hash,
        }
        return _sha16(json.dumps(payload, sort_keys=True, separators=(",", ":")))

    def shared_digest(self) -> str:
        """Key for subgraph shared across angle views (excludes positive prompt)."""
        payload = {
            "ref_asset_id": self.ref_asset_id,
            "ref_size": self.ref_size,
            "ref_mtime_ns": self.ref_mtime_ns,
            "negative_hash": self.negative_hash,
            "model_token": self.model_token,
            "workflow_key": self.workflow_key,
            "width": self.width,
            "height": self.height,
            "encode_params_hash": self.encode_params_hash,
        }
        return _sha16(json.dumps(payload, sort_keys=True, separators=(",", ":")))

    def to_dict(self) -> dict[str, Any]:
        return {
            "refAssetId": self.ref_asset_id,
            "refSize": self.ref_size,
            "refMtimeNs": self.ref_mtime_ns,
            "promptHash": self.prompt_hash,
            "negativeHash": self.negative_hash,
            "modelToken": self.model_token,
            "workflowKey": self.workflow_key,
            "width": self.width,
            "height": self.height,
            "encodeParamsHash": self.encode_params_hash,
            "digest": self.digest(),
            "sharedDigest": self.shared_digest(),
        }


def build_ref_encode_key(
    *,
    ref_asset_id: str = "",
    ref_path: str | Path | None = None,
    prompt: str = "",
    negative: str = "",
    workflow_key: str = "",
    unet_name: str = "",
    clip_name: str = "",
    vae_name: str = "",
    weight_dtype: str = "",
    width: int = 0,
    height: int = 0,
    encode_params: dict[str, Any] | None = None,
) -> RefEncodeKey:
    stat = _file_stat_token(ref_path)
    model_token = _sha16(
        "|".join(
            [
                str(unet_name or "").strip(),
                str(clip_name or "").strip(),
                str(vae_name or "").strip(),
                str(weight_dtype or "").strip(),
            ]
        )
    )
    params = dict(encode_params or {})
    # Only params that affect encode / shared latent canvas — never seed/steps/cfg/sampler.
    safe_params = {
        k: params[k]
        for k in sorted(params)
        if k
        in {
            "denoise_encode",
            "model_shift",
            "identity_role",
            "scene_image",
            "batch_size",
        }
    }
    return RefEncodeKey(
        ref_asset_id=str(ref_asset_id or "").strip(),
        ref_size=int(stat["size"]),
        ref_mtime_ns=int(stat["mtime_ns"]),
        prompt_hash=_sha16(str(prompt or "")),
        negative_hash=_sha16(str(negative or "")),
        model_token=model_token,
        workflow_key=str(workflow_key or "").strip(),
        width=int(width or 0),
        height=int(height or 0),
        encode_params_hash=_sha16(json.dumps(safe_params, sort_keys=True, separators=(",", ":"))),
    )


@dataclass
class _SessionEntry:
    full_digest: str = ""
    shared_digest: str = ""
    ref_asset_id: str = ""
    hits: int = 0
    misses: int = 0


_session: _SessionEntry = _SessionEntry()


def clear_ref_encode_session() -> None:
    global _session
    _session = _SessionEntry()


def last_shared_digest() -> str:
    return _session.shared_digest


def extract_execution_cached_nodes(history: Any) -> list[str]:
    """Pull node ids from Comfy status.messages execution_cached entries."""
    entry = history
    if isinstance(history, dict):
        # Full /history/{id} map → single entry, or the entry itself.
        if "status" not in history and len(history) == 1:
            only = next(iter(history.values()))
            if isinstance(only, dict):
                entry = only
        elif "status" not in history and "prompt" not in history:
            # maybe {promptId: entry}
            for val in history.values():
                if isinstance(val, dict) and ("status" in val or "outputs" in val):
                    entry = val
                    break
    if not isinstance(entry, dict):
        return []
    status = entry.get("status") if isinstance(entry.get("status"), dict) else {}
    messages = status.get("messages") or entry.get("messages") or []
    cached: list[str] = []
    for msg in messages:
        if not isinstance(msg, (list, tuple)) or len(msg) < 2:
            continue
        if str(msg[0]) != "execution_cached":
            continue
        body = msg[1] if isinstance(msg[1], dict) else {}
        nodes = body.get("nodes") or []
        for n in nodes:
            sid = str(n)
            if sid not in cached:
                cached.append(sid)
    return cached


def classify_encode_cache(
    *,
    key: RefEncodeKey,
    cached_nodes: list[str] | None,
    stage_reused: bool | None = None,
    graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify HIT/MISS for ref-encode graph reuse. Updates in-process session."""
    global _session
    nodes = [str(n) for n in (cached_nodes or [])]
    node_set = set(nodes)
    shared_cached = sorted(node_set & SHARED_ENCODE_NODES)
    encode_cached = sorted(node_set & ENCODE_RELATED_NODES)

    prev_shared = _session.shared_digest
    shared_same = bool(prev_shared) and prev_shared == key.shared_digest()
    full_same = bool(_session.full_digest) and _session.full_digest == key.digest()

    load_hit = NODE_LOAD_IMAGE in node_set
    neg_hit = NODE_NEG_ENCODE in node_set
    pos_hit = NODE_POS_ENCODE in node_set
    clip_hit = NODE_CLIP in node_set
    vae_hit = NODE_VAE in node_set
    unet_hit = NODE_UNET in node_set

    # Multi-view success: same shared encode inputs AND Comfy reused shared encode nodes
    # (LoadImage and/or negative TextEncode, plus ideally loaders).
    shared_hit = shared_same and (
        load_hit or neg_hit or (clip_hit and vae_hit and (stage_reused is not False))
    )
    # Stronger: LoadImage + neg encode both cached under same shared key.
    strong_hit = shared_same and load_hit and neg_hit

    invalidated_for: list[str] = []
    if prev_shared and not shared_same:
        if _session.ref_asset_id != key.ref_asset_id:
            invalidated_for.append("ref_asset_id")
        else:
            # Narrower reasons from digest components — report known fields.
            invalidated_for.append("shared_encode_inputs")
    if _session.full_digest and not full_same and shared_same:
        invalidated_for.append("prompt")

    if shared_hit:
        _session.hits += 1
    elif prev_shared:
        _session.misses += 1

    _session.full_digest = key.digest()
    _session.shared_digest = key.shared_digest()
    _session.ref_asset_id = key.ref_asset_id

    class_types = []
    if isinstance(graph, dict):
        for nid in encode_cached:
            node = graph.get(nid) or {}
            if isinstance(node, dict) and node.get("class_type"):
                class_types.append(str(node["class_type"]))

    return {
        "kind": "ref_encode_graph_reuse",
        "hit": bool(shared_hit),
        "strongHit": bool(strong_hit),
        "fullKeyMatch": bool(full_same),
        "sharedKeyMatch": bool(shared_same),
        "stageReused": stage_reused,
        "cachedNodes": nodes,
        "encodeCachedNodes": encode_cached,
        "sharedCachedNodes": shared_cached,
        "loadImageHit": load_hit,
        "negEncodeHit": neg_hit,
        "posEncodeHit": pos_hit,
        "clipLoaderHit": clip_hit,
        "vaeLoaderHit": vae_hit,
        "unetLoaderHit": unet_hit,
        "invalidatedFor": invalidated_for,
        "key": key.to_dict(),
        "sessionHits": _session.hits,
        "sessionMisses": _session.misses,
        "encodeClassTypes": class_types,
    }


def note_from_comfy_history(
    *,
    key: RefEncodeKey,
    history: Any,
    stage_reused: bool | None = None,
    graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cached = extract_execution_cached_nodes(history)
    return classify_encode_cache(
        key=key,
        cached_nodes=cached,
        stage_reused=stage_reused,
        graph=graph,
    )


def applies_to_workflow(workflow_key: str, purpose: str = "", tag: str = "") -> bool:
    wf = str(workflow_key or "")
    if wf.startswith("qwen_edit_2509"):
        return True
    purpose_l = str(purpose or "").lower()
    tag_l = str(tag or "").lower()
    return purpose_l in {"project_prop_angle", "project_prop", "project_prop_primary_ref_edit"} or tag_l.startswith(
        "prop_"
    )


__all__ = [
    "RefEncodeKey",
    "build_ref_encode_key",
    "classify_encode_cache",
    "clear_ref_encode_session",
    "extract_execution_cached_nodes",
    "note_from_comfy_history",
    "applies_to_workflow",
    "last_shared_digest",
    "SHARED_ENCODE_NODES",
    "ENCODE_RELATED_NODES",
    "NODE_LOAD_IMAGE",
    "NODE_POS_ENCODE",
    "NODE_NEG_ENCODE",
]
