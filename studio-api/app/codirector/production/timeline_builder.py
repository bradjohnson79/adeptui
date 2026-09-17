"""Create or update a real Timeline BatchBlock from a prepared SceneProductionSpec."""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .contracts import ResolvedReference, SceneProductionSpec
from .errors import TimelineShotCreationError
from .generator_validator import normalize_generator_config, normalize_generator_id

_NAMED_SCENE_RE = re.compile(r"\bnamed\s+([^.,\n]+)", re.I)
_TECHNICAL_SCENE_NAME_RE = re.compile(
    r"\b(hydration|repair\s+fresh|certification|\bcert\b|e2e|playwright|"
    r"unit\s+test|smoke\s+test|qa\s+test|debug\s+scene|canonical\s+tag)\b"
    r"|fresh\s+\d{6,}"
    r"|\d{10,}",
    re.I,
)
_SHEET_SUFFIX_RE = re.compile(
    r"\s+((environment|prop|character)\s+)?reference\s+sheet$|\s+(ers|prs|crs)$|\s+png$",
    re.I,
)
_GENERIC_FILENAMES = frozenset({"front.png", "back.png", "image.png", "sheet.png", "p.png", "hero.png"})


def _clean_story_token(raw: str) -> str:
    text = re.sub(r"\s+", " ", str(raw or "")).strip()
    text = _SHEET_SUFFIX_RE.sub("", text).strip(" -–—")
    text = re.sub(r"(?<=[a-z])Png$", "", text)
    return text[:60].strip()


def is_technical_scene_name(name: str | None) -> bool:
    token = re.sub(r"\s+", " ", str(name or "")).strip()
    if not token:
        return True
    if token.lower() in {"timeline scene", "new scene", "scene"}:
        return True
    return bool(_TECHNICAL_SCENE_NAME_RE.search(token))


def _explicit_creator_title(text: str) -> str:
    match = _NAMED_SCENE_RE.search(text or "")
    if not match:
        return ""
    name = _clean_story_token(match.group(1))
    name = re.sub(r"\s+(using|where|with|for)\s+.*$", "", name, flags=re.I).strip()
    if len(name) < 3 or len(name) > 60:
        return ""
    if is_technical_scene_name(name):
        return ""
    return name


def _story_scene_name(spec: SceneProductionSpec) -> str:
    intent = spec.director_intent
    env = ""
    subjects: list[str] = []
    if intent is not None:
        env = _clean_story_token(intent.environment.name)
        subjects = [_clean_story_token(item.name) for item in intent.subjects if _clean_story_token(item.name)]
    if not env:
        for ref in spec.references:
            if ref.asset_type == "environment":
                env = _clean_story_token(ref.display_name or ref.query)
                if env:
                    break
    if not subjects:
        for ref in spec.references:
            if ref.asset_type in {"prop", "character"}:
                token = _clean_story_token(ref.display_name or ref.query)
                if token and token not in subjects:
                    subjects.append(token)
    shot = str(spec.camera.shot_type or spec.camera_intent or "").strip().lower()
    if env and subjects:
        return f"{subjects[0]} at {env}"
    if env and shot == "establishing":
        return f"{env} Establishing"
    if env:
        return env
    if subjects:
        return subjects[0]
    opening = _clean_story_token((intent.opening_state if intent is not None else "") or spec.scene_intent)
    if opening and not is_technical_scene_name(opening) and len(opening.split()) <= 8:
        return opening
    if shot == "establishing":
        return "Establishing Shot"
    return "New Scene"


def _scene_name(spec: SceneProductionSpec) -> str:
    """Creator-facing title from the shot, not from cert/debug 'named …' clauses."""
    explicit = _explicit_creator_title(spec.source_user_prompt or "")
    if explicit:
        return explicit
    return _story_scene_name(spec)


def _distinctive_filename(filename: str) -> bool:
    token = (filename or "").strip().lower()
    if not token or token in _GENERIC_FILENAMES:
        return False
    return bool(re.search(r"[a-z]{5,}", token))


def _adopt_visible_asset(db: Session, project_id: str, source: Any) -> str:
    from ...config import settings
    from ...db import Asset

    filename = str(getattr(source, "filename", "") or "").strip()
    if _distinctive_filename(filename):
        local = (
            db.query(Asset)
            .filter(Asset.project_id == project_id, Asset.filename == filename)
            .first()
        )
        if local is not None:
            return str(local.id)
    src_path = Path(str(getattr(source, "path", "") or ""))
    if not src_path.is_file():
        return ""
    dest_dir = Path(settings.data_dir) / "assets" / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    new_id = str(uuid.uuid4())
    dest = dest_dir / f"{new_id}{src_path.suffix or '.png'}"
    shutil.copy2(src_path, dest)
    asset = Asset(
        id=new_id,
        project_id=project_id,
        tag=str(getattr(source, "tag", "") or ""),
        kind=str(getattr(source, "kind", "") or "image"),
        filename=filename or dest.name,
        path=str(dest),
        parent_asset_id=str(source.id),
    )
    db.add(asset)
    db.flush()
    return new_id


def _project_local_asset_id(db: Session, project_id: str, asset_id: str) -> str:
    if not asset_id:
        return ""
    from ...db import Asset

    row = db.get(Asset, asset_id)
    if row is None:
        return ""
    if str(row.project_id) == project_id:
        return asset_id
    filename = str(getattr(row, "filename", "") or "")
    if _distinctive_filename(filename):
        hit = (
            db.query(Asset)
            .filter(Asset.project_id == project_id, Asset.filename == filename)
            .first()
        )
        if hit is not None:
            return str(hit.id)
    adopted = _adopt_visible_asset(db, project_id, row)
    if adopted:
        return adopted
    return ""


def _usage_for(asset_type: str) -> str:
    if asset_type == "environment":
        return "environment"
    if asset_type == "character":
        return "identity"
    return "prop"


def _existing_binding_id(
    db: Session,
    project_id: str,
    scene_id: str,
    asset_id: str,
    reference_type: str = "",
) -> str:
    from ...scene_references import repository as ref_repo

    wanted_type = str(reference_type or "").strip().lower()
    for row in ref_repo.list_bindings(db, project_id, scope_type="scene", scope_id=scene_id):
        if str(getattr(row, "asset_id", "") or "") != asset_id:
            continue
        if wanted_type and str(getattr(row, "reference_type", "") or "").strip().lower() != wanted_type:
            continue
        return str(row.id)
    return ""


def _attach_reference(
    db: Session,
    *,
    project_id: str,
    scene_id: str,
    ref: ResolvedReference,
) -> dict[str, str]:
    from ...scene_references.service import attach

    asset_id = _project_local_asset_id(db, project_id, ref.bindable_asset_id or ref.asset_id)
    if not asset_id:
        raise TimelineShotCreationError(
            f"{ref.display_name or ref.query} was resolved but its Library asset is not in this project.",
            details={"query": ref.query, "assetId": ref.bindable_asset_id or ref.asset_id},
        )
    reference_type = ref.asset_type or "prop"
    # Check-first dedupe: retries and re-prepares reuse the existing binding
    # instead of attempting a duplicate attach.
    existing_first = _existing_binding_id(db, project_id, scene_id, asset_id, reference_type)
    if existing_first:
        return {
            "binding_id": existing_first,
            "asset_id": asset_id,
            "identity_id": ref.entity_id or "",
            "reference_sheet_id": ref.reference_sheet_id or "",
            "tag": ref.canonical_tag or "",
            "prompt_name": ref.display_name or ref.query,
            "type": reference_type,
        }
    alias = (ref.canonical_tag or "").lstrip("@#%*") or ref.display_name or ref.query
    body = {
        "asset_id": asset_id,
        "scope_type": "scene",
        "scope_id": scene_id,
        "reference_type": reference_type,
        "usage_modes": [_usage_for(reference_type)],
        "alias": alias,
        "identity_id": ref.entity_id or None,
        "enabled": True,
    }
    try:
        result = attach(db, project_id, body, actor="codirector")
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        existing_id = _existing_binding_id(db, project_id, scene_id, asset_id, reference_type)
        if existing_id:
            return {
                "binding_id": existing_id,
                "asset_id": asset_id,
                "identity_id": ref.entity_id or "",
                "reference_sheet_id": ref.reference_sheet_id or "",
                "tag": ref.canonical_tag or "",
                "prompt_name": ref.display_name or ref.query,
                "type": reference_type,
            }
        detail = getattr(exc, "detail", None)
        if isinstance(detail, dict) and detail.get("code") == "CROSS_PROJECT_ASSET_DENIED":
            raise TimelineShotCreationError(
                f"{ref.display_name or ref.query} could not be bound: the asset is not in this project.",
                details={"query": ref.query, "assetId": asset_id},
            ) from exc
        raise TimelineShotCreationError(
            f"{ref.display_name or ref.query} could not be bound: {exc}",
            details={"query": ref.query},
        ) from exc
    binding_id = str(
        (result or {}).get("id")
        or (result or {}).get("bindingId")
        or ((result or {}).get("binding") or {}).get("id")
        or ""
    )
    if not binding_id:
        raise TimelineShotCreationError(
            f"{ref.display_name or ref.query} attached without a binding id.",
            details={"result": result},
        )
    return {
        "binding_id": binding_id,
        "asset_id": str((result or {}).get("asset_id") or asset_id),
        "identity_id": str((result or {}).get("identity_id") or ref.entity_id or ""),
        "reference_sheet_id": ref.reference_sheet_id or "",
        "tag": ref.canonical_tag or "",
        "prompt_name": ref.display_name or ref.query,
        "type": reference_type,
    }


def _find_existing_batch(master: Any, request_id: str, batch_index: int | None = None) -> Any | None:
    if not request_id:
        return None
    for batch in master.batchBlocks or []:
        meta = getattr(batch, "migrationMetadata", None) or {}
        if str(meta.get("sourceProductionRequestId") or "") != request_id:
            continue
        if batch_index is None:
            return batch
        if int(meta.get("sourceProductionBatchIndex") or 0) == batch_index:
            return batch
    return None


def create_or_update_shot_from_spec(
    db: Session,
    spec: SceneProductionSpec,
    references: list[ResolvedReference],
    compiled_prompt: str,
    batch_prompts: list[str] | None = None,
) -> tuple[str, str, int, str]:
    from ...db import Project
    from ...director_timeline_w46 import service as timeline_service
    from ...director_timeline_w46 import store
    from ...director_timeline_w46.contracts import SceneTimelineMaster
    from ...scene_service import create_scene, list_scenes, update_scene_fields

    project = db.get(Project, spec.project_id)
    if project is None:
        raise TimelineShotCreationError("Project not found.")

    found_refs = [item for item in references if item.status == "found"]
    config = normalize_generator_config(spec)
    generator_id = normalize_generator_id(spec.generator_id)
    scene = None
    if spec.scene_id:
        scene = next((row for row in list_scenes(db, spec.project_id) if row.id == spec.scene_id), None)
    if scene is None:
        wanted = _scene_name(spec)
        ranked: list[tuple[int, str, Any]] = []
        for row in list_scenes(db, spec.project_id):
            if (row.name or "") != wanted:
                continue
            if (row.engine or "") not in {"", generator_id, "minimax-h3"}:
                continue
            loaded = store.load_master(db, spec.project_id, row.id)
            score = 0
            if loaded.get("ok"):
                master = SceneTimelineMaster.model_validate(loaded["master"])
                if _find_existing_batch(master, spec.production_request_id) is not None:
                    score = 2
                elif any((item.migrationMetadata or {}).get("codirectorSceneProduction") for item in (master.batchBlocks or [])):
                    score = 1
            ranked.append((score, str(getattr(row, "updated_at", "") or getattr(row, "created_at", "") or ""), row))
        if ranked:
            ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
            scene = ranked[0][2]
        if scene is None:
            tokens = [tok for tok in re.split(r"[^a-z0-9]+", wanted.lower()) if len(tok) > 3]
            leftovers: list[tuple[str, Any]] = []
            for row in list_scenes(db, spec.project_id):
                if not is_technical_scene_name(row.name):
                    continue
                if (row.engine or "") not in {"", generator_id, "minimax-h3"}:
                    continue
                blob = f"{row.name} {row.prompt or ''}".lower()
                if tokens and not any(tok in blob for tok in tokens):
                    continue
                leftovers.append((str(getattr(row, "updated_at", "") or getattr(row, "created_at", "") or ""), row))
            if leftovers:
                leftovers.sort(key=lambda item: item[0], reverse=True)
                scene = leftovers[0][1]
    if scene is None:
        scene = create_scene(
            db,
            project,
            name=_scene_name(spec),
            engine=generator_id,
            prompt=compiled_prompt,
            duration_sec=float(spec.duration_seconds),
        )
    wanted_name = _scene_name(spec)
    rename = {"name": wanted_name} if is_technical_scene_name(getattr(scene, "name", "")) else {}
    scene = update_scene_fields(
        db,
        scene,
        engine=generator_id,
        prompt=compiled_prompt,
        duration_sec=float(spec.duration_seconds),
        aspect_ratio=spec.aspect_ratio,
        camera_note=spec.camera.shot_type or spec.camera_intent,
        **rename,
    )

    loaded = store.load_master(db, spec.project_id, scene.id)
    if not loaded.get("ok"):
        raise TimelineShotCreationError(loaded.get("error") or "Timeline master could not be loaded.")
    master = SceneTimelineMaster.model_validate(loaded["master"])
    master.sceneGeneratorId = generator_id
    store.save_master(db, spec.project_id, scene.id, master, touch_batches=False)

    batch_count = max(int(spec.batch_count or 1), 1)
    per_batch = float(spec.duration_seconds) / batch_count
    prompts = list(batch_prompts or []) or [compiled_prompt]
    while len(prompts) < batch_count:
        prompts.append(prompts[-1] if prompts else compiled_prompt)

    bindings: list[dict[str, Any]] = []
    binding_ids: list[str] = []
    for ref in found_refs:
        if not ref.bindable_asset_id and not ref.asset_id:
            continue
        attached = _attach_reference(db, project_id=spec.project_id, scene_id=scene.id, ref=ref)
        binding_ids.append(attached["binding_id"])
        bindings.append(
            {
                "binding_id": attached["binding_id"],
                "prompt_name": attached["prompt_name"],
                "type": attached["type"],
                "tag": attached["tag"],
                "asset_id": attached["asset_id"],
                "identity_id": attached["identity_id"],
                "reference_sheet_id": attached["reference_sheet_id"],
            }
        )

    first_batch_id = ""
    first_label = ""
    written_batch_ids: set[str] = set()
    for batch_index in range(batch_count):
        master = SceneTimelineMaster.model_validate(store.load_master(db, spec.project_id, scene.id)["master"])
        batch = _find_existing_batch(master, spec.production_request_id, batch_index)
        if batch is None and batch_index == 0 and spec.shot_id:
            batch = next((item for item in master.batchBlocks if item.id == spec.shot_id), None)
        if batch is None:
            # Retry law: a follow-up revision supersedes this scene's earlier
            # CD-production batches. Adopt them (preferring the same batch
            # index) and re-stamp them with the new request id below, instead
            # of leaving orphans and minting duplicates.
            prior_cd = [
                item
                for item in (master.batchBlocks or [])
                if (item.migrationMetadata or {}).get("codirectorSceneProduction")
                and (item.migrationMetadata or {}).get("sourceProductionRequestId") != spec.production_request_id
                and not getattr(item, "activeJobId", None)
            ]
            same_index = [
                item
                for item in prior_cd
                if (item.migrationMetadata or {}).get("sourceProductionBatchIndex") == batch_index
            ]
            adopted = same_index or prior_cd
            if adopted:
                batch = adopted[0]
        if batch is None:
            unused = [
                item
                for item in (master.batchBlocks or [])
                if not (item.migrationMetadata or {}).get("sourceProductionRequestId")
                and str(getattr(item, "status", "") or "Draft") in {"", "Draft", "Ready"}
                and not getattr(item, "activeJobId", None)
                and all(
                    # Empty batches are reusable; so is the fresh-scene seed
                    # batch, whose only segment text is the scene prompt the
                    # builder itself just wrote (identical to this compile).
                    not (seg.text or "").strip()
                    or (seg.text or "").strip() == compiled_prompt.strip()
                    for seg in (item.promptSegments or [])
                )
            ]
            if unused:
                batch_id = unused[0].id
            else:
                created = timeline_service.add_batch(
                    db,
                    spec.project_id,
                    scene.id,
                    label=(
                        f"{_scene_name(spec)} — Batch {batch_index + 1}"
                        if batch_count > 1
                        else _scene_name(spec)
                    ),
                    planned_duration=per_batch,
                    generator_id=generator_id,
                )
                if not created.get("ok"):
                    raise TimelineShotCreationError(created.get("error") or "Timeline batch could not be created.")
                batch_id = str((created.get("batch") or {}).get("id") or "")
        else:
            batch_id = batch.id

        if not batch_id:
            raise TimelineShotCreationError("Timeline batch id was missing after create.")

        batch_prompt = prompts[batch_index]
        patch = {
            "generatorId": generator_id,
            "plannedDuration": per_batch,
            "h3Resolution": config.get("h3Resolution"),
            "promptSegments": [
                {
                    "start": 0.0,
                    "length": per_batch,
                    "text": batch_prompt,
                    "userDirection": spec.source_user_prompt,
                    "productionPrompt": batch_prompt,
                    "referenceBindingIds": binding_ids,
                    "referenceNameBindings": bindings,
                }
            ],
        }
        patched = timeline_service.patch_batch(db, spec.project_id, scene.id, batch_id, patch)
        if not patched.get("ok"):
            raise TimelineShotCreationError(patched.get("error") or "Timeline batch could not be updated.")

        loaded = store.load_master(db, spec.project_id, scene.id)
        master = SceneTimelineMaster.model_validate(loaded["master"])
        live = next((item for item in master.batchBlocks if item.id == batch_id), None)
        if live is None:
            raise TimelineShotCreationError("Prepared Timeline batch disappeared after save.")
        meta = dict(live.migrationMetadata or {})
        meta["sourceProductionRequestId"] = spec.production_request_id
        meta["sourceProductionBatchIndex"] = batch_index
        meta["codirectorSceneProduction"] = True
        live.migrationMetadata = meta
        live.generatorId = generator_id
        store.save_master(db, spec.project_id, scene.id, master)
        written_batch_ids.add(batch_id)
        if not first_batch_id:
            first_batch_id = batch_id
            first_label = live.label or _scene_name(spec)

    # Structural retry law: when a follow-up reduces the batch count, the
    # scene's surplus Co-Director batches must not linger as stale blocks.
    # Prune CD-produced batches this run did not write — only safe drafts
    # (never executed, no active job, no candidate versions, no execution
    # snapshots). ExecutionSnapshots are immutable provenance keyed by
    # snapshot id and linked via batchBlockId: any batch with a referencing
    # snapshot has history and stays.
    master = SceneTimelineMaster.model_validate(
        store.load_master(db, spec.project_id, scene.id)["master"]
    )
    history_ids = {
        str(getattr(snap, "batchBlockId", "") or "")
        for snap in (master.executionSnapshots or {}).values()
    }
    history_ids.discard("")
    surplus = [
        item
        for item in (master.batchBlocks or [])
        if (item.migrationMetadata or {}).get("codirectorSceneProduction")
        and item.id not in written_batch_ids
        and not getattr(item, "activeJobId", None)
        and str(getattr(item, "status", "") or "Draft") in {"", "Draft", "Ready"}
        and not getattr(item, "candidateVersions", None)
        and item.id not in history_ids
    ]
    if surplus:
        surplus_ids = {item.id for item in surplus}
        master.batchBlocks = [
            item for item in master.batchBlocks if item.id not in surplus_ids
        ]
        # Defensive orphan cleanup — keyed by snapshot id, matched on the
        # snapshot's batchBlockId (never by batch id as dict key).
        master.executionSnapshots = {
            snap_id: snap
            for snap_id, snap in (master.executionSnapshots or {}).items()
            if str(getattr(snap, "batchBlockId", "") or "") not in surplus_ids
        }
        store.save_master(db, spec.project_id, scene.id, master)

    return scene.id, first_batch_id, int(getattr(scene, "index", 0) or 0), first_label
