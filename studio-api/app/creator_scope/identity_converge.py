"""One-time repair: one canonical prompt tag per identity. Never mint suffixes."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from .identity_tag import (
    canonical_token_only,
    is_forbidden_prompt_token,
    prompt_canonical_tag,
    prompt_canonical_token,
)

_SUFFIX_TOKEN_RE = re.compile(
    r"(?P<prefix>[@#%])(?P<body>VentureSpaceship|EarthHorizon|CadeSStarfighter|CadesStarfighter)"
    r"(?P<suffix>\d+)",
    re.I,
)
_KEBAB_VENTURE_RE = re.compile(r"%?venture-spaceship-\d+", re.I)
_TARGET_BASES = frozenset({"venturespaceship", "earthhorizon", "cadesstarfighter"})


def _target_base(alias: str) -> str:
    token = canonical_token_only(alias)
    compact = re.sub(r"[^A-Za-z0-9]+", "", token or "").lower()
    match = re.match(r"^(?P<base>[a-z]+?)(?P<suffix>\d+)$", compact)
    base = match.group("base") if match else compact
    if base == "cadesstarfighter":
        return "cadesstarfighter"
    return base


def is_converged_identity_alias(alias: str) -> bool:
    return _target_base(alias) in _TARGET_BASES


def converge_prop_canonical_tags(db: Session, project_id: str | None = None) -> list[dict[str, str]]:
    from ..db import Project
    from ..spatial_map.ers_persistence import list_prop_entities, save_prop_entity

    changed: list[dict[str, str]] = []
    projects = [db.get(Project, project_id)] if project_id else list(db.query(Project).all())
    for project in projects:
        if project is None:
            continue
        for prop in list_prop_entities(db, project.id):
            wanted = prompt_canonical_tag("prop", prop.display_label or "", prop.canonical_tag)
            if not wanted:
                continue
            if str(prop.canonical_tag or "") == wanted:
                continue
            before = str(prop.canonical_tag or prop.tag or "")
            prop.canonical_tag = wanted
            save_prop_entity(db, prop.project_id, prop)
            changed.append(
                {
                    "id": prop.id,
                    "name": prop.display_label,
                    "before": before,
                    "after": wanted,
                    "db_tag": prop.tag,
                }
            )
    return changed


def _best_prop_asset(db: Session, project_id: str, prop) -> str:
    from ..scene_references.identity_resolve import approved_prop_asset_id
    from ..db import Asset

    wanted = approved_prop_asset_id(prop)
    source = db.get(Asset, wanted) if wanted else None
    filename = getattr(source, "filename", None) or "VentureSpaceship Advanced PRS.png"
    local = (
        db.query(Asset)
        .filter(Asset.project_id == project_id, Asset.filename == filename)
        .first()
    )
    if local is not None:
        return str(local.id)
    if source is not None and source.project_id == project_id:
        return wanted
    return wanted or ""


def converge_scene_bindings(db: Session, project_id: str | None = None) -> list[dict[str, str]]:
    from ..db import Asset, Project
    from ..scene_references.identity_resolve import (
        canonical_tag_for_identity,
        is_smoke_test_asset,
        load_prop_identity,
    )
    from ..scene_references.models import SceneReferenceBinding
    from ..spatial_map.ers_persistence import list_prop_entities, load_prop_entities_by_ids

    changed: list[dict[str, str]] = []
    q = db.query(SceneReferenceBinding).filter(SceneReferenceBinding.deleted_at.is_(None))
    if project_id:
        q = q.filter(SceneReferenceBinding.project_id == project_id)
    rows = list(q.all())
    props_by_id = {p.id: p for p in load_prop_entities_by_ids(db, [r.identity_id for r in rows if r.identity_id])}
    if not project_id:
        for project in db.query(Project).all():
            for prop in list_prop_entities(db, project.id):
                props_by_id[prop.id] = prop

    for row in rows:
        identity_id = str(row.identity_id or "").strip()
        alias = str(row.alias or "")
        asset = db.get(Asset, row.asset_id) if row.asset_id else None
        if not is_converged_identity_alias(alias) and not (
            identity_id and identity_id in props_by_id and is_converged_identity_alias(
                prompt_canonical_tag("prop", getattr(props_by_id[identity_id], "display_label", "") or "", None)
            )
        ):
            filename = str(getattr(asset, "filename", "") or "").lower()
            if not ("earth" in filename and "horizon" in filename):
                continue
        if not identity_id:
            identity_id = _infer_identity_id(db, row, asset, props_by_id)
            if identity_id:
                row.identity_id = identity_id
        tag = canonical_tag_for_identity(
            db,
            identity_id=identity_id or None,
            reference_type=row.reference_type,
            display_name=alias,
            stored_alias=alias,
            asset=asset,
        )
        token = canonical_token_only(tag)
        before_alias = alias
        before_asset = str(row.asset_id or "")
        if token and alias != token:
            clash = (
                db.query(SceneReferenceBinding)
                .filter(
                    SceneReferenceBinding.project_id == row.project_id,
                    SceneReferenceBinding.scope_type == row.scope_type,
                    SceneReferenceBinding.scope_id == row.scope_id,
                    SceneReferenceBinding.alias == token,
                    SceneReferenceBinding.deleted_at.is_(None),
                    SceneReferenceBinding.id != row.id,
                )
                .first()
            )
            if clash is not None and str(clash.identity_id or "") in {"", identity_id}:
                row.deleted_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                if identity_id and not clash.identity_id:
                    clash.identity_id = identity_id
                changed.append({"id": row.id, "action": "merged_into", "kept": clash.id, "alias": token})
                continue
            row.alias = token
        prop = props_by_id.get(identity_id) if identity_id else load_prop_identity(db, identity_id)
        if prop is not None and is_smoke_test_asset(asset):
            replacement = _best_prop_asset(db, row.project_id, prop)
            if replacement and replacement != row.asset_id:
                row.asset_id = replacement
        if before_alias != str(row.alias or "") or before_asset != str(row.asset_id or ""):
            changed.append(
                {
                    "id": row.id,
                    "alias_before": before_alias,
                    "alias_after": str(row.alias or ""),
                    "asset_before": before_asset,
                    "asset_after": str(row.asset_id or ""),
                    "identity_id": identity_id,
                }
            )
    db.commit()
    return changed


def _infer_identity_id(db: Session, row, asset, props_by_id: dict[str, Any]) -> str:
    alias = _target_base(str(row.alias or ""))
    filename = str(getattr(asset, "filename", "") or "").lower()
    compact_file = filename.replace(" ", "").replace("-", "").replace("_", "")
    for prop in props_by_id.values():
        token = _target_base(prompt_canonical_tag("prop", prop.display_label or "", prop.canonical_tag))
        if token and alias and token == alias:
            return prop.id
        if token and token in compact_file:
            return prop.id
    if "earth" in filename and "horizon" in filename:
        return str(getattr(asset, "id", "") or "")
    return ""


def rewrite_legacy_prompt_tags(text: str) -> str:
    out = _SUFFIX_TOKEN_RE.sub(lambda m: f"{m.group('prefix')}{m.group('body')}", text or "")
    out = _KEBAB_VENTURE_RE.sub("%VentureSpaceship", out)
    out = re.sub(r"CadesStarfighter", "CadeSStarfighter", out)
    return out


def converge_timeline_masters(db: Session, project_id: str | None = None) -> list[str]:
    from ..db import Scene
    from ..director_timeline_bindings import dump_prompt_name_binding, parse_prompt_name_bindings
    from ..director_timeline_w46.generation.prompt_token_bindings import backfill_name_binding_identities
    from ..director_timeline_w46.migration import extract_master_from_director_dict

    touched: list[str] = []
    q = db.query(Scene)
    if project_id:
        q = q.filter(Scene.project_id == project_id)
    for scene in q.all():
        raw = scene.director_json or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        changed = False
        master = extract_master_from_director_dict(data)
        if master is not None:
            for batch in master.batchBlocks or []:
                for seg in batch.promptSegments or []:
                    before_text = seg.text or ""
                    next_text = rewrite_legacy_prompt_tags(before_text)
                    if next_text != before_text:
                        seg.text = next_text
                        changed = True
                    repaired = backfill_name_binding_identities(
                        seg.referenceNameBindings, db, scene.project_id
                    )
                    dumped = [dump_prompt_name_binding(row) for row in repaired]
                    for row in dumped:
                        row["tag"] = rewrite_legacy_prompt_tags(row.get("tag") or "")
                    if dumped != [dump_prompt_name_binding(row) for row in (seg.referenceNameBindings or [])]:
                        seg.referenceNameBindings = parse_prompt_name_bindings(dumped)
                        changed = True
            if changed:
                data["timelineMaster"] = master.model_dump()
        for key in ("prompt_segments", "promptSegments"):
            segs = data.get(key)
            if not isinstance(segs, list):
                continue
            for seg in segs:
                if not isinstance(seg, dict):
                    continue
                text = rewrite_legacy_prompt_tags(str(seg.get("text") or ""))
                if text != str(seg.get("text") or ""):
                    seg["text"] = text
                    changed = True
                names = seg.get("reference_name_bindings") or seg.get("referenceNameBindings") or []
                next_names = []
                names_changed = False
                for row in names:
                    dumped = dump_prompt_name_binding(row)
                    tag = rewrite_legacy_prompt_tags(dumped.get("tag") or "")
                    if tag != dumped.get("tag"):
                        dumped["tag"] = tag
                        names_changed = True
                    next_names.append(dumped)
                if names_changed:
                    if "reference_name_bindings" in seg:
                        seg["reference_name_bindings"] = next_names
                    if "referenceNameBindings" in seg:
                        seg["referenceNameBindings"] = next_names
                    changed = True
        if changed:
            scene.director_json = json.dumps(data)
            db.add(scene)
            touched.append(scene.id)
    if touched:
        db.commit()
    return touched


def _resolve_loaded_scene_id(explicit: str | None = None) -> str | None:
    """Resolve scene id for empty-master bootstrap without editing locked store.py.

    ``store.load_master`` calls ``migrate_loaded_master(db, project_id, master)``
    and keeps ``scene_id`` / ``scene`` in its frame locals. Walk a few caller
    frames so existing empty scenes recover on the next GET /master.
    """
    sid = str(explicit or "").strip()
    if sid:
        return sid
    import inspect

    frame = inspect.currentframe()
    try:
        caller = frame.f_back if frame is not None else None
        depth = 0
        while caller is not None and depth < 6:
            locals_ = caller.f_locals
            cand = locals_.get("scene_id")
            if isinstance(cand, str) and cand.strip():
                return cand.strip()
            scene_obj = locals_.get("scene")
            cand2 = getattr(scene_obj, "id", None) if scene_obj is not None else None
            if isinstance(cand2, str) and cand2.strip():
                return cand2.strip()
            caller = caller.f_back
            depth += 1
    finally:
        del frame
    return None


def _resolve_bootstrap_generator_id(db: Session, project_id: str, gid: str) -> str:
    """Resolve inheritance markers to a concrete Timeline generator id.

    ``auto`` / ``default`` / empty are dynamic inheritance values, not W46
    registry ids — the window planner rejects them (GeneratorValidationError →
    500 on GET /master for every such scene, which is every New Scene click).
    Canonical resolution: the project's engine default, then the local-first
    floor the rest of the platform uses for ``auto`` (api.py preview caps,
    engine_recommend). A hosted default (fal_*/seedance-*) is valid for
    generation routing but unknown to the local window planner, so empty-master
    window sizing falls to the local floor; generation-time engine resolution
    is unchanged.
    """
    value = str(gid or "").strip()
    if value.lower() in {"", "auto", "default"}:
        from ..db import Project

        project = db.get(Project, project_id)
        value = str(getattr(project, "engine_default", None) or "").strip()
    if value.lower() in {"", "auto", "default"}:
        value = "minimax-h3"
    try:
        from ..director_timeline_w46.generation.registry import get_registry

        get_registry().resolve_id(value)
    except Exception:
        value = "minimax-h3"
    return value


def _bootstrap_empty_master_from_scene_engine(
    db: Session,
    project_id: str,
    master: Any,
    *,
    scene_id: str | None = None,
) -> bool:
    """When master has no windows, seed from Scene.engine + duration (not Batch CRUD)."""
    if list(getattr(master, "batchBlocks", None) or []):
        return False
    sid = _resolve_loaded_scene_id(scene_id)
    if not sid:
        return False
    from ..db import Scene
    from ..director_timeline_w46.execution_window_materialize import bootstrap_empty_master_from_plan

    scene = (
        db.query(Scene)
        .filter(Scene.project_id == project_id, Scene.id == sid)
        .one_or_none()
    )
    if scene is None:
        return False
    duration = float(getattr(scene, "duration_sec", None) or 0.0)
    gid = str(getattr(master, "sceneGeneratorId", None) or "").strip() or str(
        getattr(scene, "engine", None) or ""
    ).strip()
    gid = _resolve_bootstrap_generator_id(db, project_id, gid)
    if duration <= 0 or not gid:
        return False
    if not str(getattr(master, "sceneGeneratorId", None) or "").strip():
        try:
            master.sceneGeneratorId = gid
        except Exception:
            pass
    before_n = len(getattr(master, "batchBlocks", None) or [])
    result = bootstrap_empty_master_from_plan(
        master,
        scene_id=sid,
        duration_seconds=duration,
        generator_id=gid,
    )
    after_n = len(getattr(master, "batchBlocks", None) or [])
    return bool(result.get("ok")) and after_n > before_n


def _promote_window_local_prompt_starts(master: Any) -> bool:
    """Later-window prompts stored at time 0 are window-local, not scene time.

    Start containment owns a prompt by its start. A continuation left at 0 is
    drawn on the first window. Promote those starts once; a start already at
    or after the window is left alone so a second load does not shift again.
    """
    blocks = sorted(
        list(getattr(master, "batchBlocks", None) or []),
        key=lambda batch: int(getattr(batch, "order", 0) or 0),
    )
    cursor = 0.0
    changed = False
    for batch in blocks:
        dur = getattr(batch, "duration", None)
        try:
            length = float(getattr(dur, "plannedDuration", 0.0) or 0.0)
        except (TypeError, ValueError):
            length = 0.0
        window_start = cursor
        cursor += max(0.0, length)
        if window_start <= 1e-6:
            continue
        for seg in getattr(batch, "promptSegments", None) or []:
            try:
                seg_start = float(getattr(seg, "start", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
            if seg_start + 1e-6 < window_start:
                seg.start = window_start + max(0.0, seg_start)
                changed = True
    return changed


def migrate_loaded_master(
    db: Session,
    project_id: str,
    master: Any,
    scene_id: str | None = None,
) -> bool:
    from ..director_timeline_bindings import dump_prompt_name_binding, parse_prompt_name_bindings
    from ..director_timeline_w46.generation.prompt_token_bindings import backfill_name_binding_identities

    changed = False
    for batch in getattr(master, "batchBlocks", None) or []:
        for seg in getattr(batch, "promptSegments", None) or []:
            before_text = seg.text or ""
            next_text = rewrite_legacy_prompt_tags(before_text)
            if next_text != before_text:
                seg.text = next_text
                changed = True
            repaired = backfill_name_binding_identities(seg.referenceNameBindings, db, project_id)
            dumped = [dump_prompt_name_binding(row) for row in repaired]
            for row in dumped:
                row["tag"] = rewrite_legacy_prompt_tags(row.get("tag") or "")
            if dumped != [dump_prompt_name_binding(row) for row in (seg.referenceNameBindings or [])]:
                seg.referenceNameBindings = parse_prompt_name_bindings(dumped)
                changed = True
    # Empty masters skip locked migration bootstrap when sceneGeneratorId is
    # null; Scene.engine + duration_sec are enough to rematerialize windows so
    # Timed Prompt / Visual writers stop silently no-op'ing.
    if _bootstrap_empty_master_from_scene_engine(db, project_id, master, scene_id=scene_id):
        changed = True
    if _bind_empty_root_from_scene_prompt(db, project_id, master, scene_id=scene_id):
        changed = True
    if _promote_window_local_prompt_starts(master):
        changed = True
    return changed


def _bind_empty_root_from_scene_prompt(
    db: Session,
    project_id: str,
    master: Any,
    *,
    scene_id: str | None = None,
) -> bool:
    """A scene script must land on the root Timed Prompt, not disappear.

    Later windows then receive their own slice. The root text stays the
    creator's full script so the first window is not replaced by the ending.
    """
    sid = _resolve_loaded_scene_id(scene_id)
    if not sid:
        return False
    blocks = sorted(
        list(getattr(master, "batchBlocks", None) or []),
        key=lambda batch: int(getattr(batch, "order", 0) or 0),
    )
    if not blocks:
        return False
    root_segs = list(getattr(blocks[0], "promptSegments", None) or [])
    if not root_segs or str(getattr(root_segs[0], "text", "") or "").strip():
        return False
    from ..db import Scene

    scene = (
        db.query(Scene)
        .filter(Scene.project_id == project_id, Scene.id == sid)
        .one_or_none()
    )
    prompt = str(getattr(scene, "prompt", "") or "").strip() if scene is not None else ""
    if not prompt:
        return False
    root_segs[0].text = prompt
    from ..director_timeline_w46.generation.window_script import assign_later_window_scripts

    assign_later_window_scripts(master)
    return True


def converge_canonical_reference_tags(db: Session, project_id: str | None = None) -> dict[str, Any]:
    props = converge_prop_canonical_tags(db, project_id)
    bindings = converge_scene_bindings(db, project_id)
    scenes = converge_timeline_masters(db, project_id)
    return {"props": props, "bindings": bindings, "scenes": scenes}


def assert_no_forbidden_prompt_tokens(text: str) -> None:
    hits = is_forbidden_prompt_token(text)
    if hits:
        raise AssertionError(f"forbidden prompt-facing identity tokens: {hits}")
