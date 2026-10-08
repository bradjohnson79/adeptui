"""Capability handler: image.generate

Handles the `image.generate` capability for the Co-Director execution dispatcher.
Resolves character references, attachments, and style, then submits a real
image generation job through the existing Image Generator pipeline.

Spec §44 — Mieke acceptance case:
1. classify EXECUTION
2. capability image.generate
3. resolve Mieke Character Profile
4. resolve Approved Casting Image/reference
5. resolve style if available
6. create generation request
7. submit real job
8. right pane shows active image-generation surface
9. live progress visible
10. generated image appears
11. asset saved to Library
12. Co-Director can immediately discuss/regenerate it
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from dataclasses import replace

from ....character_identity.service import resolve_character_by_name, resolve_approved_reference
from ....production_control.image_generator_query import (
    AutoImageSelection,
    hosted_execution_binding,
    infer_image_task,
    list_compatible_image_generators,
    match_explicit_image_generator,
    required_supports_for_task,
    select_auto_image_generator,
)
from ...conversation.foundation.image_generation_defaults import (
    DEFAULT_ASPECT,
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    resolve_image_generation_profile,
)
from ...image_route import (
    observe_hosted_provider_state,
    parse_route_lock,
    plan_image_route,
)
from ...image_route.contracts import RouteLock
from ...preferences.resolver import resolve_generator_preference

logger = logging.getLogger(__name__)


def _unique_ids(values: list[str] | None) -> list[str]:
    out: list[str] = []
    for raw in values or []:
        value = str(raw or "").strip()
        if value and value not in out:
            out.append(value)
    return out


def collect_character_references(
    db: Session,
    project_id: str,
    *,
    character_id: str = "",
    character_ids: list[str] | None = None,
    character_name: str = "",
    character_names: list[str] | None = None,
    attachment_asset_ids: list[str] | None = None,
    reference_asset_ids: list[str] | None = None,
    prompt: str = "",
) -> tuple[list[str], list[str], str]:
    """Resolve every named character and keep all approved/attached references.

    Returns (character_ids, reference_asset_ids, primary_character_name).
    User attachments stay first; approved character sheets are appended, not replaced.
    """

    resolved_ids = _unique_ids([*(character_ids or []), character_id])
    names = _unique_ids([*(character_names or []), character_name])
    if prompt:
        try:
            from ...entity_resolver import find_character_names

            names = _unique_ids([*names, *find_character_names(prompt)])
        except Exception:
            pass
    primary_name = names[0] if names else character_name
    for name in names:
        profile = resolve_character_by_name(db, project_id, name)
        if profile and profile.id not in resolved_ids:
            resolved_ids.append(profile.id)
        if profile and not primary_name:
            primary_name = profile.name
    refs = _unique_ids([*(attachment_asset_ids or []), *(reference_asset_ids or [])])
    for cid in resolved_ids:
        approved = resolve_approved_reference(db, cid, "hero_identity")
        if approved and approved not in refs:
            refs.append(approved)
    return resolved_ids, refs, primary_name


def _check_runtime_admission(model_family: str, body: dict[str, Any]) -> dict[str, Any] | None:
    """Runtime admission -- verify model family residency before enqueueing.

    Returns None when admission passes, or a failed child_jobs dict
    when the runtime cannot satisfy the requested model family.
    """
    family = (model_family or "").strip().lower()

    # Qwen Image Edit requires explicit residency via request_qwen.
    if family in {"qwen2512", "qwen", "qwen-image-2512", "qwen_image_2512", "qwen_edit_2509", "qwen-image-edit-2509"}:
        try:
            from runtime_supervisor.qwen_residency import request_qwen

            status = request_qwen()
            state = str(status.get("state") or "").lower()
            if state == "offline":
                return {
                    "error": "The local image runtime is offline. Please start Services and try again.",
                    "child_jobs": [],
                }
            if state == "port_conflict":
                return {
                    "error": "Another image program is using the local picture engine. Close it and retry.",
                    "child_jobs": [],
                }
            if state in {"busy", "starting"}:
                return {
                    "error": f"Qwen Image Edit is {state} -- try again shortly.",
                    "child_jobs": [],
                }
            if state == "degraded":
                return {
                    "error": str(status.get("message") or "GPU is not available for Qwen."),
                    "child_jobs": [],
                }
            if state != "ready":
                return {
                    "error": f"Qwen Image Edit is not ready (state={state}). Try again after it loads.",
                    "child_jobs": [],
                }
        except ImportError:
            # Runtime supervisor not available (hosted/cloud mode) -- skip admission.
            pass
        except Exception as exc:
            return {
                "error": f"Could not verify Qwen readiness: {exc}",
                "child_jobs": [],
            }

    # Flux runs on the main Comfy instance -- no dedicated residency call.
    if family in {"flux", "flux1", "flux.1"}:
        try:
            from runtime_supervisor.health import comfy_healthy

            if not comfy_healthy():
                return {
                    "error": "Flux Local isn't currently available. Would you like me to use fal.ai instead?",
                    "child_jobs": [],
                }
        except ImportError:
            pass
        except Exception:
            pass

    return None


def _compile_image_prompt(source: str, generator_id: str = "") -> str:
    """Recompute compiled text from original instructions. Never reuse a prior payload."""

    text = (source or "").strip()
    if not text:
        return ""
    gen = (generator_id or "").strip()
    if not gen:
        return text
    try:
        from ...generator_knowledge.compiler import compile_for_generator
        from ...model_intelligence.schemas import NormalizedGenerationIntent

        result = compile_for_generator(
            gen,
            NormalizedGenerationIntent(userPrompt=text, mediaType="image", mode="text_to_image"),
        )
        compiled = str(getattr(result, "compiledPrompt", "") or "").strip()
        if getattr(result, "status", "") == "ok" and compiled:
            return compiled
    except Exception:
        logger.debug("image prompt compile fell back to original instructions", exc_info=True)
    return text


def _apply_strategy_a_to_cd_body(body: dict[str, Any]) -> dict[str, Any] | None:
    """Reuse CIS Strategy A adapter selection. Return error dict if fail-closed."""
    try:
        from ....image_product.cis_ref_binding import apply_cis_reference_binding

        apply_cis_reference_binding(body)
    except RuntimeError as exc:
        return {"error": str(exc), "child_jobs": []}
    except Exception:
        logger.debug("Strategy A adapter selection failed", exc_info=True)
        typed = (
            body.get("authorityReferences")
            or body.get("authorityRefs")
            or body.get("referenceAssetIds")
            or []
        )
        forced = str(body.get("forceWorkflowKey") or "").strip()
        if typed and (not forced or forced.endswith(".txt2img")):
            return {
                "error": (
                    "Refusing silent txt2img while reference images are selected. "
                    "Image Generator must bind pixels (qwen2512.ref / Qwen Edit 2509 "
                    "multi-ref / zimage.ref_edit) or fail closed."
                ),
                "child_jobs": [],
            }
        return None

    forced = str(body.get("forceWorkflowKey") or "").strip()
    ctx = body.get("creativeContext")
    if forced and isinstance(ctx, dict):
        ctx["workflowKey"] = forced
    # CD 1-ref convention: qwen2512.ref / flux.img2img still carry sourceAssetId
    # so compile/resolve keep generate-with-reference (not silent T2I).
    if forced in {"qwen2512.ref", "flux.img2img"} and not str(
        body.get("sourceAssetId") or body.get("source_asset_id") or ""
    ).strip():
        body["sourceAssetId"] = str(
            body.get("referenceImage") or body.get("reference_image") or ""
        ).strip()
    return None


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    prompt: str = "",
    character_name: str = "",
    character_id: str = "",
    character_ids: list[str] | None = None,
    character_names: list[str] | None = None,
    scene_id: str = "",
    visual_style: str = "",
    attachment_asset_ids: list[str] | None = None,
    reference_asset_ids: list[str] | None = None,
    aspect_ratio: str = "",
    width: int = 0,
    height: int = 0,
    provider_kind: str = "",
    generation_route: str = "",
    count: int = 1,
    user_instructions: str = "",
    original_user_instructions: str = "",
    resolved_creative_brief: str = "",
    explicit_provider: str = "",
    lock_level: str = "",
    lock_scope: str = "",
    requested_provider: str = "",
    requested_model_id: str = "",
    image_generator_planning: dict | None = None,
    authority_refs: list[dict] | None = None,
    selected_characters: list[dict] | None = None,
    selected_props: list[dict] | None = None,
    selected_environment: dict | None = None,
    _attempted: set[str] | None = None,
    _retry_depth: int = 0,
) -> dict[str, Any]:
    """Submit a real image generation job.

    Returns a dict with job_ids, child_jobs (for the ExecutionPlan), and
    surface_type. The dispatcher wraps this into an ExecutionPlan.
    """
    from ....storyboard_jobs import enqueue_imagegen_job

    resolved_ids, resolved_refs, resolved_character_name = collect_character_references(
        db,
        project_id,
        character_id=character_id,
        character_ids=character_ids,
        character_name=character_name,
        character_names=character_names,
        attachment_asset_ids=attachment_asset_ids,
        reference_asset_ids=reference_asset_ids,
        prompt=prompt or original_user_instructions or resolved_creative_brief,
    )

    # WAVE 2/3: compile @/%/#/~ tokens + approved-ERS hard default for production stills.
    # Typed CIS authority pack (character/environment/prop) — adapter-agnostic;
    # preserves asset IDs into compile authority (not text-only identity rewrite).
    typed_authority: dict | None = None
    apply_typed_authority_to_body = None  # bound before try (except also clears)
    try:
        from ....image_product.prompt_tokens import (
            apply_typed_authority_to_body,
            compile_typed_image_authority,
            merge_token_reference_ids,
            resolve_image_prompt_tokens,
        )

        token_pack = resolve_image_prompt_tokens(
            db,
            project_id,
            prompt or original_user_instructions or resolved_creative_brief,
            hard_default_approved_ers=True,
        )
        resolved_refs = merge_token_reference_ids(resolved_refs, token_pack)

        planning = image_generator_planning
        if not isinstance(planning, dict):
            planning = None
        if planning is None and (
            authority_refs or selected_characters or selected_props or selected_environment
        ):
            planning = {
                "authorityRefs": list(authority_refs or []),
                "selectedCharacters": list(selected_characters or []),
                "selectedProps": list(selected_props or []),
                "selectedEnvironment": selected_environment,
            }
        typed_authority = compile_typed_image_authority(
            token_pack=token_pack,
            planning=planning,
            authority_refs=authority_refs,
            reference_asset_ids=resolved_refs,
            character_asset_ids=[
                str(r.get("assetId") or "")
                for r in (selected_characters or [])
                if isinstance(r, dict)
            ]
            or None,
            environment_asset_id=str(
                (selected_environment or {}).get("assetId") or ""
            )
            if isinstance(selected_environment, dict)
            else "",
            prop_asset_ids=[
                str(r.get("assetId") or "")
                for r in (selected_props or [])
                if isinstance(r, dict)
            ]
            or None,
        )
        # Prefer typed pack ids so character+env both survive into the request.
        if typed_authority and typed_authority.get("referenceAssetIds"):
            resolved_refs = merge_token_reference_ids(
                resolved_refs, {"reference_asset_ids": typed_authority["referenceAssetIds"]}
            )
    except Exception:
        token_pack = None
        typed_authority = None
        apply_typed_authority_to_body = None  # type: ignore[assignment]

    resolved_character_id: str | None = resolved_ids[0] if resolved_ids else (character_id or None)
    reference_asset_id: str | None = resolved_refs[0] if resolved_refs else None

    original = (original_user_instructions or "").strip()
    brief = (resolved_creative_brief or "").strip()
    compile_source = brief or original or (prompt or "").strip()
    profile_message = user_instructions if original else (user_instructions or prompt)
    profile = resolve_image_generation_profile(profile_message)
    if aspect_ratio:
        profile = replace(profile, aspect_ratio=aspect_ratio, source="current")
    if width and height:
        profile = replace(profile, width=int(width), height=int(height), source="current")
    if provider_kind:
        hosted = provider_kind in {"fal", "hosted", "api", "kie", "wavespeed"}
        profile = replace(
            profile,
            provider_kind=provider_kind if hosted else "local",
            local_first=not hosted,
            route=generation_route or profile.route,
        )
    elif generation_route:
        profile = replace(profile, route=generation_route)

    resolution = resolve_generator_preference(
        db,
        project_id,
        modality="image",
        message=profile_message or compile_source,
    )
    if resolution.explicit and resolution.error:
        return {
            "error": resolution.error,
            "child_jobs": [],
            "provider": resolution.provider,
            "creatorAck": "",
        }

    task = infer_image_task(prompt=compile_source, reference_asset_id=reference_asset_id)
    explicit_name = (explicit_provider or profile.explicit_provider or requested_model_id or "").strip()
    if explicit_name and task == "reference":
        named = match_explicit_image_generator(explicit_name)
        required = required_supports_for_task("reference")
        supports = set(getattr(named, "supports", ()) or ()) if named is not None else set()
        if named is not None and not any(tag in supports for tag in required):
            # Named generator stays. Inherited stills remain as compiled
            # facts instead of silently switching the family.
            task = "text_to_image"
    if resolution.explicit and resolution.ok and not profile.is_hosted and not explicit_name:
        explicit_name = resolution.provider
        profile = replace(profile, explicit_provider=explicit_name, route="explicit")

    utterance = (user_instructions or "").strip() or compile_source
    excluded_entities: list[Any] = []
    try:
        from ...project_grounding import (
            forbidden_model_tokens,
            parse_route_lock_excluding_entities,
            resolve_turn_entities,
            snapshot_entity_tokens,
        )

        entity_resolution = resolve_turn_entities(db, project_id, utterance)
        excluded_entities = list(entity_resolution.characters)
        try:
            from ...project_grounding import build_project_grounding_snapshot

            snap = build_project_grounding_snapshot(db, project_id)
            excluded_entities.extend(snapshot_entity_tokens(snap))
        except Exception:
            pass
        parsed_lock = parse_route_lock_excluding_entities(utterance, excluded_entities)
        banned = forbidden_model_tokens(excluded_entities)
        if explicit_name and re.sub(r"[^a-z0-9]+", "", explicit_name.lower()) in banned:
            explicit_name = ""
    except Exception:
        parsed_lock = parse_route_lock(utterance)
    inherited = (lock_level or "").strip().upper()
    inherited_scope = (lock_scope or "").strip()
    if not parsed_lock.restated and inherited in {"UNLOCKED", "PREFERRED", "STRICT"}:
        scope = inherited_scope or (
            "model"
            if (requested_model_id or explicit_name)
            else ("provider" if requested_provider else parsed_lock.scope)
        )
        route_lock = RouteLock(
            level=inherited,  # type: ignore[arg-type]
            scope=scope,  # type: ignore[arg-type]
            requested_provider=requested_provider or parsed_lock.requested_provider,
            requested_model_id=requested_model_id or parsed_lock.requested_model_id or explicit_name,
            restated=False,
        )
    else:
        route_lock = parsed_lock
        if requested_provider and not route_lock.requested_provider:
            route_lock = RouteLock(
                level=route_lock.level,
                scope=route_lock.scope or "provider",
                requested_provider=requested_provider,
                requested_model_id=route_lock.requested_model_id,
                restated=route_lock.restated,
            )
        if (requested_model_id or explicit_name) and not route_lock.requested_model_id:
            route_lock = RouteLock(
                level=route_lock.level,
                scope=route_lock.scope or "model",
                requested_provider=route_lock.requested_provider,
                requested_model_id=requested_model_id or explicit_name,
                restated=route_lock.restated,
            )
    if (
        route_lock.level == "UNLOCKED"
        and not parsed_lock.requested_model_id
        and not parsed_lock.requested_provider
    ):
        explicit_name = ""
        route_lock = RouteLock(
            level="UNLOCKED",
            scope="",
            requested_provider="",
            requested_model_id="",
            restated=parsed_lock.restated,
        )
    if (
        route_lock.level != "UNLOCKED"
        and profile.provider_kind in {"fal", "hosted", "api"}
        and not route_lock.requested_provider
        and not route_lock.requested_model_id
    ):
        route_lock = RouteLock(
            level=route_lock.level,
            scope="provider",
            requested_provider="fal",
            requested_model_id="",
            restated=True,
        )

    try:
        from runtime_supervisor.health import comfy_healthy

        local_ready = bool(comfy_healthy())
    except Exception:
        local_ready = True

    attempted: set[str] = set(_attempted or ())
    if _retry_depth > 6:
        return {
            "error": "Image generation could not start after multiple route retries.",
            "child_jobs": [],
            "creatorAck": "",
        }
    route_plan = plan_image_route(
        task=task,
        lock=route_lock,
        explicit_name=explicit_name,
        requested_provider=route_lock.requested_provider,
        requested_model_id=route_lock.requested_model_id,
        project_id=project_id,
        attempted=attempted,
        local_runtime_ready=local_ready,
        match_explicit=match_explicit_image_generator,
        list_compatible=list_compatible_image_generators,
        select_auto=select_auto_image_generator,
        observe_provider=observe_hosted_provider_state,
    )
    if route_plan.blocked or route_plan.selected is None:
        return {
            "error": route_plan.error or "No compatible image generator is available right now.",
            "child_jobs": [],
            "creatorAck": "",
            "lockLevel": route_lock.level,
            "lockScope": route_lock.scope,
            "requestedProvider": route_lock.requested_provider,
            "requestedModelId": route_lock.requested_model_id or explicit_name,
            "fallbackAudit": route_plan.audit.as_dict(),
        }

    chosen = route_plan.selected
    hosted = not chosen.is_local
    explicit_family = ""
    model_family = ""
    workflow_key = ""
    hosted_model_id = ""
    fal_image_model_id = ""
    selection_source = profile.source if route_plan.step == "exact" else route_plan.step
    if hosted:
        binding = hosted_execution_binding(chosen)
        model_family = binding["family"]
        workflow_key = binding["workflowKey"]
        hosted_model_id = binding["hostedModelId"]
        fal_image_model_id = binding["falImageModelId"]
        selected_kind = (chosen.provider or "").strip().lower() or "fal"
        if selected_kind not in {"fal", "kie", "wavespeed", "hosted", "api"}:
            selected_kind = "fal"
        profile = replace(
            profile,
            provider_kind=selected_kind,
            local_first=False,
            route="explicit" if route_lock.level != "UNLOCKED" else profile.route,
            explicit_provider=explicit_name or chosen.model_id,
        )
    else:
        explicit_family = chosen.family
        model_family = chosen.family
        if task == "reference" and model_family == "qwen2512":
            workflow_key = "qwen2512.ref"
        elif task == "reference" and model_family == "flux":
            workflow_key = "flux.img2img"
        else:
            workflow_key = f"{model_family}.txt2img"
        if explicit_name:
            profile = replace(profile, explicit_provider=chosen.family or explicit_name, route="explicit")
    auto_selection = AutoImageSelection(
        selected=chosen,
        task=task,
        route=route_plan.step or profile.route,
        source=selection_source,
        why=route_plan.audit.why or route_plan.disclose,
        hosted_candidates=[],
        hosted_evaluated=hosted or route_plan.step in {"other_hosted", "same_provider"},
    )

    compiled_prompt = _compile_image_prompt(
        compile_source,
        hosted_model_id or model_family or explicit_name,
    )

    # Build the generation request.
    low_prompt = (compile_source or "").lower()
    wants_sheet = any(
        token in low_prompt
        for token in (
            "character sheet",
            "four-view",
            "four view",
            "turnaround sheet",
            "four-panel",
            "four panel",
        )
    )
    out_w = int(width or profile.width or DEFAULT_WIDTH)
    out_h = int(height or profile.height or DEFAULT_HEIGHT)
    out_aspect = "1:1" if wants_sheet else (aspect_ratio or profile.aspect_ratio or DEFAULT_ASPECT)
    if wants_sheet:
        out_w, out_h = 1024, 1024
    body: dict[str, Any] = {
        "prompt": compiled_prompt,
        "negative_prompt": "",
        "width": out_w,
        "height": out_h,
        "tag": f"codirector_image_generate_{execution_id[:8]}",
        "modelFamilyPreference": model_family,
        "purpose": "character_sheet" if wants_sheet else "codirector_image_generate",
        "aspectRatio": out_aspect,
        "batchCount": max(1, min(count, 8)),
        "source": selected_kind if hosted else "local",
        "providerKind": selected_kind if hosted else "local",
        "providerPreference": "hosted" if hosted else "local",
        "creativeContext": {
            "objective": "character_sheet" if wants_sheet else "image_generate",
            "executionId": execution_id,
            "characterId": resolved_character_id or "",
            "characterIds": resolved_ids,
            "characterName": resolved_character_name or "",
            "reference_image_ids": list(resolved_refs),
            "workflowKey": workflow_key,
            "source": selected_kind if hosted else "local",
            "providerKind": selected_kind if hosted else "local",
            "autoResolution": auto_selection.as_observability() if auto_selection else {
                "route": profile.route,
                "source": selection_source,
                "selectedFamily": model_family,
                "locality": "hosted" if hosted else "local",
            },
        },
        "lockModelFamily": bool(model_family) and not hosted,
    }
    if hosted:
        body["hostedModelId"] = hosted_model_id
        if fal_image_model_id:
            body["falImageModelId"] = fal_image_model_id
    if wants_sheet:
        from ....character_identity.four_view_sheet import (
            attach_four_view_sheet_intent,
            strengthen_four_view_prompt,
        )

        attach_four_view_sheet_intent(body)
        body["prompt"] = strengthen_four_view_prompt(compiled_prompt)
        body["width"] = 1024
        body["height"] = 1024

    if resolved_refs:
        body["referenceAssetIds"] = list(resolved_refs)
        body["referenceImage"] = resolved_refs[0]
        body["reference_image"] = resolved_refs[0]

    # Stamp typed CIS authority fields first (kinds survive into Strategy A).
    if typed_authority and apply_typed_authority_to_body is not None:
        try:
            apply_typed_authority_to_body(body, typed_authority)
        except Exception:
            logger.debug("typed authority stamp failed", exc_info=True)

    # Structured generationIntent: merge Bible/CD creative compile into body.
    # Lock precedence: user-locked visualStyle / lighting / colorGrade / camera WIN;
    # Bible/CD fill gaps only. Must run BEFORE Strategy A so creative locks are set
    # before the last binder selects workflow/refs.
    try:
        from ...production_intent.generation_intent import compile_and_apply_generation_intent

        compile_and_apply_generation_intent(
            body,
            project_id=project_id,
            scene_id=scene_id or "",
            db=db,
            planning=image_generator_planning if isinstance(image_generator_planning, dict) else None,
            visual_style=visual_style or "",
            include_bible=True,
        )
    except Exception:
        logger.debug(
            "generationIntent lock-merge failed; falling back to visual_style stamp",
            exc_info=True,
        )
        if visual_style:
            body.setdefault("creativeContext", {})
            if isinstance(body.get("creativeContext"), dict):
                # Gap-fill only when unlocked / absent.
                body["creativeContext"].setdefault("visualStyle", visual_style)
                body.setdefault("visualStyle", visual_style)

    # Strategy A LAST binder: same CIS contract (1 typed ref -> .ref; char+env / 2+ -> edit;
    # locked family that cannot bind pixels -> fail closed). Never silent txt2img.
    # Do not reorder ahead of locked creative stamps above.
    if not hosted and not wants_sheet:
        strategy_blocked = _apply_strategy_a_to_cd_body(body)
        if strategy_blocked is not None:
            return strategy_blocked

    # ---- Runtime admission ----
    if not hosted:
        admission_blocked = _check_runtime_admission(model_family, body)
        if admission_blocked is not None:
            attempted.add(chosen.model_id)
            retry_plan = plan_image_route(
                task=task,
                lock=route_lock,
                explicit_name=explicit_name,
                requested_provider=route_lock.requested_provider,
                requested_model_id=route_lock.requested_model_id,
                project_id=project_id,
                attempted=attempted,
                local_runtime_ready=local_ready,
                match_explicit=match_explicit_image_generator,
                list_compatible=list_compatible_image_generators,
                select_auto=select_auto_image_generator,
                observe_provider=observe_hosted_provider_state,
            )
            if retry_plan.blocked or retry_plan.selected is None:
                admission_blocked.setdefault("creatorAck", "")
                admission_blocked["fallbackAudit"] = retry_plan.audit.as_dict()
                return admission_blocked
            if retry_plan.selected.model_id != chosen.model_id and retry_plan.selected.model_id not in attempted:
                return handle(
                    db,
                    project_id,
                    execution_id,
                    prompt=prompt,
                    character_name=character_name,
                    character_id=character_id,
                    character_ids=resolved_ids,
                    character_names=character_names,
                    scene_id=scene_id,
                    visual_style=visual_style,
                    attachment_asset_ids=attachment_asset_ids,
                    reference_asset_ids=resolved_refs,
                    aspect_ratio=aspect_ratio,
                    width=width,
                    height=height,
                    provider_kind="fal" if not retry_plan.selected.is_local else "local",
                    generation_route=generation_route,
                    count=count,
                    user_instructions=user_instructions,
                    original_user_instructions=original_user_instructions or compile_source,
                    explicit_provider=retry_plan.selected.model_id,
                    lock_level=route_lock.level,
                    requested_provider=route_lock.requested_provider,
                    requested_model_id=route_lock.requested_model_id,
                    _attempted=attempted,
                    _retry_depth=_retry_depth + 1,
                )
            admission_blocked.setdefault("creatorAck", "")
            return admission_blocked

    # Installed LoRAs only. A name in the request can be applied. Unknown names are not invented.
    lora_note = ""
    if not hosted and model_family and "lora" in (compile_source or "").lower():
        try:
            from ....lora_registry.registry import compatible_loras, match_prompt_lora

            available = compatible_loras(model_family, "image")
            names = [rec.name for rec in available if rec.name]
            if isinstance(body.get("creativeContext"), dict):
                body["creativeContext"]["availableLoras"] = names
            matched = match_prompt_lora(compile_source or "", model_family)
            if matched is not None:
                selection = {
                    "id": matched.id,
                    "loraId": matched.id,
                    "name": matched.name,
                    "strength": matched.recommended_strength if matched.recommended_strength is not None else 0.8,
                }
                body["lora"] = selection
                body["loras"] = [selection]
                lora_note = f" Using the installed LoRA {matched.name}."
            elif names:
                lora_note = " Installed LoRAs for this model: " + ", ".join(names) + ". None of those names were in the request, so none were applied."
            else:
                lora_note = " No LoRAs are installed for this image model."
        except Exception:
            logger.debug("installed LoRA lookup failed", exc_info=True)

    # Submit the real job.
    job = enqueue_imagegen_job(db, project_id, body, scene_id=scene_id or None)

    child_jobs = []
    for i in range(max(1, min(count, 8))):
        child_jobs.append({
            "job_id": job.id if i == 0 else f"{job.id}_batch{i}",
            "label": f"Image {i + 1}" if count > 1 else "Generated Image",
            "status": "queued",
            "child_index": i,
            "metadata": {
                "character_id": resolved_character_id or "",
                "character_ids": resolved_ids,
                "character_name": resolved_character_name or "",
                "reference_asset_id": reference_asset_id or "",
                "reference_asset_ids": resolved_refs,
                "route": profile.route,
                "providerKind": selected_kind if hosted else "local",
                "aspectRatio": out_aspect,
                "selectedModelId": auto_selection.selected_model_id if auto_selection else "",
                "selectedFamily": model_family,
                "autoWhy": auto_selection.why if auto_selection else "",
            },
        })

    return {
        "job_ids": [cj["job_id"] for cj in child_jobs],
        "child_jobs": child_jobs,
        "surface_type": "image_generation",
        "character_id": resolved_character_id,
        "character_ids": resolved_ids,
        "reference_asset_id": reference_asset_id,
        "reference_asset_ids": resolved_refs,
        "creatorAck": (route_plan.disclose or profile.acknowledgement() or "") + lora_note,
        "aspectRatio": out_aspect,
        "width": out_w,
        "height": out_h,
        "route": (
            route_plan.step
            if route_lock.level == "UNLOCKED"
            else (profile.route or route_plan.step)
        ),
        "providerKind": selected_kind if hosted else "local",
        "originalUserInstructions": compile_source,
        "compiledGeneratorPrompt": str(body.get("prompt") or compiled_prompt),
        "prompt": str(body.get("prompt") or compiled_prompt),
        "lockLevel": route_lock.level,
        "lockScope": route_lock.scope,
        "requestedProvider": route_lock.requested_provider,
        "requestedModelId": route_lock.requested_model_id or explicit_name,
        "fallbackAudit": route_plan.audit.as_dict(),
        "selectedModelId": chosen.model_id,
    }
