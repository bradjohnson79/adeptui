"""Scene production orchestrator: prepare Timeline state, then generate through Timeline."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from .contracts import (
    PreparedSceneResult,
    PreparationEvent,
    SceneProductionSpec,
)
from .errors import GenerationSubmissionError, ProductionError, ReferenceResolutionError
from .generator_validator import normalize_generator_id, validate_scene_spec_against_generator
from .intent_parser import (
    is_follow_up_edit,
    mentions_aspect_ratio,
    mentions_batch_count,
    mentions_megapixels,
    merge_reference_queries,
    parse_scene_intent,
    production_request_id,
)
from .prompt_compiler import compile_generator_prompt
from .reference_resolver import resolve_project_references
from .scene_breakdown import build_director_scene_intent
from .scene_understanding import LlmFn, extract_scene_understanding
from .timeline_builder import create_or_update_shot_from_spec

CONTEXT_CATEGORY = "codirector_scene_production"
CONTEXT_KEY = "active"


def _event(kind: str, message: str, *, surface: str = "creator", **payload: Any) -> PreparationEvent:
    return PreparationEvent(type=kind, message=message, payload={"surface": surface, **payload})



def build_generator_switch_handoff(
    *,
    previous_generator_id: str,
    new_generator_id: str,
    duration_seconds: float,
    previous_windows: list | None = None,
) -> dict:
    """CD handoff for Timeline Gen / Systems on generator switch (no timeline_builder edits)."""
    from .execution_windows import generator_switch_plan_delta

    delta = generator_switch_plan_delta(
        previous_generator_id=previous_generator_id,
        new_generator_id=new_generator_id,
        duration_seconds=duration_seconds,
        previous_windows=previous_windows,
    )
    return {
        "requiresNewSceneTake": delta.requires_new_scene_take,
        "requiresRevisionBump": delta.requires_revision_bump,
        "reason": delta.reason,
        "previousGeneratorId": delta.previous_generator_id,
        "newGeneratorId": delta.new_generator_id,
        "previousWindows": delta.previous_windows,
        "newWindows": delta.new_windows,
        "newBatchCount": delta.new_batch_count,
        "note": delta.note,
    }


def _human_generator(generator_id: str) -> str:
    token = normalize_generator_id(generator_id)
    if token.startswith("minimax-h3"):
        return "MiniMax H3"
    if token.startswith("ltx"):
        return "LTX 2.5"
    if token.startswith("seedance"):
        return "Seedance"
    return generator_id


def _quality_label(spec: SceneProductionSpec) -> str:
    if spec.megapixels is not None:
        return f"Megapixels {spec.megapixels:g}"
    return spec.quality or "Default"


def _sheet_label(ref) -> str:
    global_bit = "Global " if ref.is_global or ref.verification == "global_found" else ""
    kind = {
        "prop": f"{global_bit}Prop Reference Sheet",
        "environment": f"{global_bit}environment reference",
        "character": f"{global_bit}Character Reference Sheet",
    }.get(ref.asset_type or "", f"{global_bit}Reference")
    return f"{ref.display_name or ref.query} — {kind} found"


_REFERENCE_CONTEXT_RE = re.compile(r"reference|sheet|as\s+the\s+setting|[@#%]", re.I)


def _dedupe_references(references: list[Any]) -> list[Any]:
    """One identity = one reference row (Canonical Tag Law).

    The deterministic parser and the corroborated understanding mentions can
    both surface the same asset; collapse duplicates by canonical tag, falling
    back to normalized name+type when no tag exists yet.
    """
    seen: set[str] = set()
    out: list[Any] = []
    for item in references:
        tag = str(getattr(item, "canonical_tag", "") or "").strip()
        if tag:
            key = f"tag:{tag}"
        else:
            name = str(getattr(item, "display_name", "") or getattr(item, "query", "") or "")
            kind = str(getattr(item, "asset_type", "") or getattr(item, "expected_type", "") or "")
            key = f"name:{kind}:{re.sub(r'[^a-z0-9]+', '', name.lower())}"
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
_SENTENCE_START_RE = re.compile(r"(?:^|[.!?]\s+)$")
_NAME_STOPWORDS = frozenset({"of", "the", "de", "del", "van", "von", "la", "le", "di", "da"})


def _corroborated_asset_mentions(understanding: Any, source_text: str) -> list[tuple[str, str]]:
    """Filter understanding-extracted asset mentions to plausible references.

    The understanding layer (LLM or fallback) may list descriptive scenery
    ("distant mountains", "thick fog") as assets. Reference verification must
    never chase scenery: a mention only becomes a reference query when the
    creator's own words corroborate it as an invoked identity — the creator
    wrote it as a proper noun (capitalized mid-sentence, or a multi-word
    capitalized phrase) or it sits in explicit reference language
    ("reference sheet", "@tag", "as the setting").
    """
    source = source_text or ""
    out: list[tuple[str, str]] = []
    for asset in getattr(understanding, "assets", []) or []:
        name = str(getattr(asset, "name", "") or "").strip()
        if not name or len(name) < 2 or len(name) > 80:
            continue
        pattern = re.compile(r"\b" + re.escape(name) + r"\b", re.I)
        matches = list(pattern.finditer(source))
        if not matches:
            continue  # the creator never wrote these words
        proper_noun = False
        for match in matches:
            token = source[match.start() : match.end()]  # creator's own casing
            if not any(char.isupper() for char in token):
                continue  # lowercase descriptive mention
            if " " in name:
                # Multi-word proper-noun phrase: every content word capitalized
                # ("Mara Voss", "Salt Flats") — not a sentence-start capital on
                # a descriptive phrase ("Thick fog ...").
                words = [w for w in re.split(r"\s+", token) if w]
                if words and all(
                    w[0].isupper() or w.lower() in _NAME_STOPWORDS for w in words
                ):
                    proper_noun = True
                    break
                continue
            if not _SENTENCE_START_RE.search(source[: match.start()]):
                proper_noun = True  # capitalized mid-sentence
                break
        if proper_noun:
            out.append((name, str(getattr(asset, "hinted_type", "") or "")))
            continue
        mention = matches[0]
        window = source[max(0, mention.start() - 60) : mention.end() + 30]
        if _REFERENCE_CONTEXT_RE.search(window):
            out.append((name, str(getattr(asset, "hinted_type", "") or "")))
    return out


def load_active_production(db: Session, project_id: str) -> dict[str, Any]:
    from ...db import ProjectTraitRow

    row = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == project_id,
            ProjectTraitRow.category == CONTEXT_CATEGORY,
            ProjectTraitRow.key == CONTEXT_KEY,
        )
        .first()
    )
    if row is None or not row.value:
        return {}
    try:
        data = json.loads(row.value)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_active_production(db: Session, project_id: str, payload: dict[str, Any]) -> None:
    from ...db import ProjectTraitRow

    raw = json.dumps(payload)
    row = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == project_id,
            ProjectTraitRow.category == CONTEXT_CATEGORY,
            ProjectTraitRow.key == CONTEXT_KEY,
        )
        .first()
    )
    if row:
        row.value = raw
        row.provenance = "CODEX_SCENE_PRODUCTION"
    else:
        db.add(
            ProjectTraitRow(
                id=str(uuid4()),
                project_id=project_id,
                category=CONTEXT_CATEGORY,
                key=CONTEXT_KEY,
                value=raw,
                provenance="CODEX_SCENE_PRODUCTION",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        )
    db.commit()


_SCENE_NUMBER_RE = re.compile(r"\bscene\s+(\d{1,3})\b", re.I)


def _address_scene_by_number(db: Session, project_id: str, message: str) -> str:
    """'For Scene 3' / 'Scene 3' → the project's scene with that index or name."""
    match = _SCENE_NUMBER_RE.search(message or "")
    if not match:
        return ""
    try:
        wanted = int(match.group(1))
    except ValueError:
        return ""
    if wanted < 1:
        return ""
    try:
        from ...scene_service import list_scenes

        scenes = list(list_scenes(db, project_id) or [])
    except Exception:
        return ""
    by_name = next(
        (row for row in scenes if (getattr(row, "name", "") or "").strip().lower() == f"scene {wanted}"),
        None,
    )
    if by_name is not None:
        return str(by_name.id)
    ordered = sorted(scenes, key=lambda row: int(getattr(row, "index", 0) or 0))
    if wanted <= len(ordered):
        return str(ordered[wanted - 1].id)
    return ""


def prepare_production_request(
    db: Session,
    *,
    project_id: str,
    message: str,
    scene_id: str = "",
    llm_fn: LlmFn | None = None,
    allow_llm: bool = True,
) -> PreparedSceneResult:
    events: list[PreparationEvent] = []
    try:
        active = load_active_production(db, project_id)
        follow_up = bool(active.get("shotId") and is_follow_up_edit(message))
        prior_spec: SceneProductionSpec | None = None
        if follow_up and active.get("spec"):
            try:
                prior_spec = SceneProductionSpec.model_validate(active["spec"])
            except Exception:
                prior_spec = None

        # Retry law: a follow-up edit re-synthesizes from the ORIGINAL request
        # plus the revision — never from the edit text alone.
        understanding_input = message
        if follow_up and prior_spec is not None and prior_spec.source_user_prompt:
            understanding_input = (
                f"{prior_spec.source_user_prompt}\n\nCreator revision: {message}"
            )

        spec = parse_scene_intent(message, project_id=project_id, follow_up=follow_up)
        if follow_up:
            spec.scene_id = str(active.get("sceneId") or scene_id or "")
            spec.shot_id = str(active.get("shotId") or "")
            spec.generator_id = str(active.get("generatorId") or spec.generator_id)
            spec.source_user_prompt = understanding_input
            if prior_spec is not None:
                if not spec.reference_queries:
                    spec.reference_queries = prior_spec.reference_queries
                if not spec.scale_relationships:
                    spec.scale_relationships = prior_spec.scale_relationships
                if spec.duration_seconds == 10.0 and not re.search(r"\d+(?:\.\d+)?\s*-?\s*seconds?", message, re.I):
                    spec.duration_seconds = prior_spec.duration_seconds
                # Batch count: inherit the prior count only when the edit does
                # not state one. An explicit "1 batch" / "single batch" is an
                # intentional structural reduction and must be honored.
                # P2+: do not inherit creator/prior batch_count — capability replans.
                # Retry law: an edit that does not mention aspect, quality, or
                # camera inherits them from the validated prior spec — a
                # follow-up must never silently reset the scene to 16:9 or
                # drop the camera plan.
                if not mentions_aspect_ratio(message):
                    spec.aspect_ratio = prior_spec.aspect_ratio
                if not mentions_megapixels(message):
                    spec.megapixels = prior_spec.megapixels
                    spec.quality = prior_spec.quality
                if not spec.camera.shot_type and prior_spec.camera.shot_type:
                    spec.camera = prior_spec.camera
                    spec.camera_intent = prior_spec.camera_intent
            # Retry law: the idempotency key must reflect the EFFECTIVE spec
            # (restored duration/batches/references), not the bare edit text —
            # otherwise a follow-up mints a new request id and duplicates
            # Timeline batches instead of re-synthesizing them in place.
            spec.production_request_id = production_request_id(project_id, spec)
        elif scene_id:
            spec.scene_id = scene_id
        elif not spec.scene_id:
            addressed = _address_scene_by_number(db, project_id, message)
            if addressed:
                spec.scene_id = addressed

        events.append(_event("preparing", "Preparing scene..."))
        events.append(_event("target_resolved", "Timeline selected", target="timeline"))
        events.append(
            _event(
                "generator_resolved",
                _human_generator(spec.generator_id),
                generatorId=spec.generator_id,
            )
        )

        # Layer B understanding runs BEFORE reference resolution so asset
        # mentions the deterministic parser missed still get resolved.
        understanding, understanding_source, fallback_reason = extract_scene_understanding(
            understanding_input,
            llm_fn=llm_fn,
            allow_llm=allow_llm,
        )
        if fallback_reason:
            events.append(
                _event(
                    "understanding_fallback",
                    "Advanced scene analysis unavailable; used deterministic cinematic breakdown.",
                    surface="debug",
                    reason=fallback_reason,
                )
            )
        if understanding.assets:
            merge_reference_queries(
                spec,
                _corroborated_asset_mentions(understanding, understanding_input),
            )

        events.append(
            _event(
                "config_resolved",
                f"Runtime settings extracted — {spec.duration_seconds:g}s, {spec.aspect_ratio}, "
                f"{spec.batch_count} batch(es), {_human_generator(spec.generator_id)}",
                durationSeconds=spec.duration_seconds,
                aspectRatio=spec.aspect_ratio,
                batchCount=spec.batch_count,
            )
        )
        events.append(
            _event(
                "config_resolved",
                f"Quality: {_quality_label(spec)}.",
                surface="debug",
                quality=spec.quality,
            )
        )

        spec.preparation_state = "resolving_references"
        events.append(_event("references_started", "Resolving project references...", surface="debug"))
        resolved = resolve_project_references(db, project_id=project_id, queries=spec.reference_queries)
        if follow_up and prior_spec is not None:
            # Retry law: validated prior bindings are reused; only newly named
            # assets go through resolution.
            prior_found = {
                (item.asset_type or item.expected_type or "", item.display_name.lower()): item
                for item in prior_spec.references
                if item.status == "found"
            }
            merged: list = []
            for item in resolved:
                key = (item.asset_type or item.expected_type or "", (item.display_name or item.query).lower())
                if item.status != "found" and key in prior_found:
                    merged.append(prior_found[key])
                else:
                    merged.append(item)
            resolved = merged
        # One identity = one reference row. The parser and the corroborated
        # understanding mentions can both surface the same asset; collapse by
        # canonical tag (or normalized name+type when no tag exists yet) so the
        # creator-facing list, SUBJECTS, and CONTINUITY sections never duplicate.
        resolved = _dedupe_references(resolved)
        spec.references = resolved
        missing = [item for item in resolved if item.status == "missing"]
        ambiguous = [item for item in resolved if item.status == "ambiguous"]
        wrong = [item for item in resolved if item.status == "wrong_type"]
        broken = [item for item in resolved if item.status == "broken"]
        for item in resolved:
            if item.status == "found":
                events.append(
                    _event(
                        "reference_found",
                        _sheet_label(item),
                        assetId=item.asset_id,
                        displayName=item.display_name,
                        assetType=item.asset_type,
                        canonicalTag=item.canonical_tag,
                        verification=item.verification,
                        isGlobal=item.is_global,
                        notes=item.notes,
                    )
                )
            elif item.status == "missing":
                kind = {
                    "prop": "Prop Reference Sheet",
                    "environment": "environment reference",
                    "character": "Character Reference Sheet",
                }.get(item.expected_type or "", "reference")
                events.append(
                    _event(
                        "reference_missing",
                        f"{item.query} — {kind} missing",
                        query=item.query,
                    )
                )
            elif item.status == "broken":
                events.append(
                    _event(
                        "reference_broken",
                        f"{item.display_name or item.query} — binding broken",
                        query=item.query,
                    )
                )
            elif item.status == "ambiguous":
                events.append(_event("reference_ambiguous", f"{item.query} matched more than one asset.", query=item.query))
            else:
                events.append(_event("reference_wrong_type", f"{item.query} is the wrong reference type.", query=item.query))
        if missing or ambiguous or wrong or broken:
            raise ReferenceResolutionError(
                " ".join(
                    ev.message
                    for ev in events
                    if ev.type.startswith("reference_") and ev.type != "reference_found"
                ),
                details={
                    "missing": [m.query for m in missing],
                    "ambiguous": [m.query for m in ambiguous],
                    "broken": [m.query for m in broken],
                },
            )

        spec.preparation_state = "validating_generator"
        events.append(
            _event(
                "generator_validating",
                f"Checking {_human_generator(spec.generator_id)} capabilities...",
                surface="debug",
                generatorId=spec.generator_id,
            )
        )

        # Generator-aware batch planning (capability law): the batch count and
        # temporal windows come from the generator's certified single-generation
        # window in the Timeline capability registry — never a hardcoded
        # threshold. A creator-stated count is honored only when every window
        # still fits the certified maximum.
        # REBUILD LAW: planning runs BEFORE generator validation. The validator
        # checks the PLANNED windows (per_batch_duration prefers spec.batchWindows);
        # validating an unplanned even-split first used to reject over-window
        # scenes (e.g. "37 seconds" on H3) before the planner could resolve the
        # batch count — blocking capability-driven long-scene planning.
        from .execution_windows import plan_spec_execution_windows

        # CLEAR P2+: creator batchCount / chat "N batches" is NON-AUTHORITATIVE.
        # Execution Windows come only from duration + generator capability.
        _prev_count, _plan_windows = plan_spec_execution_windows(spec)
        spec.batch_count = _prev_count
        spec.batchWindows = list(_plan_windows)
        events.append(
            _event(
                "batch_plan_resolved",
                (
                    f"{spec.batch_count} Execution Window plan — "
                    + ", ".join(
                        f"{float(w.get('start', 0)):g}–{float(w.get('end', 0)):g}s"
                        for w in _plan_windows
                    )
                    + f" ({_human_generator(spec.generator_id)} certified single-generation window; "
                    "creator batch count ignored)"
                ),
                surface="debug",
                batchCount=spec.batch_count,
                batchWindows=spec.batchWindows,
                creatorBatchCountIgnored=True,
            )
        )
        spec.production_request_id = production_request_id(project_id, spec)

        validate_scene_spec_against_generator(spec)

        intent = build_director_scene_intent(
            spec,
            resolved,
            understanding=understanding,
            understanding_source=understanding_source,
            fallback_reason=fallback_reason,
        )
        spec.director_intent = intent
        spec.scene_intent = intent.opening_state or intent.action_text[:240]

        # Grounded creator-visible preparation milestones (no chain-of-thought).
        if intent.environment.verified and intent.environment.name:
            events.append(
                _event(
                    "environment_identified",
                    f"Environment identified — {intent.environment.name} {intent.environment.tag}".strip(),
                    tag=intent.environment.tag,
                )
            )
        char_subjects = [s for s in intent.subjects if (s.asset_type or "") == "character" and s.verified]
        prop_subjects = [s for s in intent.subjects if (s.asset_type or "") == "prop" and s.verified]
        if char_subjects:
            events.append(
                _event(
                    "characters_identified",
                    "Character references identified — "
                    + ", ".join(f"{s.name} {s.tag}".strip() for s in char_subjects),
                )
            )
        if prop_subjects:
            events.append(
                _event(
                    "props_identified",
                    "Prop references identified — "
                    + ", ".join(f"{s.name} {s.tag}".strip() for s in prop_subjects),
                )
            )
        events.append(_event("references_verified", "References verified"))
        events.append(
            _event(
                "scene_structure_analyzed",
                f"Scene structure analyzed — {len(intent.scene_beats)} beats"
                + (f" ({intent.scene_type.replace('_', ' ')})" if intent.scene_type else ""),
                beatCount=len(intent.scene_beats),
                sceneType=intent.scene_type,
            )
        )
        if intent.dialogue:
            events.append(
                _event(
                    "dialogue_detected",
                    f"Dialogue detected — {len(intent.dialogue)} line(s)",
                    count=len(intent.dialogue),
                )
            )
        if intent.reveals:
            events.append(
                _event(
                    "reveals_identified",
                    "Reveal constraints identified — "
                    + "; ".join(
                        f"{r.subject} hidden until {r.hidden_until}" if r.hidden_until else f"{r.subject} staged reveal"
                        for r in intent.reveals
                    ),
                )
            )
        if intent.camera_plan.movement or intent.camera_plan.shot_type:
            events.append(
                _event(
                    "camera_plan_identified",
                    "Camera plan identified — "
                    + (intent.camera_plan.movement or intent.camera_plan.shot_type),
                )
            )
        events.append(_event("continuity_locked", "Continuity locked"))
        if spec.scale_relationships or intent.scale_summary:
            events.append(
                _event(
                    "scale_resolved",
                    "Scale relationship identified:\n"
                    + (intent.scale_summary or "extreme size difference"),
                    relationship=spec.scale_relationships[0].model_dump() if spec.scale_relationships else {},
                )
            )
        events.append(_event("action_synthesized", "Cinematic action synthesized"))

        spec.preparation_state = "compiling_prompt"
        events.append(
            _event(
                "prompt_compilation_started",
                f"Compiling {_human_generator(spec.generator_id)} prompt...",
                surface="debug",
                generatorId=spec.generator_id,
            )
        )
        compiled = compile_generator_prompt(spec, resolved)
        spec.compiled_prompt = compiled
        events.append(_event("prompt_compiled", "Timeline prompt synthesized", generatorId=spec.generator_id, prompt=compiled))

        # Long-scene law: multi-batch scenes get one COMPLETE execution prompt
        # per batch, compiled from the capability-driven temporal windows —
        # not the full scene prompt re-sent N times.
        batch_prompts: list[str] = []
        if int(spec.batch_count or 1) > 1:
            from .prompt_compiler import compile_batch_prompts

            batch_prompts = compile_batch_prompts(spec, resolved)
            events.append(
                _event(
                    "batch_prompts_compiled",
                    f"{len(batch_prompts)} batch execution prompts compiled "
                    + " · ".join(
                        f"Batch {i + 1}: {float(w.get('start', 0)):g}–{float(w.get('end', 0)):g}s"
                        for i, w in enumerate(spec.batchWindows or [])
                    ),
                    surface="debug",
                    batchCount=len(batch_prompts),
                )
            )

        spec.preparation_state = "building_timeline"
        events.append(_event("timeline_building", "Building Timeline shot...", surface="debug"))
        scene_id_out, shot_id, scene_index, shot_label = create_or_update_shot_from_spec(
            db, spec, resolved, compiled, batch_prompts=batch_prompts
        )
        spec.scene_id = scene_id_out
        spec.shot_id = shot_id
        spec.preparation_state = "ready"
        events.append(_event("timeline_shot_created", "Shot created.", surface="debug", sceneId=scene_id_out, shotId=shot_id))
        events.append(_event("timeline_ready", "Timeline ready.", surface="debug", sceneId=scene_id_out, shotId=shot_id))
        events.append(_event("ready", "Scene prepared.", surface="debug", sceneId=scene_id_out, shotId=shot_id))

        save_active_production(
            db,
            project_id,
            {
                "projectId": project_id,
                "sceneId": scene_id_out,
                "shotId": shot_id,
                "generatorId": spec.generator_id,
                "productionRequestId": spec.production_request_id,
                "compiledPrompt": compiled,
                "spec": spec.model_dump(),
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            },
        )
        return PreparedSceneResult(
            ok=True,
            spec=spec,
            events=events,
            compiled_prompt=compiled,
            scene_id=scene_id_out,
            shot_id=shot_id,
            scene_index=scene_index,
            shot_label=shot_label,
        )
    except ProductionError as exc:
        try:
            db.rollback()
        except Exception:
            pass
        events.append(_event("failed", exc.message, code=exc.code, details=exc.details))
        return PreparedSceneResult(
            ok=False,
            spec=SceneProductionSpec(project_id=project_id, source_user_prompt=message, preparation_state="failed"),
            events=events,
            error=exc.message,
            error_code=exc.code,
        )
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        events.append(_event("failed", str(exc) or "Scene preparation failed."))
        return PreparedSceneResult(
            ok=False,
            spec=SceneProductionSpec(project_id=project_id, source_user_prompt=message, preparation_state="failed"),
            events=events,
            error=str(exc) or "Scene preparation failed.",
            error_code="PRODUCTION_ERROR",
        )


def generate_prepared_scene(
    db: Session,
    *,
    project_id: str,
    scene_id: str,
    shot_id: str,
) -> dict[str, Any]:
    from ...film_timeline.orchestrator import FilmTimelineError, generate_shot

    if not scene_id or not shot_id:
        raise GenerationSubmissionError("Timeline shot is not prepared yet.")
    try:
        result = generate_shot(db, project_id, scene_id, shot_id)
    except FilmTimelineError as exc:
        raise GenerationSubmissionError(exc.message) from exc
    if not result.get("ok"):
        raise GenerationSubmissionError(
            str(result.get("message") or result.get("error") or "Timeline generation failed."),
            details=result,
        )
    return result
