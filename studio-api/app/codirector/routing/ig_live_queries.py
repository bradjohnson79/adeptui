"""Backend-only Image Generator live-state query replies (WAVE 2).

Answers which-refs / generate-with-current-setup from imageGeneratorPlanning
when the FE (or any client) posts that snapshot. No FE publisher required for
the contract itself — empty planning yields None.
"""

from __future__ import annotations

import re
from typing import Any, Optional

_WHICH_REFS_RE = re.compile(
    r"(?i)\b(?:which|what)\s+(?:refs?|references?|images?)\b|"
    r"\b(?:refs?|references?)\s+(?:are|do i have|loaded|attached|bound)\b|"
    r"\bcurrent\s+(?:refs?|references?|setup)\b"
)

_GENERATE_SETUP_RE = re.compile(
    r"(?i)\b(?:generate|make|create|render)\b.+\b(?:with\s+(?:this|current|my)\s+setup|using\s+(?:this|current)\s+setup)\b|"
    r"\b(?:generate|make|create)\b.+\b(?:current\s+(?:composer|prompt|settings))\b|"
    r"\bgenerate\s+with\s+(?:these|the)\s+refs?\b"
)



def _planning_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _ref_row_from_selected(kind: str, item: object) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    asset_id = str(item.get("assetId") or item.get("id") or "").strip()
    name = str(item.get("name") or "").strip()
    token = str(item.get("chip") or item.get("token") or "").strip()
    label = str(item.get("label") or name or token or asset_id or "?").strip()
    row_kind = str(item.get("kind") or kind or "ref").strip() or "ref"
    return {
        "kind": row_kind,
        "role": str(item.get("role") or row_kind).strip() or row_kind,
        "assetId": asset_id,
        "name": name,
        "label": label,
        "token": token,
    }


def normalize_image_generator_planning(planning: object | None) -> dict[str, Any]:
    """Ensure CIS planning shape: authorityRefs / selected* / references / referenceAssetIds.

    Adapter-agnostic normalize -- does not pick workflowKey. When clients send
    authorityRefs or selected*, partition into the same compile authority the
    Image Generator FE publishes (serializeImageGeneratorPlan).
    """
    data = _planning_dict(planning)
    if not data:
        return {}

    out = dict(data)
    try:
        from ...image_product.prompt_tokens import compile_typed_image_authority

        pack = compile_typed_image_authority(planning=out)
        if pack.get("authorityRefs"):
            out.setdefault("authorityRefs", pack["authorityRefs"])
            out.setdefault("selectedCharacters", pack["selectedCharacters"])
            out.setdefault("selectedProps", pack["selectedProps"])
            out.setdefault("selectedEnvironment", pack["selectedEnvironment"])
            out.setdefault("selectedPoseCraft", pack["selectedPoseCraft"])
            out.setdefault("selectedGeneric", pack["selectedGeneric"])
            out.setdefault("references", pack["references"])
            ids = pack.get("referenceAssetIds") or []
            existing_ids = out.get("referenceAssetIds") if isinstance(out.get("referenceAssetIds"), list) else []
            if ids and not existing_ids:
                out["referenceAssetIds"] = list(ids)
            elif ids:
                merged = []
                for aid in list(existing_ids) + list(ids):
                    s = str(aid or "").strip()
                    if s and s not in merged:
                        merged.append(s)
                out["referenceAssetIds"] = merged
            if pack.get("poseCraft") and not (
                isinstance(out.get("poseCraft"), dict) and out["poseCraft"].get("attached")
            ):
                out["poseCraft"] = pack["poseCraft"]
            return out
    except Exception:
        pass

    refs = out.get("references") if isinstance(out.get("references"), list) else None
    if not refs:
        built: list[dict[str, Any]] = []
        authority = out.get("authorityRefs") if isinstance(out.get("authorityRefs"), list) else []
        if authority:
            for item in authority:
                kind = str(item.get("kind") or "ref") if isinstance(item, dict) else "ref"
                row = _ref_row_from_selected(kind, item)
                if row:
                    built.append(row)
        else:
            for kind, key, multi in (
                ("character", "selectedCharacters", True),
                ("prop", "selectedProps", True),
                ("environment", "selectedEnvironment", False),
                ("posecraft", "selectedPoseCraft", False),
                ("other", "selectedGeneric", True),
            ):
                raw = out.get(key)
                items = raw if multi else ([raw] if raw is not None else [])
                if not isinstance(items, list):
                    continue
                for item in items:
                    row = _ref_row_from_selected(kind, item)
                    if row:
                        built.append(row)
        if built:
            out["references"] = built

    pose = out.get("poseCraft") if isinstance(out.get("poseCraft"), dict) else None
    if not pose:
        selected_pose = out.get("selectedPoseCraft")
        if isinstance(selected_pose, dict):
            out["poseCraft"] = {
                "attached": True,
                "imageAssetId": str(selected_pose.get("assetId") or "").strip() or None,
                "name": str(selected_pose.get("name") or "").strip() or None,
                "chip": str(selected_pose.get("chip") or "").strip() or None,
            }
        else:
            auth = out.get("authorityRefs") if isinstance(out.get("authorityRefs"), list) else []
            for item in auth:
                if isinstance(item, dict) and str(item.get("kind") or "") == "posecraft":
                    out["poseCraft"] = {
                        "attached": True,
                        "imageAssetId": str(item.get("assetId") or "").strip() or None,
                        "name": str(item.get("name") or "").strip() or None,
                        "chip": str(item.get("chip") or "").strip() or None,
                    }
                    break
    if not (isinstance(out.get("referenceAssetIds"), list) and out.get("referenceAssetIds")):
        ids: list[str] = []
        for item in (out.get("references") if isinstance(out.get("references"), list) else []) or []:
            if not isinstance(item, dict):
                continue
            aid = str(item.get("assetId") or item.get("id") or "").strip()
            if aid and aid not in ids:
                ids.append(aid)
        for item in (out.get("authorityRefs") if isinstance(out.get("authorityRefs"), list) else []) or []:
            if not isinstance(item, dict):
                continue
            aid = str(item.get("assetId") or "").strip()
            if aid and aid not in ids:
                ids.append(aid)
        if ids:
            out["referenceAssetIds"] = ids
    return out

def describe_ig_refs(planning: object | None) -> str:
    data = normalize_image_generator_planning(planning)
    if not data:
        return (
            "I do not have a live Image Generator composer snapshot in this turn. "
            "Open Image Generator and ask again, or name the refs "
            "(@Character %Prop #Environment ~GenericImage)."
        )
    lines = ["Live Image Generator references:"]
    refs = data.get("references") if isinstance(data.get("references"), list) else []
    ids = data.get("referenceAssetIds") if isinstance(data.get("referenceAssetIds"), list) else []
    if refs:
        for item in refs[:12]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or item.get("kind") or "ref").strip()
            aid = str(item.get("assetId") or item.get("id") or "").strip()
            label = str(item.get("label") or item.get("name") or aid or "?").strip()
            token = str(item.get("token") or "").strip()
            bit = f"- {role}: {label}"
            if token:
                bit += f" ({token})"
            elif aid:
                bit += f" [{aid[:8]}]"
            lines.append(bit)
    elif ids:
        lines.append(
            f"- Reference asset ids ({len(ids)}): " + ", ".join(str(x) for x in ids[:8])
        )
    else:
        lines.append("- None loaded in the current composer.")
    pose = data.get("poseCraft") if isinstance(data.get("poseCraft"), dict) else {}
    if pose.get("attached"):
        lines.append(
            "- Picture reference attached"
            + (f" ({pose.get('imageAssetId')})" if pose.get("imageAssetId") else "")
        )
    prompt = str(data.get("prompt") or "").strip()
    if prompt:
        lines.append(f"- Prompt: {prompt[:240]}")
    model = str(data.get("modelId") or "").strip()
    if model:
        lines.append(f"- Model: {model}")
    return "\n".join(lines)


def describe_generate_with_setup(planning: object | None) -> tuple[str, Optional[str]]:
    """Return (spoken, optional capability target)."""
    data = normalize_image_generator_planning(planning)
    if not data:
        return (
            "I can generate with the current Image Generator setup once the live composer "
            "snapshot is on this turn. Open Image Generator (or publish imageGeneratorPlanning) and confirm generate.",
            "image.generator",
        )
    prompt = str(data.get("prompt") or "").strip()
    model = str(data.get("modelId") or "").strip() or "the selected engine"
    refs = data.get("referenceAssetIds") if isinstance(data.get("referenceAssetIds"), list) else []
    nrefs = len(refs)
    spoken = (
        f"Ready to generate a production still with the current Image Generator setup "
        f"({model}; {nrefs} ref{'s' if nrefs != 1 else ''}"
        + (f"; prompt starts: {prompt[:120]!r}" if prompt else "; empty prompt")
        + "). Confirm and I will run image.generate - not Scene Creator Standard."
    )
    return spoken, "image.generate"


def resolve_ig_live_query(
    message: str,
    planning: object | None,
) -> Optional[dict[str, Any]]:
    text = (message or "").strip()
    if not text:
        return None
    if _WHICH_REFS_RE.search(text):
        return {
            "kind": "ig_which_refs",
            "spoken": describe_ig_refs(planning),
            "block": True,
            "target": None,
        }
    if _GENERATE_SETUP_RE.search(text):
        spoken, target = describe_generate_with_setup(planning)
        return {
            "kind": "ig_generate_with_setup",
            "spoken": spoken,
            "block": True,
            "target": target,
        }
    return None
