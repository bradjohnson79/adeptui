"""CIS / Image Generator reference pixel-binding (typed authority refs).

Product law:
- Actual images are authoritative; never silent txt2img when refs are selected
  and the locked family cannot bind them.
- Adept @/#/% tags stay creator grammar; provider gets native conditioning slots.
- Prefer reconnect: qwen2512.ref (single) and Qwen Edit 2509 EditPlus (multi).
"""

from __future__ import annotations

from typing import Any

# Cinematic Image Studio categories that mean "Image Generator general plate"
# (not ERS / CRS / Scene Creator purposes with their own binding laws).
# Co-Director image.generate uses the SAME Strategy A contract.
_CIS_IMAGE_GENERATOR_PURPOSES = frozenset(
    {
        "",
        "general",
        "concept",
        "keyframe",
        "character",
        "location",
        "prop",
        "mood",
        "storyboard",
        "codirector_image_generate",
    }
)

_IDENTITY_KINDS = frozenset({"character", "posecraft"})
_SCENE_KINDS = frozenset({"environment", "location"})
_PROP_KINDS = frozenset({"prop"})

_QWEN2512 = frozenset({"qwen2512", "qwen-image-2512", "qwen_image_2512", "qwen-image2512"})
_ZIMAGE = frozenset({"zimage", "z-image", "z_image"})
_FLUX = frozenset({"flux", "flux1", "flux.1", "flux-dev", "flux-schnell"})
_QWEN_EDIT = frozenset({"qwen_edit_2509", "qwen-edit-2509", "qwen-image-edit-2509"})

_ALREADY_MULTI = frozenset({"qwen_edit_2509.edit"})
_ALREADY_SINGLE = frozenset({"qwen2512.ref", "zimage.ref_edit", "flux.img2img"})


def _norm_family(raw: Any) -> str:
    return str(raw or "").strip().lower().replace("_", "-")


def _is_qwen2512(family: str) -> bool:
    n = _norm_family(family)
    return n in _QWEN2512 or n.startswith("qwen2512.")


def _is_zimage(family: str) -> bool:
    n = _norm_family(family)
    return n in _ZIMAGE or n.startswith("zimage.")


def _is_flux(family: str) -> bool:
    n = _norm_family(family)
    return n in _FLUX or n.startswith("flux.")


def _is_qwen_edit_2509(family: str) -> bool:
    n = _norm_family(family)
    return n in _QWEN_EDIT or n.startswith("qwen-edit-2509") or n.startswith("qwen-image-edit-2509")


def is_cis_image_generator_purpose(purpose: str | None) -> bool:
    return str(purpose or "").strip().lower() in _CIS_IMAGE_GENERATOR_PURPOSES


def _push_typed_row(
    item: dict[str, Any],
    out: list[dict[str, Any]],
    seen: set[str],
    *,
    default_kind: str = "other",
) -> None:
    asset_id = str(
        item.get("assetId") or item.get("asset_id") or item.get("id") or ""
    ).strip()
    if not asset_id or asset_id in seen:
        return
    kind = str(
        item.get("kind") or item.get("role") or item.get("type") or default_kind
    ).strip().lower()
    if kind in {"env", "location", "scene"}:
        kind = "environment"
    if kind in {"pose", "pose_craft"}:
        kind = "posecraft"
    if kind not in {"character", "prop", "environment", "posecraft", "other"}:
        kind = "other"
    row = {
        "assetId": asset_id,
        "kind": kind,
        "name": str(item.get("name") or item.get("label") or "").strip(),
        "chip": str(item.get("chip") or item.get("token") or "").strip(),
        "key": str(item.get("key") or f"{kind}:{asset_id}").strip(),
    }
    # Provider-native slot labels (Adept tags stay in chip/name).
    if kind in _IDENTITY_KINDS:
        row["slot"] = "IDENTITY_REFERENCE"
    elif kind in _SCENE_KINDS:
        row["slot"] = "SCENE_REFERENCE"
    elif kind in _PROP_KINDS:
        row["slot"] = "PROP_REFERENCE"
    else:
        row["slot"] = "REFERENCE"
    out.append(row)
    seen.add(asset_id)


def normalize_authority_references(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Preserve typed kinds from AuthorityReferencePanel through the generate body.

    Accepts authorityReferences / authorityRefs / selected* / references (typed
    rows) and falls back to bare referenceAssetIds as kind=other so ids are
    never dropped. Never invents identity from names or prose.
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _push(item: dict[str, Any], default_kind: str = "other") -> None:
        _push_typed_row(item, out, seen, default_kind=default_kind)

    for key in ("authorityReferences", "authorityRefs", "typedReferences"):
        raw = body.get(key)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    _push(item)

    for key, default_kind in (
        ("selectedCharacters", "character"),
        ("selectedProps", "prop"),
        ("selectedPoseCraft", "posecraft"),
        ("selectedGeneric", "other"),
    ):
        raw = body.get(key)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    _push(item, default_kind)
        elif isinstance(raw, dict):
            _push(raw, default_kind)

    env = body.get("selectedEnvironment")
    if isinstance(env, list):
        for item in env:
            if isinstance(item, dict):
                _push(item, "environment")
    elif isinstance(env, dict):
        _push(env, "environment")

    raw_refs = body.get("references")
    if isinstance(raw_refs, list):
        for item in raw_refs:
            if isinstance(item, dict) and (
                item.get("assetId") or item.get("asset_id") or item.get("kind") or item.get("role")
            ):
                _push(item)

    for aid in body.get("referenceAssetIds") or body.get("referenceIds") or []:
        aid_s = str(aid or "").strip()
        if aid_s:
            _push({"assetId": aid_s, "kind": "other"})

    single = str(body.get("referenceImage") or body.get("reference_image") or "").strip()
    if single:
        _push({"assetId": single, "kind": "other"})

    return out


def pick_identity_and_scene(
    typed: list[dict[str, Any]],
) -> tuple[str | None, str | None, list[str]]:
    """Primary identity plate + environment plate + ordered asset ids."""
    ids = [str(r["assetId"]) for r in typed if r.get("assetId")]
    identity = next(
        (str(r["assetId"]) for r in typed if r.get("kind") in _IDENTITY_KINDS),
        None,
    )
    scene = next(
        (str(r["assetId"]) for r in typed if r.get("kind") in _SCENE_KINDS),
        None,
    )
    if not identity and ids:
        # Untyped dual stack: first = identity, second = scene when two present.
        identity = ids[0]
        if not scene and len(ids) >= 2:
            scene = ids[1]
    elif identity and not scene and len(ids) >= 2:
        for aid in ids:
            if aid != identity:
                scene = aid
                break
    return identity, scene, ids


def _bind_qwen_edit_2509_multi(
    body: dict[str, Any],
    creative: dict[str, Any],
    typed: list[dict[str, Any]],
    identity: str | None,
    scene: str | None,
    ids: list[str],
) -> dict[str, Any]:
    """Path A: Qwen Edit 2509 multi-image binder (IDENTITY + SCENE)."""
    id_asset = identity or ids[0]
    scene_asset = scene or next((a for a in ids if a != id_asset), None)
    if not scene_asset:
        raise RuntimeError(
            "This Image Generator selection needs both a character plate and an "
            "environment plate bound as pixels, but a second reference image is "
            "missing. Attach @character and #environment (or two library refs)."
        )
    body["forceWorkflowKey"] = "qwen_edit_2509.edit"
    body["allow_force_workflow_key"] = True
    body["allowDraft"] = True
    body["allow_draft"] = True
    # Adapter switch is honest: locked qwen2512 cannot dual-bind on .ref alone.
    body["modelFamilyPreference"] = "qwen_edit_2509"
    body["model"] = "qwen_edit_2509"
    body["operation"] = "image.edit"
    body["edit"] = True
    body["sourceAssetId"] = id_asset
    body["referenceImage"] = id_asset
    body["sceneReferenceAssetId"] = scene_asset
    body["referenceKind"] = "IDENTITY_REFERENCE"
    creative["referenceKind"] = "IDENTITY_REFERENCE"
    creative["sceneReferenceAssetId"] = scene_asset
    creative["workflowKey"] = "qwen_edit_2509.edit"
    creative["referenceBinding"] = {
        "strategy": "qwen_edit_2509.multi_ref",
        "identityAssetId": id_asset,
        "sceneAssetId": scene_asset,
        "identitySlot": "IDENTITY_REFERENCE",
        "sceneSlot": "SCENE_REFERENCE",
        "reason": (
            "qwen2512.ref binds one LoadImage only; CIS dual character+environment "
            "routes through Qwen Edit 2509 TextEncodeQwenImageEditPlus (image1+image2)."
        ),
        "authorityReferences": typed,
    }
    body["creativeContext"] = creative
    return body


def apply_cis_reference_binding(body: dict[str, Any]) -> dict[str, Any]:
    """Mutate compile body so CIS refs bind pixels (or fail closed). Never silent T2I.

    Strategy:
    - Stamp IMAGE_I2I when refs present (unless a more specific taskType already set).
    - zimage + refs -> image.edit / zimage.ref_edit (existing certified path).
    - qwen2512 + single ref -> force qwen2512.ref (Certified LoadImage).
    - qwen2512 + identity+scene (or 2+ plates) -> Qwen Edit 2509 EditPlus
      image1=IDENTITY_REFERENCE, image2=SCENE_REFERENCE (CC multi-ref pattern).
    - Locked family with no binder -> RuntimeError (honest), never txt2img.
    """
    purpose = str(body.get("purpose") or "").strip().lower()
    if not is_cis_image_generator_purpose(purpose):
        return body

    typed = normalize_authority_references(body)
    if not typed:
        return body

    body["authorityReferences"] = typed
    body["referenceAssetIds"] = list(
        dict.fromkeys(
            list(body.get("referenceAssetIds") or [])
            + [r["assetId"] for r in typed]
        )
    )

    existing_task = str(body.get("taskType") or "").strip()
    if existing_task not in {"POSE_CONDITIONED_IMAGE"}:
        body["taskType"] = "IMAGE_I2I"

    creative = dict(body.get("creativeContext") or {}) if isinstance(body.get("creativeContext"), dict) else {}
    creative["authorityReferences"] = typed
    creative["reference_image_ids"] = list(body["referenceAssetIds"])
    creative.setdefault("taskType", body.get("taskType"))
    body["creativeContext"] = creative

    family = _norm_family(
        body.get("modelFamilyPreference") or body.get("model") or body.get("modelId") or ""
    )
    if family in {"qwen-image-2512", "qwen_image_2512"}:
        family = "qwen2512"
        body["modelFamilyPreference"] = "qwen2512"

    identity, scene, ids = pick_identity_and_scene(typed)
    char_plus_env = bool(identity and scene and identity != scene)
    multi = char_plus_env or (
        len(ids) >= 2 and (_is_qwen2512(family) or _is_qwen_edit_2509(family) or purpose == "codirector_image_generate")
    )

    # Already pinned by caller (e.g. ERS-style force) — keep, but still refuse T2I.
    existing_force = str(body.get("forceWorkflowKey") or "").strip()
    if existing_force.endswith(".txt2img") and typed:
        body.pop("forceWorkflowKey", None)
        existing_force = ""

    # Idempotent: compile may run after CD already applied Strategy A.
    if existing_force in _ALREADY_MULTI:
        return body
    if existing_force in _ALREADY_SINGLE and not multi:
        return body

    # CD rule: char+env OR 2+ typed plates always take Edit 2509
    # (IDENTITY image1 + SCENE image2), regardless of the locked family.
    if purpose == "codirector_image_generate" and multi:
        return _bind_qwen_edit_2509_multi(body, creative, typed, identity, scene, ids)

    if _is_zimage(family):
        # Certified zimage.ref_edit path (IMAGE_I2I).
        src = str(body.get("sourceAssetId") or body.get("source_asset_id") or "").strip()
        if not src:
            body["sourceAssetId"] = identity or ids[0]
        body["operation"] = "image.edit"
        body.pop("edit", None)
        body["edit"] = True
        if not existing_force:
            body["forceWorkflowKey"] = "zimage.ref_edit"
            body["allow_force_workflow_key"] = True
        creative["referenceBinding"] = {
            "strategy": "zimage.ref_edit",
            "identityAssetId": body.get("sourceAssetId"),
            "authorityReferences": typed,
        }
        body["creativeContext"] = creative
        return body

    if _is_qwen2512(family) or family in {"qwen", "qwen-image"} or _is_qwen_edit_2509(family):
        if multi:
            return _bind_qwen_edit_2509_multi(body, creative, typed, identity, scene, ids)

        # Single-ref: certified qwen2512.ref (generate-with-reference, not edit refuse).
        id_asset = identity or ids[0]
        body["forceWorkflowKey"] = "qwen2512.ref"
        body["allow_force_workflow_key"] = True
        body["operation"] = "image.generate"
        body.pop("edit", None)
        body["referenceImage"] = id_asset
        # Do not copy identity into sourceAssetId (ref_generate_pixels law).
        creative["referenceKind"] = "IDENTITY_REFERENCE"
        creative["workflowKey"] = "qwen2512.ref"
        creative["referenceBinding"] = {
            "strategy": "qwen2512.ref",
            "identityAssetId": id_asset,
            "authorityReferences": typed,
        }
        body["creativeContext"] = creative
        return body

    # CD convention: flux + exactly one typed ref keeps certified img2img.
    # Dual typed refs (char+env / 2+ plates) still take Strategy A edit.
    if purpose == "codirector_image_generate" and _is_flux(family):
        if multi:
            return _bind_qwen_edit_2509_multi(body, creative, typed, identity, scene, ids)
        src = str(body.get("sourceAssetId") or body.get("source_asset_id") or "").strip()
        if not src:
            body["sourceAssetId"] = identity or ids[0]
        if not existing_force:
            body["forceWorkflowKey"] = "flux.img2img"
            body["allow_force_workflow_key"] = True
        creative["referenceBinding"] = {
            "strategy": "flux.img2img",
            "identityAssetId": body.get("sourceAssetId"),
            "authorityReferences": typed,
        }
        creative["workflowKey"] = "flux.img2img"
        body["creativeContext"] = creative
        return body

    # Locked family with refs but no known pixel binder — fail closed.
    if body.get("lockModelFamily") and family:
        raise RuntimeError(
            f"Selected model '{family}' cannot use an attached picture as pixel "
            "conditioning for this Image Generator plate. Remove the reference, or "
            "choose Qwen Image 2512 / Z-Image / Qwen Edit 2509 (multi-ref)."
        )

    return body


def refuse_silent_txt2img_if_needed(body: dict[str, Any], workflow_key: str | None) -> None:
    """Last-line honesty after resolve: refs + *.txt2img is never OK for CIS / CD."""
    typed = body.get("authorityReferences") or body.get("referenceAssetIds") or []
    if not typed:
        return
    if not is_cis_image_generator_purpose(str(body.get("purpose") or "")):
        return
    key = str(workflow_key or "").strip().lower()
    if key.endswith(".txt2img"):
        raise RuntimeError(
            f"Refusing silent txt2img ({key}) while reference images are selected. "
            "Image Generator must bind pixels (qwen2512.ref / Qwen Edit 2509 multi-ref / "
            "zimage.ref_edit) or fail closed."
        )
