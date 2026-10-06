"""Structured generationIntent merge for Co-Director image.generate.

Lock precedence (highest -> lowest) — documented once, enforced in merge:
  1. User-locked stamps already on the CIS/CD body:
       visualStyle, lighting.setup/presetId, colorGrade, camera
     Sources: body.*, creativeContext.*, cinematic.*, planning.controls / planning.*
  2. CD capability suggestions (e.g. visual_style arg) — fill gaps only
  3. Bible / compile_creative_context suggestions — fill gaps only

Strategy A (cis_ref_binding) is intentionally NOT applied here. Callers must
keep Strategy A as the LAST binder after creative locks are stamped.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Optional


# Fields treated as creator locks when present (non-empty) on the request body.
LOCKED_CREATIVE_FIELDS = ("visualStyle", "lighting", "colorGrade", "camera")


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _nonempty_str(value: Any) -> str:
    text = str(value or "").strip()
    return text


def _first_str(*candidates: Any) -> str:
    for raw in candidates:
        text = _nonempty_str(raw)
        if text:
            return text
    return ""


def _lighting_from(value: Any) -> dict[str, str]:
    """Normalize lighting lock to {setup, presetId}."""
    if isinstance(value, Mapping):
        setup = _first_str(
            value.get("setup"),
            value.get("presetId"),
            value.get("direction"),
            value.get("id"),
        )
        preset = _first_str(value.get("presetId"), value.get("setup"), value.get("id"))
        out: dict[str, str] = {}
        if setup:
            out["setup"] = setup
        if preset:
            out["presetId"] = preset
        return out
    text = _nonempty_str(value)
    if not text:
        return {}
    return {"setup": text, "presetId": text}


def _camera_from(
    *,
    cinematography: Mapping[str, Any] | None = None,
    cinematic: Mapping[str, Any] | None = None,
    body: Mapping[str, Any] | None = None,
    planning: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cine = _as_dict(cinematography)
    cbody = _as_dict(cinematic)
    src = _as_dict(body)
    plan = _as_dict(planning)
    controls = _as_dict(plan.get("controls"))
    camera: dict[str, Any] = {}
    lens = _first_str(
        cine.get("lens"),
        cbody.get("lens"),
        controls.get("lens"),
        plan.get("lens"),
        src.get("lens"),
    )
    shot = _first_str(
        cine.get("shotIntent"),
        cine.get("shotSize"),
        cbody.get("shotIntent"),
        controls.get("shotIntent"),
        plan.get("shotIntent"),
    )
    aspect = _first_str(
        cine.get("aspectRatio"),
        cbody.get("aspectRatio"),
        controls.get("aspectRatio"),
        src.get("aspect") or src.get("aspectRatio"),
    )
    custom = _first_str(
        cine.get("customShotIntent"),
        cbody.get("customShotIntent"),
        controls.get("customShotIntent"),
    )
    spatial = _first_str(
        src.get("spatialCameraId"),
        plan.get("spatialCameraId"),
        cine.get("spatialCameraId"),
    )
    if lens:
        camera["lens"] = lens
    if shot:
        camera["shotIntent"] = shot
    if aspect:
        camera["aspectRatio"] = aspect
    if custom:
        camera["customShotIntent"] = custom
    if spatial:
        camera["spatialCameraId"] = spatial
    return camera


def _color_grade_from(
    *,
    visual_language: Mapping[str, Any] | None = None,
    cinematic: Mapping[str, Any] | None = None,
    creative: Mapping[str, Any] | None = None,
    planning: Mapping[str, Any] | None = None,
    body: Mapping[str, Any] | None = None,
) -> str:
    vl = _as_dict(visual_language)
    cbody = _as_dict(cinematic)
    ctx = _as_dict(creative)
    plan = _as_dict(planning)
    controls = _as_dict(plan.get("controls"))
    src = _as_dict(body)
    return _first_str(
        ctx.get("colorGrade"),
        ctx.get("colorGradePreset"),
        vl.get("colorGradePreset"),
        vl.get("colorTreatment"),
        cbody.get("colorGradePreset"),
        cbody.get("colorTreatment"),
        controls.get("colorGradePreset"),
        controls.get("colorTreatment"),
        plan.get("colorGradePreset"),
        plan.get("colorGrade"),
        src.get("colorGradePreset"),
        src.get("colorGrade"),
    )


def extract_user_locked_creative(
    body: Mapping[str, Any] | None = None,
    *,
    planning: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract already-stamped user locks from CIS/CD request shapes.

    Presence = lock. Empty / missing fields are unlocked (Bible/CD may fill).
    """
    src = _as_dict(body)
    ctx = _as_dict(src.get("creativeContext"))
    cinematic = _as_dict(src.get("cinematic"))
    plan = _as_dict(planning)
    controls = _as_dict(plan.get("controls"))

    visual_style = _first_str(
        src.get("visualStyle"),
        ctx.get("visualStyle"),
        cinematic.get("visualStyle"),
        controls.get("visualStyle"),
        plan.get("visualStyle"),
    )
    lighting = _lighting_from(ctx.get("lighting"))
    if not lighting:
        lighting = _lighting_from(
            cinematic.get("lighting")
            or controls.get("lighting")
            or plan.get("lighting")
            or src.get("lighting")
        )
    color_grade = _color_grade_from(
        visual_language=_as_dict(ctx.get("visualLanguage")),
        cinematic=cinematic,
        creative=ctx,
        planning=plan,
        body=src,
    )
    camera = _camera_from(
        cinematography=_as_dict(ctx.get("cinematography")),
        cinematic=cinematic,
        body=src,
        planning=plan,
    )

    locks: dict[str, Any] = {}
    if visual_style:
        locks["visualStyle"] = visual_style
    if lighting:
        locks["lighting"] = lighting
    if color_grade:
        locks["colorGrade"] = color_grade
    if camera:
        locks["camera"] = camera
    return locks


def _bible_suggestions(packaged: Any) -> dict[str, Any]:
    """Map CreativeContext / dict Bible package into gap-fill suggestions."""
    data = packaged.model_dump() if hasattr(packaged, "model_dump") else _as_dict(packaged)
    suggestions: dict[str, Any] = {}
    vl = _as_dict(data.get("visualLanguage"))
    # Bible rarely carries STYLE_REGISTRY keys; accept common aliases if present.
    vs = _first_str(
        data.get("visualStyle"),
        vl.get("visualStyle"),
        vl.get("productionStyle"),
        vl.get("styleKey"),
    )
    if vs:
        suggestions["visualStyle"] = vs
    lighting = _lighting_from(data.get("lighting"))
    if lighting:
        suggestions["lighting"] = lighting
    grade = _first_str(
        data.get("colorGrade"),
        vl.get("colorGradePreset"),
        vl.get("colorTreatment"),
    )
    if grade:
        suggestions["colorGrade"] = grade
    camera = _camera_from(cinematography=_as_dict(data.get("cinematography")))
    if camera:
        suggestions["camera"] = camera
    return suggestions


def _cd_suggestions(
    *,
    visual_style: str = "",
    lighting: Any = None,
    color_grade: str = "",
    camera: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    suggestions: dict[str, Any] = {}
    vs = _nonempty_str(visual_style)
    if vs:
        suggestions["visualStyle"] = vs
    light = _lighting_from(lighting)
    if light:
        suggestions["lighting"] = light
    grade = _nonempty_str(color_grade)
    if grade:
        suggestions["colorGrade"] = grade
    cam = _as_dict(camera)
    if cam:
        suggestions["camera"] = cam
    return suggestions


def _merge_lighting(locked: dict[str, str], suggestion: dict[str, str]) -> dict[str, str]:
    """Per-key fill: locked setup/presetId win; suggestion fills absent keys only."""
    out = dict(suggestion or {})
    out.update({k: v for k, v in (locked or {}).items() if _nonempty_str(v)})
    # Keep setup/presetId aligned when only one side is set.
    if out.get("setup") and not out.get("presetId"):
        out["presetId"] = out["setup"]
    if out.get("presetId") and not out.get("setup"):
        out["setup"] = out["presetId"]
    return out


def _merge_camera(locked: dict[str, Any], suggestion: dict[str, Any]) -> dict[str, Any]:
    out = dict(suggestion or {})
    for key, value in (locked or {}).items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        out[key] = value
    return out


def merge_generation_intent(
    *,
    locked: Mapping[str, Any] | None = None,
    cd_suggestions: Mapping[str, Any] | None = None,
    bible_suggestions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge creative fields with hard lock precedence.

    Precedence table:
      visualStyle | lighting | colorGrade | camera
      ------------|----------|------------|-------
      1 user lock | 1 lock   | 1 lock     | 1 lock
      2 CD gap    | 2 CD gap | 2 CD gap   | 2 CD gap
      3 Bible gap | 3 Bible  | 3 Bible    | 3 Bible

    Unlocked/absent fields may be filled by CD then Bible. Locked fields never
    lose to Bible/CD suggestions.
    """
    locks = _as_dict(locked)
    cd = _as_dict(cd_suggestions)
    bible = _as_dict(bible_suggestions)

    # Start from Bible, overlay CD, then force locks (locks always win).
    merged: dict[str, Any] = {}

    # visualStyle — scalar
    vs = _first_str(locks.get("visualStyle"), cd.get("visualStyle"), bible.get("visualStyle"))
    if vs:
        merged["visualStyle"] = vs

    # lighting — dict with per-key lock
    lighting = _merge_lighting(
        _lighting_from(locks.get("lighting")),
        _merge_lighting(_lighting_from(cd.get("lighting")), _lighting_from(bible.get("lighting"))),
    )
    # Re-apply lock on top (hard win)
    if locks.get("lighting"):
        lighting = _merge_lighting(_lighting_from(locks.get("lighting")), lighting)
    if lighting:
        merged["lighting"] = lighting

    # colorGrade — scalar
    grade = _first_str(locks.get("colorGrade"), cd.get("colorGrade"), bible.get("colorGrade"))
    if grade:
        merged["colorGrade"] = grade

    # camera — dict with per-key lock
    camera = _merge_camera(
        _as_dict(locks.get("camera")),
        _merge_camera(_as_dict(cd.get("camera")), _as_dict(bible.get("camera"))),
    )
    if locks.get("camera"):
        camera = _merge_camera(_as_dict(locks.get("camera")), camera)
    if camera:
        merged["camera"] = camera

    merged["lockPrecedence"] = {
        "order": ["user_locked", "cd_suggestions", "bible_compile"],
        "lockedFields": [k for k in LOCKED_CREATIVE_FIELDS if k in locks and locks.get(k)],
        "filledFromCd": [
            k
            for k in LOCKED_CREATIVE_FIELDS
            if k not in locks
            and k in cd
            and merged.get(k)
        ],
        "filledFromBible": [
            k
            for k in LOCKED_CREATIVE_FIELDS
            if k not in locks
            and k not in cd
            and k in bible
            and merged.get(k)
        ],
    }
    return merged


def apply_generation_intent_to_body(
    body: MutableMapping[str, Any],
    intent: Mapping[str, Any],
) -> dict[str, Any]:
    """Stamp merged generationIntent onto body + creativeContext + cinematic.

    Does not touch reference binding / workflowKey — Strategy A remains the
    last binder for pixel workflow selection.
    """
    if not isinstance(body, MutableMapping):
        return {}
    ctx = body.get("creativeContext")
    if not isinstance(ctx, dict):
        ctx = {}
        body["creativeContext"] = ctx
    cinematic = body.get("cinematic")
    if not isinstance(cinematic, dict):
        cinematic = {}
        body["cinematic"] = cinematic

    vs = _nonempty_str(intent.get("visualStyle"))
    if vs:
        body["visualStyle"] = vs
        ctx["visualStyle"] = vs
        cinematic["visualStyle"] = vs

    lighting = _lighting_from(intent.get("lighting"))
    if lighting:
        ctx["lighting"] = {**_as_dict(ctx.get("lighting")), **lighting}
        cinematic["lighting"] = lighting.get("setup") or lighting.get("presetId")

    grade = _nonempty_str(intent.get("colorGrade"))
    if grade:
        ctx["colorGrade"] = grade
        vl = _as_dict(ctx.get("visualLanguage"))
        vl["colorGradePreset"] = grade
        ctx["visualLanguage"] = vl
        cinematic["colorGradePreset"] = grade

    camera = _as_dict(intent.get("camera"))
    if camera:
        cine_cam = _as_dict(ctx.get("cinematography"))
        for key in ("lens", "shotIntent", "aspectRatio", "customShotIntent"):
            if camera.get(key):
                cine_cam[key] = camera[key]
                cinematic[key] = camera[key]
        ctx["cinematography"] = cine_cam
        if camera.get("spatialCameraId") and not _nonempty_str(body.get("spatialCameraId")):
            body["spatialCameraId"] = camera["spatialCameraId"]

    # Structured intent record for observability / downstream compile.
    generation_intent = {
        "visualStyle": vs or None,
        "lighting": lighting or None,
        "colorGrade": grade or None,
        "camera": camera or None,
        "lockPrecedence": intent.get("lockPrecedence") or {},
    }
    body["generationIntent"] = generation_intent
    ctx["generationIntent"] = generation_intent
    return dict(generation_intent)


def compile_and_apply_generation_intent(
    body: MutableMapping[str, Any],
    *,
    project_id: str = "",
    scene_id: str = "",
    db: Any = None,
    planning: Mapping[str, Any] | None = None,
    visual_style: str = "",
    lighting: Any = None,
    color_grade: str = "",
    camera: Mapping[str, Any] | None = None,
    include_bible: bool = True,
) -> dict[str, Any]:
    """Orchestrate lock extract → Bible/CD gap-fill → stamp on body.

    Call this on CD image.generate AFTER typed authority stamps and BEFORE
    Strategy A (cis_ref_binding). Never rebuilds CIS; never reorders Strategy A.
    """
    locked = extract_user_locked_creative(body, planning=planning)
    cd = _cd_suggestions(
        visual_style=visual_style,
        lighting=lighting,
        color_grade=color_grade,
        camera=camera,
    )
    bible: dict[str, Any] = {}
    if include_bible and project_id:
        try:
            from .compiler import compile_creative_context

            packaged = compile_creative_context(
                project_id=project_id,
                scene_id=scene_id or None,
                db=db,
                objective=str(
                    _as_dict(body.get("creativeContext")).get("objective")
                    or body.get("purpose")
                    or ""
                ),
                # Pass existing creative extras so compiler can deep-merge where supported;
                # locks are still re-applied below and win.
                extra=_as_dict(body.get("creativeContext")),
            )
            bible = _bible_suggestions(packaged)
            # Soft-merge non-locked Bible digest fields into creativeContext for grounding.
            ctx = body.get("creativeContext")
            if not isinstance(ctx, dict):
                ctx = {}
                body["creativeContext"] = ctx
            data = packaged.model_dump() if hasattr(packaged, "model_dump") else _as_dict(packaged)
            for key in (
                "projectIntent",
                "characterIdentity",
                "wardrobe",
                "environment",
                "continuity",
                "approvedReferences",
                "prohibitedChanges",
                "digest",
            ):
                if key in data and data[key] and key not in ctx:
                    ctx[key] = data[key]
            # Gap-fill cinematography / visualLanguage / lighting only when unlocked.
            if "camera" not in locked and data.get("cinematography") and not ctx.get("cinematography"):
                ctx["cinematography"] = data["cinematography"]
            if "colorGrade" not in locked and data.get("visualLanguage"):
                existing_vl = _as_dict(ctx.get("visualLanguage"))
                bible_vl = _as_dict(data.get("visualLanguage"))
                for k, v in bible_vl.items():
                    if k not in existing_vl or not existing_vl.get(k):
                        existing_vl[k] = v
                ctx["visualLanguage"] = existing_vl
            if "lighting" not in locked and data.get("lighting") and not ctx.get("lighting"):
                ctx["lighting"] = data["lighting"]
        except Exception:
            bible = {}

    intent = merge_generation_intent(
        locked=locked,
        cd_suggestions=cd,
        bible_suggestions=bible,
    )
    return apply_generation_intent_to_body(body, intent)
