"""Build TimelineGenerationRequest from a BatchBlock + execution snapshot."""

from __future__ import annotations

import re

import logging
from typing import Any

from ...aspect_fps import normalize_production_aspect, production_pixels
from ...video_runtime.legal_canvas import (
    SpecFidelityError,
    infer_tier_from_pixels,
    is_minimax_h3_generator,
    resolve_h3_timeline_canvas,
    resolve_legal_canvas,
    snap_h3_timeline_duration,
)
from ...video_runtime.workflow_resolver import is_ltx_25_generator
from ..contracts import BatchBlock, ExecutionSnapshot
from .contracts import GenerationMode, TimelineGenerationRequest, VideoGeneratorCapabilities
from .registry import get_registry

logger = logging.getLogger("adept.director_timeline_w46.request_builder")








def _frames_full_scene(prompt: str, scene_total: float, segments: list[Any] | None = None) -> bool:
    """True when the prompt still frames the batch as the WHOLE scene.

    Detects the full-scene Duration framing ("Seconds: 0-30. This segment is a
    30 second scene.") and a stacked Timed Prompt whose length covers the
    scene. Either one makes H3 compress the entire story into one window.
    Extension prompts ("continues the scene") are not full-scene.
    """
    import re

    if "continues the scene" in (prompt or "").lower():
        return False
    if "CONTINUATION window" in (prompt or ""):
        return False
    for seg in segments or []:
        try:
            start = float(getattr(seg, "start", 0.0) or 0.0)
            length = float(getattr(seg, "length", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if scene_total > 0 and start <= 0.05 and length >= max(0.0, scene_total - 0.5):
            return True
    pattern = re.compile(
        r"Seconds:\s*0\s*-\s*(\d+(?:\.\d+)?)", re.IGNORECASE
    )
    m = pattern.search(prompt or "")
    if not m:
        return False
    try:
        end = float(m.group(1))
    except ValueError:
        return False
    return end >= scene_total > 0


def _authoritative_timed_segments(segments: list[Any]) -> list[Any]:
    """One Timed Prompt per start. A later save replaces a stacked copy.

    Legacy reconcile used to append a second segment beside the one the
    creator just edited. Joining every copy sends MiniMax conflicting drafts.
    """
    chosen: list[Any] = []
    starts: list[float] = []
    for seg in segments or []:
        text = str(getattr(seg, "text", "") or "").strip()
        if not text:
            continue
        try:
            start = round(float(getattr(seg, "start", 0.0) or 0.0), 2)
        except (TypeError, ValueError):
            start = 0.0
        replaced = False
        for index, prev in enumerate(starts):
            if abs(prev - start) < 0.05:
                chosen[index] = seg
                replaced = True
                break
        if not replaced:
            starts.append(start)
            chosen.append(seg)
    return chosen


def _spoken_dialogue_line(language: str | None) -> str:
    """H3 has no language widget. The spoken language has to be in the prompt."""
    code = str(language or "").strip().lower().split("-")[0]
    names = {
        "en": "English",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "ja": "Japanese",
        "zh": "Chinese",
        "ko": "Korean",
        "pt": "Portuguese",
    }
    name = names.get(code)
    if not name:
        return ""
    return f"Spoken dialogue language: {name}. Speak every scripted line in {name}."


def _scope_root_batch_prompt(
    scene_prompt: str,
    *,
    window_start: float,
    window_end: float,
    total_batches: int,
) -> str:
    """Scope the scene-level Timed Prompt for a ROOT batch (0-15s of an N-batch scene).

    12B reference lesson: the known-good 2-batch scene gives each batch its own
    window-scoped prompt. When a single scene-level Timed Prompt covers the full
    scene, delivering it verbatim to Batch 1 with duration=15 makes H3 compress
    the ENTIRE story arc into 15 seconds -- the first half of the
    "15-second scene twice" symptom.

    This keeps the creator's prose intact and only adds an explicit WINDOW
    scoping note: which part of the scene this batch renders and that the
    remaining story belongs to later batches.
    """
    if not scene_prompt or not scene_prompt.strip():
        return scene_prompt
    import re

    text = scene_prompt
    duration_pattern = re.compile(
        r"(Duration:\s*\n?\s*Seconds:\s*)0\s*-\s*\d+(?:\.\d+)?\.?\s*"
        r"This segment is a \d+(?:\.\d+)? second scene\.?",
        re.IGNORECASE,
    )
    replacement = (
        f"{window_start:.0f}-{window_end:.0f}. "
        f"This segment renders only the scene window from {window_start:.0f}s to {window_end:.0f}s."
    )
    if duration_pattern.search(text):
        text = duration_pattern.sub(lambda m: m.group(1) + replacement, text, count=1)
    else:
        seconds_pattern = re.compile(
            r"(Seconds:\s*)0\s*-\s*\d+(?:\.\d+)?\.?",
            re.IGNORECASE,
        )
        if seconds_pattern.search(text):
            text = seconds_pattern.sub(
                lambda m: m.group(1) + f"{window_start:.0f}-{window_end:.0f}.", text, count=1
            )
    # Explicit window discipline for the root batch.
    scoping = (
        "\n\nWINDOW SCOPE\n"
        f"This batch renders ONLY the segment from {window_start:.0f}s to {window_end:.0f}s "
        f"of the scene. Do not compress, summarize, or complete the whole scene in this "
        f"segment. The story continues after {window_end:.0f}s in the next batch -- end this "
        "segment mid-motion at a natural continuation point that the next batch can "
        "advance from. Preserve identity, wardrobe, environment, and lighting."
    )
    if "WINDOW SCOPE" not in text:
        text = text.rstrip() + scoping
    if total_batches > 1:
        text += (
            f"\n(This scene continues across {total_batches} sequential batches; "
            f"this is batch 1.)"
        )
    return text


def _batch_windows_for_prompt(project_id: str, scene_id: str) -> list[tuple[float, float]]:
    """Cumulative planned-duration windows per batch in order, for prompt framing."""
    try:
        from ..reconcile import batch_time_windows
        from ...db import SessionLocal
        from .. import store

        db = SessionLocal()
        try:
            payload = store.load_master(db, project_id, scene_id)
            if not payload.get("ok"):
                return []
            master = payload.get("master")
            if master is None:
                return []
            from ..contracts import SceneTimelineMaster

            m = SceneTimelineMaster.model_validate(master) if not isinstance(master, SceneTimelineMaster) else master
            return [(start, end) for _b, start, end in batch_time_windows(m)]
        finally:
            db.close()
    except Exception:
        return []


def _root_scene_prompt(project_id: str, scene_id: str) -> str:
    """Root Timed Prompt text, used to fill a later window that has none."""
    try:
        from ...db import SessionLocal
        from .. import store
        from ..contracts import SceneTimelineMaster

        db = SessionLocal()
        try:
            payload = store.load_master(db, project_id, scene_id)
            if not payload.get("ok"):
                return ""
            master = payload.get("master")
            if master is None:
                return ""
            scene = (
                master
                if isinstance(master, SceneTimelineMaster)
                else SceneTimelineMaster.model_validate(master)
            )
            blocks = sorted(
                list(scene.batchBlocks or []),
                key=lambda batch: int(getattr(batch, "order", 0) or 0),
            )
            if not blocks:
                return ""
            segments = list(getattr(blocks[0], "promptSegments", None) or [])
            if not segments:
                return ""
            return str(getattr(segments[0], "text", "") or "")
        finally:
            db.close()
    except Exception:
        return ""




def _resolve_project_visual_style(project_id: str) -> str:
    """Best-effort read of the project-level visual style (never raises).

    Single project authority: ``settings_json.visualStyle`` (API field
    ``visual_style``). Character ``visual_style`` and storyboard styles are
    not substitutes. Timed Prompt may still lift a ``Visual style:`` line
    when the project field is empty.
    """
    try:
        from ...db import Project, SessionLocal
        from .semantic_contract import resolve_style_key

        db = SessionLocal()
        try:
            project = db.get(Project, project_id)
            if not project:
                return ""
            settings_raw = getattr(project, "settings_json", None) or "{}"
            settings: dict = {}
            if isinstance(settings_raw, str):
                import json

                try:
                    parsed = json.loads(settings_raw)
                except Exception:
                    parsed = {}
                if isinstance(parsed, dict):
                    settings = parsed
            for key in ("visualStyle", "visual_style", "style", "globalStyle"):
                value = settings.get(key)
                if value:
                    return resolve_style_key(str(value)) or str(value).strip()
            # Soft compat: free-text defaults_json.prompt_style if it maps to a
            # known STYLE_REGISTRY key -- not a second registry.
            defaults_raw = getattr(project, "defaults_json", None) or "{}"
            if isinstance(defaults_raw, str):
                import json

                try:
                    defaults = json.loads(defaults_raw)
                except Exception:
                    defaults = {}
                if isinstance(defaults, dict):
                    for key in ("visual_style", "visualStyle", "prompt_style"):
                        value = defaults.get(key)
                        if value:
                            resolved = resolve_style_key(str(value))
                            if resolved:
                                return resolved
        finally:
            db.close()
    except Exception:
        return ""
    return ""

def _style_prompt_phrase(style_key: str) -> str:
    """Map a visual style key to a rendering phrase. Style is not identity."""
    from .semantic_contract import style_rendering_phrase

    return style_rendering_phrase(style_key)


def _requested_duration(batch: BatchBlock, range_rep: dict[str, Any]) -> float:
    marked = float(range_rep.get("length") or 0.0) if range_rep else 0.0
    if marked > 0:
        return marked
    return float(batch.duration.plannedDuration or 5.0)


def _h3_duration_for_request(generator_id: str, requested: float) -> tuple[float, dict[str, Any]]:
    """Inspector/batch request ? legal H3 duration. Disclose snap. Fail if >15s."""
    if not is_minimax_h3_generator(generator_id):
        return requested, {}
    snap = snap_h3_timeline_duration(requested)
    if not snap.get("ok"):
        raise ValueError(str(snap.get("message") or "MiniMax H3 duration is above 15s."))
    extras = {
        "requestedDurationSec": snap.get("requestedDurationSec"),
        "legalDurationSec": snap.get("legalDurationSec"),
        "durationSnapDisclosed": bool(snap.get("snapped")),
        "durationSnapMessage": snap.get("message") or "",
        "legalFrameCount": snap.get("frames"),
    }
    # Job/legal length is frames/fps; creator durationSec stays on request separately.
    legal = snap.get("legalDurationSec")
    if legal is None:
        legal = snap.get("durationSec")
    return float(legal), extras


def _range_replacement(snapshot: ExecutionSnapshot) -> dict[str, Any]:
    raw = (snapshot.continuityState or {}).get("rangeReplacement")
    return raw if isinstance(raw, dict) else {}


def _video_reference_from_batch(batch: BatchBlock) -> tuple[str | None, dict[str, Any] | None]:
    """Copy the attached video reference onto the request. Never drop it here."""
    asset_id: str | None = None
    trim: dict[str, Any] | None = None
    for anchor in batch.sourceAnchors or []:
        if anchor.kind == "video" and (anchor.assetId or "").strip():
            asset_id = str(anchor.assetId)
            break
    for ref in batch.references or []:
        if not isinstance(ref, dict):
            continue
        kind = str(ref.get("kind") or ref.get("role") or "").lower()
        rid = str(ref.get("assetId") or "").strip()
        if rid and ("video" in kind or kind == "motion"):
            if ref.get("consumed") is False:
                continue
            asset_id = asset_id or rid
            if isinstance(ref.get("trim"), dict):
                trim = ref.get("trim")
    return asset_id, trim


def _tier_for_caps(caps: VideoGeneratorCapabilities, *, draft_mode: bool) -> str:
    """Map capability resolution labels / pixels onto a legal-canvas tier."""
    label = ""
    if draft_mode and caps.draftResolution:
        label = str(caps.draftResolution)
    elif caps.finalResolution:
        label = str(caps.finalResolution)
    token = label.strip().lower()
    if token in {"480p", "720p", "1080p", "2k", "4k"}:
        return "2K" if token == "2k" else token
    if "x" in token:
        try:
            w_s, h_s = token.split("x", 1)
            return infer_tier_from_pixels(int(w_s), int(h_s))
        except (TypeError, ValueError):
            pass
    return "480p" if draft_mode else "720p"


def _aspect_supported(caps: VideoGeneratorCapabilities, aspect: str) -> bool:
    listed = [str(a) for a in (caps.supportedAspectRatios or [])]
    if not listed:
        return True
    if aspect in listed:
        return True
    return any(aspect in a for a in listed)


def _resolution_for_request(
    caps: VideoGeneratorCapabilities,
    aspect: str,
    batch: BatchBlock,
    *,
    draft_mode: bool,
) -> str | None:
    """Compile generator-native resolution for the scene aspect.

    Never treat landscape finalResolution WxH as aspect-blind authority.
    Per-family legal_canvas (or honest refuse) -- Law 25 / Law 64.
    """
    # MiniMax H3: 16:9 stays megapixel-grid authority. Non-16:9 uses legal_canvas
    # vertical dims and passes WxH through the Comfy adapter.
    if is_minimax_h3_generator(batch.generatorId):
        if aspect == "16:9":
            canvas = resolve_h3_timeline_canvas(batch.h3Resolution, draft_mode=draft_mode)
            return f"{canvas['width']}x{canvas['height']}"
        tier = "480p" if draft_mode else "720p"
        h3_res = batch.h3Resolution if isinstance(batch.h3Resolution, dict) else {}
        try:
            mp = float(h3_res.get("megapixels")) if h3_res.get("megapixels") is not None else None
        except (TypeError, ValueError):
            mp = None
        if not draft_mode and mp is not None and mp >= 1.5:
            tier = "1080p"
        try:
            legal = resolve_legal_canvas(
                batch.generatorId or caps.id, tier=tier, aspect=aspect
            )
        except SpecFidelityError as exc:
            raise ValueError(
                f"{caps.label} cannot compile aspect {aspect}: {exc}"
            ) from exc
        return f"{legal.width}x{legal.height}"

    # Hosted cheap-preview uses provider-native labels (480p/720p), never forced pixels.
    # Seedance keeps aspect_ratio on the request; labels stay honest.
    if caps.draftPathway == "cheap_preview" and (caps.draftResolution or caps.finalResolution):
        chosen = caps.draftResolution if draft_mode else caps.finalResolution
        return chosen or caps.finalResolution

    # LTX / align-32 families: aspect-aware legal canvas (704x1248 for 9:16 @720p).
    # LTX 2.5 Fast is fewer steps at production size -- never a smaller picture.
    # Timeline LTX QUALITY (batch.ltxQuality) is the creator tier authority when set.
    # Absent => 720p (adapter finalResolution). 4K fails honestly (native UNAVAILABLE).
    # 480p is never a Timeline QUALITY choice (may still exist on CREATE adapter caps).
    try:
        if is_ltx_25_generator(caps.id) or is_ltx_25_generator(batch.generatorId):
            raw_tier = getattr(batch, "ltxQuality", None)
            if raw_tier:
                token = str(raw_tier).strip()
                aliases = {"720p": "720p", "1080p": "1080p", "2k": "2K", "4k": "4K"}
                tier = aliases.get(token.lower(), token if token in {"720p", "1080p", "2K", "4K"} else None)
                if tier is None:
                    raise ValueError(
                        f"LTX Timeline QUALITY {raw_tier!r} is not supported. "
                        "Use 720p, 1080p, 2K, or 4K (4K is UNAVAILABLE natively)."
                    )
                if tier == "480p":
                    raise ValueError(
                        "480p is not a Timeline LTX QUALITY option. Choose 720p, 1080p, or 2K."
                    )
            else:
                tier = "720p"
            try:
                legal = resolve_legal_canvas(caps.id, tier=tier, aspect=aspect)
            except SpecFidelityError as exc:
                raise ValueError(
                    f"{caps.label} cannot compile LTX QUALITY {tier} for aspect {aspect}: {exc}"
                ) from exc
            return f"{legal.width}x{legal.height}"

        tier_draft = draft_mode
        legal = resolve_legal_canvas(
            caps.id, tier=_tier_for_caps(caps, draft_mode=tier_draft), aspect=aspect
        )
        return f"{legal.width}x{legal.height}"
    except SpecFidelityError:
        pass

    # Landscape WxH capability label is only honest for 16:9.
    if caps.finalResolution and "x" in str(caps.finalResolution):
        if aspect == "16:9":
            return caps.finalResolution
        if _aspect_supported(caps, aspect):
            raise ValueError(
                f"{caps.label} lists {aspect} but Adept has no legal vertical canvas "
                f"compiler for this generator. Refusing dishonest landscape "
                f"{caps.finalResolution} labeled as {aspect}."
            )
        raise ValueError(
            f"{caps.label} does not support aspect {aspect}. "
            f"Supported: {', '.join(str(a) for a in (caps.supportedAspectRatios or [])) or 'none listed'}."
        )

    quality = "draft" if draft_mode and caps.draftPathway != "none" else "final"
    width, height = production_pixels(aspect, quality)
    return f"{width}x{height}"


def build_timeline_generation_request(
    *,
    project_id: str,
    scene_id: str,
    batch: BatchBlock,
    snapshot: ExecutionSnapshot,
    fallback_allowed: bool = False,
    incoming_bridge: object | None = None,
    aspect_ratio: str | None = None,
    draft_mode: bool | None = None,
    temporal_packet: object | None = None,
    turbo_lora: bool = False,
    direct_references: object | None = None,
) -> TimelineGenerationRequest:
    registry = get_registry()
    generator_id = batch.generatorId
    if not generator_id:
        raise ValueError("BATCH_GENERATOR_REQUIRED")
    # Resolve aliases to canonical adapter ids for the shared contract.
    canonical = registry.resolve_id(generator_id)
    caps = registry.capabilities(canonical)

    # Creator Spec Fidelity: Timed Prompt segment text is authoritative action
    # language for delivery. productionPrompt is Co-Director enrichment only.
    # MiniMax H3 Direct Line: never let productionPrompt / Scene Prompt become a
    # second silent authority for Comfy Input Text -- use Timed Prompt text only.
    from ...video_runtime.legal_canvas import is_minimax_h3_generator as _is_h3_gen
    _h3_delivery = _is_h3_gen(str(batch.generatorId or ""))
    # LTX 2.5 uses the same scene-length window rule. Its clip is 20s, not 15s.
    _window_split = _h3_delivery or is_ltx_25_generator(str(batch.generatorId or ""))
    # Whether a ready Qwen packet was woven into this request's prompt (set in
    # the extension-adaptation branch below; initialized for all other paths).
    _qwen_weave_packet = None
    # Batch time windows for root-batch scoping (resolved once, reused below).
    windows_for_scope: list[tuple[float, float]] = []
    try:
        windows_for_scope = _batch_windows_for_prompt(project_id, scene_id)
    except Exception:
        windows_for_scope = []
    source_segments = _authoritative_timed_segments(batch.promptSegments or []) if _h3_delivery else list(batch.promptSegments or [])
    prompt_parts = []
    for p in source_segments:
        timed = (p.text or "").strip()
        if _h3_delivery:
            if timed:
                prompt_parts.append(timed)
            # else: leave empty -- do not fill from productionPrompt on H3
            continue
        part = timed or str(p.productionPrompt or "").strip()
        if part:
            prompt_parts.append(part)
    prompt = "\n".join(prompt_parts)
    if _window_split and windows_for_scope:
        # Dual-stack removal left later windows empty, or with only a
        # [CONTINUATION] stub and no story. That stub is not a prompt.
        # Reconnect the root Timed Prompt as this window's slice.
        try:
            order_empty = int(getattr(batch, "order", 0) or 0)
        except (TypeError, ValueError):
            order_empty = 0
        if 0 < order_empty < len(windows_for_scope):
            from .window_script import story_blocks as _story_blocks

            if not prompt.strip() or not _story_blocks(prompt):
                from ..execution_window_materialize import _continuation_text
                from .window_script import is_structured_scene_prompt, slice_story_for_window

                ws_empty, we_empty = windows_for_scope[order_empty]
                root_script = _root_scene_prompt(project_id, scene_id)
                sliced = ""
                if root_script and not is_structured_scene_prompt(root_script):
                    sliced = slice_story_for_window(
                        root_script, order_empty, len(windows_for_scope)
                    )
                continuation = _continuation_text(order_empty, ws_empty, we_empty)
                scope = (
                    "\n\nWINDOW SCOPE\n"
                    f"This batch renders ONLY the segment from {ws_empty:g}s to {we_empty:g}s of the scene. "
                    "Do not restart the scene from 0s. Do not retell the opening. "
                    "Continue identity, wardrobe, environment, and lighting."
                )
                prompt = continuation + (("\n\n" + sliced) if sliced else "") + scope
    if not prompt.strip():
        # WAVE2 dual-authority purge: refuse empty batch prompts. Do NOT inherit
        # scene-level Timed Prompt / legacy director_json / scene.prompt.
        # Co-Director + timeline_builder must supply per-batch window segments.
        raise ValueError(
            "BATCH_PROMPT_REQUIRED: batch has no promptSegments text; "
            "scene-level prompt inheritance is removed (WAVE2)."
        )
    # Root-batch window scoping: if an H3 root batch's own segment still frames
    # the full scene (Seconds: 0-N) while the batch window is a strict sub-window,
    # append WINDOW SCOPE. WAVE2: empty batches refuse above -- no scene-level inherit.
    if _window_split and windows_for_scope:
        try:
            order_now = int(getattr(batch, "order", 0) or 0)
        except (TypeError, ValueError):
            order_now = 0
        # A11: every window that still carries identical full-scene framing must be
        # rewritten to its own [ws, we] -- not only the root batch.
        if len(windows_for_scope) > 1 and 0 <= order_now < len(windows_for_scope):
            ws, we = windows_for_scope[order_now]
            scene_total = windows_for_scope[-1][1]
            full_scene = _frames_full_scene(prompt, scene_total, source_segments)
            if order_now > 0 and full_scene:
                from ..execution_window_materialize import _continuation_text
                from .window_script import is_structured_scene_prompt, slice_story_for_window

                if is_structured_scene_prompt(prompt):
                    # Structured compiler recipes must not replay Seconds: 0-N.
                    prompt = (
                        _continuation_text(order_now, ws, we)
                        + "\n\nWINDOW SCOPE\n"
                        f"This batch renders ONLY the segment from {ws:g}s to {we:g}s of the scene. "
                        "Do not restart the scene from 0s. Do not retell the opening. "
                        "Continue identity, wardrobe, environment, and lighting."
                    )
                else:
                    sliced = slice_story_for_window(
                        prompt, order_now, len(windows_for_scope)
                    )
                    prompt = (
                        _continuation_text(order_now, ws, we)
                        + ("\n\n" + sliced if sliced else "")
                        + "\n\nWINDOW SCOPE\n"
                        f"This batch renders ONLY the segment from {ws:g}s to {we:g}s of the scene. "
                        "Do not restart the scene from 0s. Do not retell the opening. "
                        "Continue identity, wardrobe, environment, and lighting."
                    )
            elif full_scene and (we < scene_total or ws > 0):
                from .window_script import is_structured_scene_prompt, slice_story_for_window

                if is_structured_scene_prompt(prompt):
                    if "WINDOW SCOPE" not in prompt:
                        prompt = _scope_root_batch_prompt(
                            prompt,
                            window_start=ws,
                            window_end=we,
                            total_batches=len(windows_for_scope),
                        )
                else:
                    # A 45s Timed Prompt on a 15s window must not carry the
                    # rest of the scene, including the ending, into batch 1.
                    sliced = slice_story_for_window(
                        prompt, order_now, len(windows_for_scope)
                    )
                    if order_now == 0:
                        prompt = _scope_root_batch_prompt(
                            sliced or prompt,
                            window_start=ws,
                            window_end=we,
                            total_batches=len(windows_for_scope),
                        )
                    else:
                        from ..execution_window_materialize import _continuation_text

                        prompt = (
                            _continuation_text(order_now, ws, we)
                            + ("\n\n" + sliced if sliced else "")
                            + "\n\nWINDOW SCOPE\n"
                            f"This batch renders ONLY the segment from {ws:g}s to {we:g}s of the scene. "
                            "Do not restart the scene from 0s. Do not retell the opening. "
                            "Continue identity, wardrobe, environment, and lighting."
                        )
            # A one-sentence Timed Prompt cannot be split into story beats, so
            # later windows keep that sentence. They still must be told their
            # own interval. Without this fence MiniMax treats every window as
            # the whole scene.
            if order_now > 0 and "WINDOW SCOPE" not in prompt:
                from ..execution_window_materialize import _continuation_text

                header = ""
                if "CONTINUATION window" not in prompt:
                    header = _continuation_text(order_now, ws, we) + "\n\n"
                prompt = (
                    header
                    + prompt.rstrip()
                    + "\n\nWINDOW SCOPE\n"
                    f"This batch renders ONLY the segment from {ws:g}s to {we:g}s of the scene. "
                    "Do not restart the scene from 0s. Do not retell the opening. "
                    "Continue identity, wardrobe, environment, and lighting."
                )
    negative = next((p.negativePrompt for p in (batch.promptSegments or []) if p.negativePrompt), None)
    range_rep = _range_replacement(snapshot)
    range_prompt = str(range_rep.get("prompt") or "").strip()
    # STYLE AUTHORITY is a separate semantic layer. Do not prepend it into the
    # action blob -- that mixes WHO with HOW and lets style language recast people.
    project_style = _resolve_project_visual_style(project_id)
    if not project_style:
        from .semantic_contract import lift_style_from_text

        project_style, _ = lift_style_from_text(prompt)
    style_phrase = _style_prompt_phrase(project_style)
    retake_package: dict[str, Any] | None = None
    if range_prompt:
        # LAW: Re-Take is DELTA -- do NOT wipe master Timed Prompt.
        # compiled = ESTABLISHED SCENE + TARGET BEAT + USER DELTA + HARD CONSTRAINTS.
        from .retake_context_package import build_retake_context_package

        user_corr = {}
        cont = snapshot.continuityState or {}
        if isinstance(cont.get("userCorrection"), dict):
            user_corr = dict(cont["userCorrection"])
        retake_package = build_retake_context_package(
            batch=batch,
            snapshot=snapshot,
            range_rep=range_rep,
            user_correction=user_corr,
            project_style=project_style,
            style_phrase=style_phrase,
            supports_image_to_video=bool(getattr(caps, "supportsImageToVideo", False)),
            supports_reference_to_video=bool(getattr(caps, "supportsReferenceToVideo", False)),
            project_id=project_id,
        )
        prompt = str(retake_package.get("compiledPrompt") or range_prompt)
        authored_prompt = str(retake_package.get("authoredPrompt") or "\n".join(prompt_parts))
    else:
        # Creator Spec Fidelity: authoredPrompt is the creator Timed Prompt only.
        # Temporal / pose / Spatial Map movement prefixes must not overwrite it --
        # identity bind and R2V body use authoredPrompt as cast/action authority.
        authored_prompt = prompt
    temporal_compile: dict[str, Any] = {}
    temporal_packet_id = None
    pose_compile: dict[str, Any] = {}
    # Wave 2A H3 call-fence: temporal / pose / movement prefixes must never land on
    # H3 Comfy Input Text. Skip the silent prepend writers entirely for H3 (not only
    # rely on delivery_prompt=authored_prompt). Non-H3 keeps existing behavior.
    if temporal_packet is not None and not range_prompt and not _h3_delivery:
        from ...codirector.video_intelligence.compile import compile_temporal_continuation

        rejected = bool(getattr(getattr(temporal_packet, "continuation", None), "creatorRejected", False))
        temporal_compile = compile_temporal_continuation(
            temporal_packet,
            supports_prompt_continuation=bool(getattr(caps, "supportsPromptContinuation", True)),
            creator_rejected=rejected,
        )
        temporal_packet_id = getattr(temporal_packet, "packetId", None)
        prefix = str(temporal_compile.get("promptPrefix") or "").strip()
        # REBUILD LAW (single weave): temporal continuation weave is applied once.
        # appends the compiled block to a scene-level prompt for extension
        # batches. The membership check prevents the same observed-state block
        # from being prepended a second time (non-H3 mirror of the H3
        # H3_CONTINUATION_WEAVE dedupe).
        if temporal_compile.get("applied") and prefix and prefix not in prompt:
            prompt = "\n".join(part for part in (prefix, prompt) if part)
    elif temporal_packet is not None and _h3_delivery:
        temporal_packet_id = getattr(temporal_packet, "packetId", None)
        # Direct Line law: no machine PREFIX before the creator text. The Qwen
        # observed end-state reaches H3 prompts as an additive CONTINUATION
        # weave appended after the creator's text -- for ANY extension batch
        # with a ready packet, whether its prompt came from its own segment or
        # the inherited scene-level Timed Prompt (recursive Batch N ? N+1
        # continuity contract). Scene-level prompts are already woven inside
        # scene-level inheritance path (removed WAVE2/5); membership check prevents a
        # duplicate block.
        rejected = bool(
            getattr(getattr(temporal_packet, "continuation", None), "creatorRejected", False)
        )
        _h3_order_ok = int(getattr(batch, "order", 0) or 0) > 0
        if (
            str(getattr(temporal_packet, "availability", "") or "") == "ready"
            and not rejected
            and _h3_order_ok
            and not range_prompt
        ):
            from ...codirector.video_intelligence.compile import compile_temporal_continuation

            _compiled = compile_temporal_continuation(
                temporal_packet,
                supports_prompt_continuation=True,
                creator_rejected=False,
            )
            _qwen_block = str(_compiled.get("promptPrefix") or "").strip()
            if _qwen_block and _qwen_block not in prompt:
                prompt = prompt.rstrip() + "\n\n" + _qwen_block
            semantic = ""
            if incoming_bridge is not None:
                state = getattr(incoming_bridge, "continuityState", None) or {}
                if isinstance(state, dict):
                    semantic = str(state.get("semanticContinuity") or "").strip()
            if semantic and semantic not in prompt:
                prompt = prompt.rstrip() + "\n\n" + semantic
            temporal_compile = {
                "applied": True,
                "reason": "H3_CONTINUATION_WEAVE",
                "promptPrefix": "",
            }
        else:
            # Direct Line law: no machine prefix on H3 Comfy Input Text. With
            # no ready packet (or creator rejection / range replacement) the
            # review reaches the prompt through no weave; report honestly.
            temporal_compile = {
                "applied": False,
                "reason": "H3_DIRECT_LINE_FENCE",
                "promptPrefix": "",
            }
    # PoseCraft attach is deferred until continuityStrategy is known (after
    # last-frame / sourceAnchor resolution). Track temporal/bridge rejection here.
    _pose_rejected = bool(
        temporal_packet is not None
        and (
            bool(getattr(getattr(temporal_packet, "continuation", None), "creatorRejected", False))
            or str(temporal_compile.get("reason") or "") == "CREATOR_REJECTED"
        )
    )
    _bridge_continue_without = bool(
        incoming_bridge is not None
        and str(getattr(incoming_bridge, "error", "") or "") == "CREATOR_CONTINUE_WITHOUT"
    )
    pose_compile = {}
    movement_layers = (
        _compile_movement_layers(project_id, batch)
        if (not range_prompt and not _h3_delivery)
        else {}
    )
    if movement_layers.get("providerText") and not _h3_delivery:
        # Keep structured layers distinct from free-text Timed Prompt.
        prompt = "\n".join(
            part for part in (movement_layers["providerText"], prompt) if part and not _is_alias_only(part)
        )

    start_image = None
    end_image = None
    planning_start = None
    for anchor in batch.sourceAnchors or []:
        if anchor.kind == "image" and anchor.assetId:
            if planning_start is None:
                planning_start = anchor.assetId
            if anchor.kind == "image" and not start_image:
                # Prefer role-like labels
                label = (anchor.label or "").lower()
                if "end" in label:
                    end_image = anchor.assetId
                else:
                    start_image = start_image or anchor.assetId
        if anchor.kind == "end_frame" and anchor.assetId:
            end_image = anchor.assetId
    cut_in = str(
        range_rep.get("startImageAssetId")
        or range_rep.get("referenceImageAssetId")
        or ""
    ).strip()
    if cut_in:
        start_image = cut_in

    # Also accept references dict entries (IMAGE only).
    # Voice/audio/sfx never belong in visual referenceAssetIds -- those ride
    # characterVoice / audio slots. Video is a dedicated field below.
    _NON_IMAGE_REF_KINDS = {
        "charactervoice",
        "voice",
        "audio",
        "sfx",
        "lipsync_audio",
        "motion",
    }
    # Explicit Timeline start_image role (I2V / LTXVImgToVideo cond). Must win
    # over generic entity refs so single-cond engines still receive a start frame
    # after Co-Director clears extra entity tensors.
    if not start_image:
        for ref in batch.references or []:
            if not isinstance(ref, dict) or not ref.get("assetId"):
                continue
            if ref.get("consumed") is False:
                continue
            role = str(ref.get("role") or "").lower()
            kind = str(ref.get("kind") or "").lower()
            if role in {"start_image", "start", "i2v_start", "opening"} or (
                kind in {"image", "start_image"} and "start" in role
            ):
                start_image = str(ref["assetId"]).strip() or start_image
                if start_image:
                    break

    ref_ids: list[str] = []
    for ref in batch.references or []:
        if not isinstance(ref, dict) or not ref.get("assetId"):
            continue
        if ref.get("consumed") is False:
            continue
        kind = str(ref.get("kind") or "").lower()
        if "video" in kind or kind in _NON_IMAGE_REF_KINDS:
            continue
        ref_ids.append(str(ref["assetId"]))

    # Single-cond I2V engines (LTX 2.5 maximumReferenceImages=0) still need one
    # start frame for LTXVImgToVideo. Promote first image reference when
    # supportsImageToVideo and no start was resolved.
    if not start_image and caps.supportsImageToVideo:
        max_imgs = int(getattr(caps, "maximumReferenceImages", 0) or 0)
        multi = bool(getattr(caps, "supportsMultipleImageReferences", False))
        if max_imgs <= 0 or not multi:
            for rid in ref_ids:
                token = str(rid or "").strip()
                if token:
                    start_image = token
                    break
        # Multi-image R2V/I2V with no T2V (Seedance Mini): batch.references
        # alone must activate image mode. Leaving generationMode=text_to_video
        # when supportsTextToVideo=False causes CAPABILITY_VALIDATION_FAILED.
        elif ref_ids and not caps.supportsTextToVideo:
            token = str(ref_ids[0] or "").strip()
            if token:
                start_image = token

    video_ref_id, video_trim = _video_reference_from_batch(batch)
    video_ids = []
    for ref in batch.references or []:
        if not isinstance(ref, dict) or not ref.get("assetId"):
            continue
        kind = str(ref.get("kind") or "").lower()
        if "video" in kind:
            vid = str(ref["assetId"]).strip()
            if vid and vid not in video_ids:
                video_ids.append(vid)

    mode: GenerationMode = "text_to_video"
    gen_start = None
    gen_end = None
    supports_r2v = bool(getattr(caps, "supportsReferenceToVideo", False))
    if supports_r2v:
        # First-class Timeline R2V BEFORE I2V/T2V fallthrough (MiniMax H3).
        # supportsImageToVideo=False is not "text-to-video only". Image-frame /
        # cut-in / CRS refs ride generationMode=reference + FM4/FM5 DR->ref_image_N.
        # No T2V fallback, no Seedance substitution.
        mode = "reference"
        if start_image:
            gen_start = start_image
        elif ref_ids:
            gen_start = str(ref_ids[0]).strip() or None
        gen_end = None
    elif caps.supportsImageToVideo and start_image:
        # Multi-image force-R2V (Seedance Mini): references are R2V slots, not a
        # classic single-start I2V. Prefer generationMode=reference so CD does
        # not need a sourceAnchor start hack to pass capability validation.
        multi = bool(getattr(caps, "supportsMultipleImageReferences", False))
        if multi and not caps.supportsTextToVideo and (ref_ids or video_ref_id or video_ids):
            mode = "reference"
            gen_start = start_image
            gen_end = None
        else:
            mode = "image_to_video"
            gen_start = start_image
            if caps.supportsEndFrame and end_image:
                mode = "start_end_frame"
                gen_end = end_image
    elif caps.supportsImageToVideo and (ref_ids or video_ref_id or video_ids):
        # Image/video refs present but no dedicated start role -- R2V/I2V, never
        # unsupported T2V for force-R2V products (Seedance Mini).
        multi = bool(getattr(caps, "supportsMultipleImageReferences", False))
        if multi and not caps.supportsTextToVideo:
            mode = "reference"
        else:
            mode = "image_to_video"
        if ref_ids:
            gen_start = str(ref_ids[0]).strip() or None
        gen_end = None
    elif caps.supportsTextToVideo:
        mode = "text_to_video"
        # Do not pass unsupported start frames as generation inputs (no silent drop of claimed I2V).
        gen_start = None
        gen_end = None
    elif start_image or ref_ids or video_ref_id or video_ids:
        # Visual refs present but neither I2V nor R2V -- honest refuse.
        # Leave generationMode=reference so validate reports R2V missing.
        # Do NOT fall back to T2V or swap engines (Seedance).
        mode = "reference"
        if start_image:
            gen_start = start_image
        elif ref_ids:
            gen_start = str(ref_ids[0]).strip() or None
        gen_end = None
    else:
        # Generator rejects T2V and no image/video refs resolved -- keep mode for
        # validate_against_capabilities to report a clear capability error.
        mode = "text_to_video"

    last_frame = None
    tail_asset = None
    bridge_id = None
    if incoming_bridge is not None:
        last_frame = getattr(incoming_bridge, "lastFrameAssetId", None)
        tail_asset = getattr(incoming_bridge, "tailAssetId", None)
        bridge_id = getattr(incoming_bridge, "bridgeId", None)
    if range_rep and float(range_rep.get("start") or 0.0) > 0.05:
        last_frame = None

    strategy = "none"
    if last_frame and caps.supportsImageToVideo:
        mode = "image_to_video"
        gen_start = last_frame
        strategy = "last_frame_i2v"
        if caps.supportsEndFrame and end_image:
            mode = "start_end_frame"
            gen_end = end_image
    elif last_frame:
        strategy = "prompt_context"

    # Multi-angle: batch sourceAnchors still win composition when they exist as
    # dedicated start images AND the generator supports I2V -- last-frame is then
    # continuity metadata, not a framing override.
    if start_image and caps.supportsImageToVideo and last_frame:
        gen_start = start_image
        strategy = "prompt_context"
        mode = "image_to_video" if mode == "text_to_video" else mode

    # PoseCraft intended-state attach (continuityStrategy + temporal rejection gates).
    if _h3_delivery:
        pose_compile = {"applied": False, "reason": "H3_DIRECT_LINE_FENCE", "promptPrefix": ""}
    elif range_prompt:
        pose_compile = {"applied": False, "reason": "RANGE_REPLACEMENT", "promptPrefix": ""}
    elif _pose_rejected or _bridge_continue_without:
        pose_compile = {
            "applied": False,
            "reason": "POSE_SKIPPED_CONTINUITY_REJECTED",
            "promptPrefix": "",
        }
    else:
        pose_compile = _compile_pose_conditioning(
            project_id,
            batch,
            caps,
            continuity_strategy=strategy,
            temporal_rejected=_pose_rejected,
        )
        pose_prefix = str(pose_compile.get("promptPrefix") or "").strip()
        if pose_compile.get("applied") and pose_prefix:
            prompt = "\n".join(part for part in (pose_prefix, prompt) if part)

    if caps.executionType == "local":
        # Mapped start/end stay for single-cond engines. Product mode is R2V.
        mode = "reference"

    # Never silently drop image references. Adapter validation refuses
    # unsupported / over-limit counts. Bindings stay on the Prompt clip.
    aspect = normalize_production_aspect(aspect_ratio)
    use_draft = bool(draft_mode) if draft_mode is not None else caps.draftPathway != "none"
    if caps.draftPathway == "none":
        use_draft = False
    speed_quality = is_ltx_25_generator(generator_id)
    # Official LTX 2.5 Fast is fewer steps at production size, not a smaller picture.
    resolution = _resolution_for_request(
        caps, aspect, batch, draft_mode=False if speed_quality else use_draft
    )
    # H3 canvas provenance for job history. Non-H3 batches leave this None.
    h3_resolved_canvas = (
        resolve_h3_timeline_canvas(batch.h3Resolution, draft_mode=use_draft)
        if is_minimax_h3_generator(batch.generatorId)
        else None
    )
    ltx_resolved_quality = None
    if is_ltx_25_generator(generator_id) or is_ltx_25_generator(batch.generatorId):
        tier = str(getattr(batch, "ltxQuality", None) or "720p").strip()
        aliases = {"720p": "720p", "1080p": "1080p", "2k": "2K", "4k": "4K"}
        tier = aliases.get(tier.lower(), tier)
        ltx_resolved_quality = {"tier": tier, "resolution": resolution}
    aspect_warning = ""
    listed_aspects = list(caps.supportedAspectRatios or [])
    if listed_aspects and aspect not in listed_aspects and not any(aspect in str(a) for a in listed_aspects):
        # Law 64: never soft-warn-and-still-gen on unsupported scene aspect.
        raise ValueError(
            f"{caps.label} does not support aspect {aspect}. "
            f"Supported: {', '.join(str(a) for a in listed_aspects)}. "
            f"Adept will not crop a different ratio and call it {aspect}."
        )

    requested_duration = _requested_duration(batch, range_rep)
    # Keep request.duration as the RAW creator-requested duration (12.0s).
    # The legal MiniMax generation frame count (294) is stored in providerOptions
    # as legalFrameCount. The generation path uses legalFrameCount for MiniMax,
    # then trims the excess back to requested_duration. This preserves duration
    # honesty: the Scene stays 12.0s, the final clip is 12.0s, and MiniMax
    # internally generates 294 legal frames (12.25s) that are trimmed to 12.0s.
    job_duration, duration_extras = _h3_duration_for_request(generator_id, requested_duration)
    # request.duration stays as the creator's requested duration (not snapped).
    # For MiniMax H3, job_duration is the legal duration (12.25s) but we keep
    # request.duration = requested_duration (12.0s) so the Scene is not mutated
    # and the trim target is the creator's request.
    if is_minimax_h3_generator(generator_id):
        request_duration_value = requested_duration
    else:
        request_duration_value = job_duration
    knowledge = _compile_generator_knowledge(
        generator_id=canonical,
        prompt=prompt,
        negative=negative,
        mode=mode,
        start_image=gen_start,
        reference_ids=ref_ids,
        batch=batch,
        duration=job_duration,
    )
    # Phase A Direct Line (H3): knowledge compiledPrompt must not overwrite
    # Timed Prompt. Non-H3 generators keep the existing compile overwrite.
    if (
        knowledge.get("compiledPrompt")
        and not range_prompt
        and not is_minimax_h3_generator(generator_id)
    ):
        prompt = str(knowledge["compiledPrompt"])
    if knowledge.get("compiledNegative") and caps.supportsNegativePrompt:
        negative = str(knowledge["compiledNegative"])

    # H3 Comfy Input Text = creator Timed Prompt (authoredPrompt), not temporal
    # / pose / movement prefixes or knowledge rewrites -- EXCEPT:
    #   - range retake, where delivery is ESTABLISHED + TARGET BEAT + USER DELTA
    #     + HARD CONSTRAINTS (authoredPrompt stays established), and
    #   - the H3 continuation weave, where the Qwen observed end-state is
    #     appended after the creator text (temporal_compile reason
    #     H3_CONTINUATION_WEAVE). The weave is additive observation bound to a
    #     ready packet -- it must ship on H3 Comfy Input Text or the review is
    #     silently dropped (recursive Batch N ? N+1 continuity contract).
    _h3_weave_applied = (
        is_minimax_h3_generator(generator_id)
        and str(temporal_compile.get("reason") or "") == "H3_CONTINUATION_WEAVE"
    )
    if retake_package is not None:
        delivery_prompt = prompt
    elif _h3_weave_applied:
        delivery_prompt = prompt
    else:
        delivery_prompt = authored_prompt if is_minimax_h3_generator(generator_id) else prompt

    # Keep @ImageN order: startImage = Image1, referenceAssetIds = Image2..N
    # so Seedance fal image_urls does not upload the first ref twice.
    ref_ids_for_request = list(ref_ids)
    if gen_start and ref_ids_for_request and str(ref_ids_for_request[0]).strip() == str(gen_start).strip():
        ref_ids_for_request = ref_ids_for_request[1:]

    request = TimelineGenerationRequest(
        projectId=project_id,
        sceneId=scene_id,
        batchBlockId=batch.id,
        executionSnapshotId=snapshot.id,
        generatorId=canonical,
        generationMode=mode,
        prompt=delivery_prompt,
        negativePrompt=negative if caps.supportsNegativePrompt else None,
        startImageAssetId=gen_start,
        endImageAssetId=gen_end,
        referenceAssetIds=ref_ids_for_request,
        videoReferenceAssetId=video_ref_id,
        videoReferenceTrim=video_trim,
        duration=request_duration_value,
        resolution=resolution,
        aspectRatio=aspect,
        seed=None,
        cameraMotion=None,
        providerOptions={
            "lora": batch.lora,
            "planningStartImageAssetId": planning_start,
            "originalGeneratorId": generator_id,
            "selectedGenerator": snapshot.selectedGenerator,
            "continuityLastFrameAssetId": last_frame,
            "continuityEffectiveTail": getattr(incoming_bridge, "effectiveTailDuration", None)
            if incoming_bridge
            else None,
            "draftMode": use_draft,
            "draftPathway": caps.draftPathway,
            "finalRequiresNewGeneration": caps.finalRequiresNewGeneration,
            "fast_generation": bool(use_draft and (caps.draftPathway == "local_live" or speed_quality)),
            "h3ResolvedCanvas": h3_resolved_canvas,
            "ltxResolvedQuality": ltx_resolved_quality,
            "aspectWarning": aspect_warning,
            "videoReferenceAssetIds": video_ids,
            "motionSubjectIdentityId": next(
                (
                    str(ref.get("identityId"))
                    for ref in (batch.references or [])
                    if isinstance(ref, dict) and ref.get("role") == "motion_subject" and ref.get("identityId")
                ),
                None,
            ),
            "motionSubjectBindingId": next(
                (
                    str(ref.get("bindingId"))
                    for ref in (batch.references or [])
                    if isinstance(ref, dict) and ref.get("role") == "motion_subject" and ref.get("bindingId")
                ),
                None,
            ),
            "motionReferenceAssetId": next(
                (
                    str(ref.get("assetId"))
                    for ref in (batch.references or [])
                    if isinstance(ref, dict)
                    and ref.get("role") == "motion_reference"
                    and ref.get("consumed")
                    and ref.get("assetId")
                ),
                None,
            ),
            "movementLayers": movement_layers.get("layers"),
            "temporalContinuation": temporal_compile,
            "temporalContinuityPacketId": temporal_packet_id,
            "poseMotionConditioning": pose_compile,
            "generatorKnowledge": knowledge,
            "authoredPrompt": authored_prompt,
            "visualStyle": project_style,
            "stylePhrase": style_phrase,
            "rangeReplacement": range_rep or None,
            "retakeContextPackage": (
                {
                    "establishedScene": (retake_package or {}).get("establishedScene"),
                    "establishedSetup": (retake_package or {}).get("establishedSetup"),
                    "localBeat": (retake_package or {}).get("localBeat"),
                    "targetBeat": (retake_package or {}).get("targetBeat"),
                    "prevBeatContext": (retake_package or {}).get("prevBeatContext"),
                    "nextBeatExcluded": (retake_package or {}).get("nextBeatExcluded"),
                    "userDelta": (retake_package or {}).get("userDelta"),
                    "authoredPrompt": (retake_package or {}).get("authoredPrompt"),
                    "compiledPrompt": (retake_package or {}).get("compiledPrompt"),
                    "actualH3BoundPrompt": (retake_package or {}).get("actualH3BoundPrompt"),
                    "hardConstraints": (retake_package or {}).get("hardConstraints"),
                    "effectiveH3Exclusions": (retake_package or {}).get("effectiveH3Exclusions"),
                    "overlapWarning": (retake_package or {}).get("overlapWarning"),
                    "userCorrection": (retake_package or {}).get("userCorrection"),
                    "currentTake": (retake_package or {}).get("currentTake"),
                    "speakers": (retake_package or {}).get("speakers"),
                    "shots": (retake_package or {}).get("shots"),
                    "inherited": (retake_package or {}).get("inherited"),
                    "boundaryContinuity": (retake_package or {}).get("boundaryContinuity"),
                    "debug": (retake_package or {}).get("debug"),
                }
                if retake_package
                else None
            ),
            **duration_extras,
            "motionReferenceBindingId": next(
                (
                    str(ref.get("bindingId"))
                    for ref in (batch.references or [])
                    if isinstance(ref, dict)
                    and ref.get("role") == "motion_reference"
                    and ref.get("consumed")
                    and ref.get("bindingId")
                ),
                None,
            ),
        },
        fallbackAllowed=fallback_allowed,
        continuityBridgeId=bridge_id,
        lastFrameAssetId=last_frame,
        tailAssetId=tail_asset,
        continuityStrategy=strategy,
        temporalContinuityPacketId=temporal_packet_id,
    )
    from ...production_control.generator_authority import supports_turbo_lora

    if bool(turbo_lora) and supports_turbo_lora(generator_id):
        request.providerOptions["turbo_lora"] = True
    # Audio authority contract: determine who owns the audio for this generation.
    audio_authority = _resolve_audio_authority(project_id, scene_id, batch, caps)
    request.providerOptions["audioAuthority"] = audio_authority
    request.providerOptions["generate_audio"] = audio_authority.get("generateAudio", False)
    # Co-Director Dialogue Authority: structured language + locked script for generators.
    spoken_code = None
    try:
        from app.codirector.dialogue_authority import (
            apply_manifest_to_request,
            compile_dialogue_authority_for_batch,
            get_manifest_from_batch,
        )
        from ...db import SessionLocal as _DlgSessionLocal
        from .. import store as _dlg_store
        from ..contracts import SceneTimelineMaster as _DlgMaster

        manifest = get_manifest_from_batch(batch)
        if manifest is None:
            _dlg_db = _DlgSessionLocal()
            try:
                scene_master = None
                try:
                    loaded = _dlg_store.load_master(_dlg_db, project_id, scene_id)
                    raw_master = loaded.get("master") if loaded.get("ok") else None
                    if raw_master is not None:
                        scene_master = (
                            raw_master
                            if isinstance(raw_master, _DlgMaster)
                            else _DlgMaster.model_validate(raw_master)
                        )
                except Exception:
                    scene_master = None
                manifest = compile_dialogue_authority_for_batch(
                    _dlg_db,
                    project_id=project_id,
                    scene_id=scene_id,
                    batch=batch,
                    master=scene_master,
                )
            finally:
                _dlg_db.close()
        if manifest is not None:
            apply_manifest_to_request(request, manifest)
            if _h3_delivery:
                spoken = (request.providerOptions or {}).get("spokenLanguage") or {}
                if isinstance(spoken, dict):
                    spoken_code = (
                        spoken.get("language")
                        or spoken.get("sceneLanguage")
                        or spoken.get("projectLanguage")
                    )
            # Re-assert silence lock after Dialogue Manifest apply.
            if _batch_silence_locked(batch, request.prompt):
                aa = dict(request.providerOptions.get("audioAuthority") or {})
                aa["authority"] = "silence_locked"
                aa["nativeAudio"] = "disabled"
                aa["generateAudio"] = False
                aa["reason"] = aa.get("reason") or "expectedSpeech_NONE_or_empty_silence_locked_manifest"
                request.providerOptions["audioAuthority"] = aa
                request.providerOptions["generate_audio"] = False
                request.providerOptions["audio_generation"] = False
    except Exception:
        # REBUILD LAW (dialogue authority): never ship silently. The submit
        # path already fails closed on manifest compile errors (stale cached
        # manifests are dropped); here a read/apply failure must at least be
        # observable -- the structured authority block is simply absent and
        # post-gen QC still gates the render.
        logger.warning(
            "dialogue authority manifest read/apply failed project=%s scene=%s batch=%s",
            project_id,
            scene_id,
            getattr(batch, "id", "?"),
            exc_info=True,
        )
    # A hollow later-window stub can silence-lock before the slice is attached.
    # The slice is the script that will be spoken. Restore native audio for it.
    if (
        _h3_delivery
        and not _batch_silence_locked(batch, request.prompt)
        and _text_implies_speech(request.prompt or "")
    ):
        request.providerOptions["generate_audio"] = True
        request.providerOptions["audio_generation"] = True
    # H3 has no language widget. Without this line MiniMax speaks Chinese.
    if (
        _h3_delivery
        and not _batch_silence_locked(batch, request.prompt)
        and bool((request.providerOptions or {}).get("generate_audio"))
        and "Spoken dialogue language:" not in (request.prompt or "")
    ):
        from .window_script import h3_spoken_lock

        lock = h3_spoken_lock(
            str(spoken_code) if spoken_code else None,
            request.prompt or "",
        )
        if lock:
            request.prompt = (request.prompt or "").rstrip() + "\n\n" + lock
    # Always re-assert silence lock (covers empty-manifest / try skip paths).
    # The delivered prompt counts: a slice with spoken lines is not silence.
    if _batch_silence_locked(batch, request.prompt):
        aa = dict(request.providerOptions.get("audioAuthority") or {})
        aa["authority"] = "silence_locked"
        aa["nativeAudio"] = "disabled"
        aa["generateAudio"] = False
        aa["reason"] = aa.get("reason") or "expectedSpeech_NONE_or_empty_silence_locked_manifest"
        request.providerOptions["audioAuthority"] = aa
        request.providerOptions["generate_audio"] = False
        request.providerOptions["audio_generation"] = False
    from .r2v import attach_canonical_r2v
    from .direct_reference import attach_direct_reference_payload
    from ...db import SessionLocal as _SessionLocal

    if direct_references is not None:
        attach_direct_reference_payload(request, direct_references)
    _db = _SessionLocal()
    try:
        attach_canonical_r2v(request, batch, caps, db=_db)
        # H3: a reference sheet stays the whole Library file on Load Image.
        # A front or side still is replaced by the approved sheet when one exists.
        from .h3_front_identity import apply_h3_front_identity_to_request
        from .r2v import H3_MECHANISM, mechanism_for_generator

        product = str(request.generatorId or caps.id or "")
        if mechanism_for_generator(product) == H3_MECHANISM or product.startswith("minimax-h3"):
            # Advisory annotations only -- never fail Timed Prompt delivery if the
            # local DB schema/session cannot resolve Front/CRS metadata.
            try:
                apply_h3_front_identity_to_request(_db, request)
            except Exception:
                pass
    finally:
        _db.close()
    return request


def _batch_silence_locked(batch: BatchBlock, delivered_prompt: str | None = None) -> bool:
    """True when Dialogue Authority locks silence (no native H3 speech audio).

    Silence-locked only when expectedSpeech=NONE is *authoritative* (explicit
    NONE, or an empty compiled manifest that does not imply speech in Prompt
    text). Missing manifest alone must NOT mute -- that was silencing required
    character voice when screenplay dialogue failed to parse.

    Do not use Omni inference.
    """
    try:
        from app.codirector.dialogue_authority import (
            EXPECTED_SPEECH_NONE,
            get_manifest_from_batch,
            resolve_expected_speech,
        )
    except Exception:
        # Import failure: only silence if speechWindows explicitly declare none.
        windows = getattr(batch, "speechWindows", None) or []
        if windows and all(
            isinstance(w, dict) and str(w.get("speechKind") or "").lower() in {"none", "silent", ""}
            for w in windows
        ):
            return True
        return False

    manifest = get_manifest_from_batch(batch)
    if manifest is None:
        windows = getattr(batch, "speechWindows", None) or []
        if windows and all(
            isinstance(w, dict) and str(w.get("speechKind") or "").lower() in {"none", "silent", ""}
            for w in windows
        ):
            return True
        # Missing manifest is NOT silence-locked (owner 2026-09-20): accidental
        # empty authority must not disable required H3 native audio / voices.
        return False

    expected = resolve_expected_speech(
        lines=list(manifest.get("lines") or []),
        allow_adlibs=bool(manifest.get("allowAdLibs")),
        explicit=manifest.get("expectedSpeech"),
    )
    if expected != EXPECTED_SPEECH_NONE:
        return False
    # Ambience-on / speech-off: still speech-locked for QC, but NOT full mute.
    if _batch_allow_non_speech_audio(batch):
        return False
    # Parser-miss guard: Prompt clearly has dialogue but manifest lines empty.
    # A later window can be stored as a hollow [CONTINUATION] stub while the
    # delivered prompt carries that window's slice of the spoken script.
    if _batch_prompt_implies_speech(batch) or _text_implies_speech(delivered_prompt or ""):
        return False
    return True


def _text_implies_speech(blob: str) -> bool:
    """True when text looks like dialogue or screenplay speech."""
    if not blob:
        return False
    if '"' in blob or "\u201c" in blob or "\u201d" in blob:
        return True
    if re.search(r"\b(says|said|asks|asked|whispers|shouts|yells)\b", blob, re.I):
        return True
    # Screenplay cue: short ALL-CAPS line followed by a non-caps spoken line
    lines = blob.replace("\r\n", "\n").split("\n")
    for idx, line in enumerate(lines[:-1]):
        s = line.strip()
        if not s or len(s) > 48:
            continue
        if not s.isupper():
            continue
        if s.startswith("INT.") or s.startswith("EXT."):
            continue
        nxt = lines[idx + 1].strip()
        if nxt and not nxt.isupper() and not nxt.startswith("("):
            return True
    return False


def _batch_prompt_implies_speech(batch: BatchBlock) -> bool:
    """True when Timed Prompt text looks like dialogue / screenplay speech.

    Used to refuse silence_locked when cue extraction missed screenplay
    formatting (NAME then spoken line) or quotes -- missing metadata must not
    mute required character voice.
    """
    texts: list[str] = []
    for seg in getattr(batch, "promptSegments", None) or []:
        t = str(getattr(seg, "text", None) or getattr(seg, "promptText", None) or "").strip()
        if t:
            texts.append(t)
        d = str(getattr(seg, "dialogue", None) or "").strip()
        if d:
            return True
    return _text_implies_speech("\n".join(texts))




def _batch_allow_non_speech_audio(batch: BatchBlock) -> bool:
    """True when speech is locked off but non-speech / ambience audio is allowed.

    Brad ambience-on/speech-off: expectedSpeech=NONE (empty speech authority) but
    generateAudio may be true. Distinct from silence_locked full mute / path-b.

    Read order: dialogueManifest fields, then batch.references kind=audioAuthority
    (Pydantic DialogueManifest may strip unknown keys on save -- refs are durable).
    """
    try:
        from app.codirector.dialogue_authority import get_manifest_from_batch
    except Exception:
        get_manifest_from_batch = None  # type: ignore

    manifest: dict = {}
    if get_manifest_from_batch is not None:
        raw = get_manifest_from_batch(batch)
        if isinstance(raw, dict):
            manifest = raw
    # Also inspect raw dialogueManifest dict (may carry extras get_manifest filters)
    direct = getattr(batch, "dialogueManifest", None)
    if isinstance(direct, dict):
        for k in ("allowNonSpeechAudio", "allow_non_speech_audio", "audioPolicy", "audioAuthority"):
            if k in direct and k not in manifest:
                manifest[k] = direct[k]

    if bool(manifest.get("allowNonSpeechAudio") or manifest.get("allow_non_speech_audio")):
        return True
    aa = manifest.get("audioAuthority") if isinstance(manifest.get("audioAuthority"), dict) else {}
    auth = str(aa.get("authority") or manifest.get("audioPolicy") or "").strip().lower()
    if auth in {"ambience_speech_off", "ambience_only", "ambience-on-speech-off"}:
        return True

    for r in getattr(batch, "references", None) or []:
        if not isinstance(r, dict):
            continue
        kind = str(r.get("kind") or "").strip().lower()
        role = str(r.get("role") or "").strip().lower()
        if kind not in {"audioauthority", "audio_authority"} and role not in {"audioauthority", "audio_authority"}:
            # also accept explicit authority field without kind
            if str(r.get("authority") or "").strip().lower() not in {
                "ambience_speech_off", "ambience_only", "ambience-on-speech-off"
            } and not r.get("allowNonSpeechAudio") and not r.get("allow_non_speech_audio"):
                continue
        if bool(r.get("allowNonSpeechAudio") or r.get("allow_non_speech_audio")):
            return True
        rauth = str(r.get("authority") or r.get("audioPolicy") or "").strip().lower()
        if rauth in {"ambience_speech_off", "ambience_only", "ambience-on-speech-off"}:
            return True
    return False


def _resolve_audio_authority(
    project_id: str,
    scene_id: str,
    batch: BatchBlock,
    caps: VideoGeneratorCapabilities,
) -> dict[str, Any]:
    """Determine who owns the audio for this generation.

    Authority precedence:
    1. Lip Sync / Dialogue Authority -- if Timeline has active lip sync tracks,
       Timeline owns the dialogue/voice path.
    2. Explicit Timeline Audio / SFX / Music -- if creator placed explicit
       audio clips, SFX clips, or music, Timeline uses those tracks.
    3. No Explicit Audio Tracks -- USE GENERATOR-NATIVE AUDIO (default).

    An empty audio track lane is NOT an instruction for silence. It means
    "Let the video generator supply its own audio."
    """
    # Check if the generator supports native audio at all.
    supports_native = bool(getattr(caps, "audio_generation", False))

    # Check for explicit Timeline audio (batch-level).
    has_audio_clips = bool(getattr(batch, "audioClips", None))
    has_sfx_clips = bool(getattr(batch, "sfxClips", None))

    # Check for lip sync tracks (scene-level, via DB).
    has_lip_sync = False
    try:
        from ...db import SessionLocal, Scene

        db = SessionLocal()
        try:
            scene = db.get(Scene, scene_id)
            if scene and getattr(scene, "lipsync_audio_asset_id", None):
                has_lip_sync = True
        finally:
            db.close()
    except Exception:
        pass

    if has_lip_sync:
        return {
            "authority": "timeline",
            "dialogue": "lip_sync",
            "nativeAudio": "preserved_if_supported",
            "generateAudio": False,  # Timeline owns dialogue; generator may still produce ambient
        }
    if has_audio_clips or has_sfx_clips:
        return {
            "authority": "timeline",
            "nativeAudio": "mixed",
            "generateAudio": False,  # Timeline owns audio; generator may still produce ambient
        }
    # Ambience-on / speech-off: empty speech authority, non-speech native audio ON.
    if _batch_allow_non_speech_audio(batch):
        return {
            "authority": "ambience_speech_off",
            "dialogue": "speech_locked_empty",
            "nativeAudio": "enabled" if supports_native else "unsupported",
            "generateAudio": bool(supports_native),
            "reason": "allowNonSpeechAudio_expectedSpeech_NONE",
        }

    # Silence-locked Dialogue Authority: never ask H3 for native audio.
    if _batch_silence_locked(batch):
        return {
            "authority": "silence_locked",
            "dialogue": "manifest_locked_script",
            "nativeAudio": "disabled",
            "generateAudio": False,
            "reason": "expectedSpeech_NONE_or_empty_silence_locked_manifest",
        }

    # No explicit audio -- use generator-native audio by default.
    return {
        "authority": "generator_native",
        "nativeAudio": "enabled" if supports_native else "unsupported",
        "generateAudio": supports_native,  # Let the generator produce its own audio
    }


def _compile_generator_knowledge(
    *,
    generator_id: str,
    prompt: str,
    negative: str | None,
    mode: str,
    start_image: str | None,
    reference_ids: list[str],
    batch: BatchBlock,
    duration: float,
) -> dict[str, Any]:
    """Apply the generator knowledge compiler on the W46 generate path.

    If the profile is unavailable, keep the authored prompt. Never empty it.
    """
    try:
        from ...codirector.generator_knowledge.compiler import compile_for_generator
        from ...codirector.generator_knowledge.resolver import try_resolve_profile
        from ...codirector.model_intelligence.schemas import NormalizedGenerationIntent

        profile, _err = try_resolve_profile(generator_id)
        image_slots = dict(getattr(getattr(profile, "capability", None), "imageSlots", None) or {})
        subjects = _real_minimax_slots(batch, image_slots)
        intent = NormalizedGenerationIntent(
            userPrompt=prompt,
            negativePromptHint=negative or "",
            mode=mode,
            mediaType="video",
            durationSec=duration,
            hasSourceImage=bool(start_image),
            referenceCount=len(reference_ids),
            subjects=subjects,
        )
        result = compile_for_generator(generator_id, intent)
        compiled = str(result.compiledPrompt or "").strip()
        if result.status != "ok" or not compiled:
            return {
                "status": result.status,
                "dialect": (result.parameters or {}).get("dialect"),
                "profileId": (result.parameters or {}).get("profileId"),
                "subjectTagsEmitted": False,
                "warnings": list(result.warnings or []),
            }
        return {
            "status": result.status,
            "compiledPrompt": compiled,
            "compiledNegative": str(result.negativePrompt or ""),
            "dialect": (result.parameters or {}).get("dialect"),
            "profileId": (result.parameters or {}).get("profileId"),
            "subjectTagsEmitted": bool((result.parameters or {}).get("subjectTagsEmitted")),
            "knowledgeLoaded": bool((result.parameters or {}).get("knowledgeLoaded")),
            "knowledgeSpecPath": (result.parameters or {}).get("knowledgeSpecPath"),
            "knowledgeFile": (result.parameters or {}).get("knowledgeFile"),
            "r2vDialect": (result.parameters or {}).get("r2vDialect"),
            "r2vContract": (result.parameters or {}).get("r2vContract"),
            "warnings": list(result.warnings or []),
        }
    except Exception as exc:
        return {"status": "GENERATOR_KNOWLEDGE_UNAVAILABLE", "reason": repr(exc), "subjectTagsEmitted": False}


def _real_minimax_slots(batch: BatchBlock, image_slots: dict[str, Any]) -> list[dict[str, Any]]:
    """Subject tags require a wired Route A ref_images slot plus entity + asset."""
    if str(image_slots.get("ref_images") or "").upper() != "WIRED":
        return []
    slots: list[dict[str, Any]] = []
    for ref in batch.references or []:
        if not isinstance(ref, dict):
            continue
        if ref.get("consumed") is False:
            continue
        asset_id = str(ref.get("assetId") or "").strip()
        entity_id = str(ref.get("identityId") or ref.get("entityId") or "").strip()
        if not asset_id or not entity_id:
            continue
        slots.append(
            {
                "entityId": entity_id,
                "assetId": asset_id,
                "routeASlot": "ref_images",
                "wired": True,
            }
        )
    return slots


def _is_alias_only(text: str) -> bool:
    import re

    return bool(re.fullmatch(r"\s*~?M\s*[1-5]\s*", text or "", re.I))


def _compile_movement_layers(project_id: str, batch: BatchBlock) -> dict[str, Any]:
    """Compile Spatial Map movement layers only when the creator bound them.

    Creator Spec Fidelity: a fresh Timed Prompt with Korri+Addex bindings must
    not inherit the project's active Spatial Map segment cast (e.g. Anadriya)
    just because a document exists. Require an explicit movementSegmentRef or a
    ~M alias in the Timed Prompt text. Never fall back to active_segment.
    """
    try:
        from ...spatial_map.movement_compile import (
            compile_generation_layers,
            layers_as_provider_text,
            parse_movement_alias,
        )
        from ...spatial_map import movement as movement_mod
        from ...spatial_map.service import list_documents
        from ...db import SessionLocal

        db = SessionLocal()
        try:
            docs = list_documents(db, project_id) or []
            if not docs:
                return {}
            document = docs[0]
            first = (batch.promptSegments or [None])[0]
            ref = getattr(first, "movementSegmentRef", None) if first is not None else None
            timed = getattr(first, "text", "") if first is not None else ""
            movement_mod.hydrate_movement_segments(document)

            segment = None
            if isinstance(ref, dict) and str(ref.get("id") or "").strip():
                segment = movement_mod.find_segment(document, str(ref["id"]))
            else:
                number = None
                if isinstance(ref, dict) and ref.get("segmentNumber"):
                    try:
                        number = int(ref["segmentNumber"])
                    except (TypeError, ValueError):
                        number = None
                if number is None:
                    number = parse_movement_alias(str(timed or ""))
                if number is not None:
                    segment = movement_mod.find_segment_by_number(document, number)

            if segment is None:
                # No creator-bound movement segment -- do not inject Spatial Map cast.
                return {}

            layers = compile_generation_layers(document, segment, timed_prompt=str(timed or ""))
            return {"layers": layers, "providerText": layers_as_provider_text(layers)}
        finally:
            db.close()
    except Exception:
        return {}


def _compile_pose_conditioning(
    project_id: str,
    batch: BatchBlock,
    caps: Any,
    *,
    continuity_strategy: str | None = None,
    temporal_rejected: bool = False,
) -> dict[str, Any]:
    """Attach persisted PoseCraft intended state. Never overwrites temporal continuation.

    Skip when continuityStrategy is none or temporal continuation was creator-rejected --
    otherwise a stale Adult Male / intended packet can still prefix the timed prompt.
    """
    if temporal_rejected:
        return {
            "applied": False,
            "reason": "TEMPORAL_CREATOR_REJECTED",
            "promptPrefix": "",
        }
    if str(continuity_strategy or "").strip().lower() == "none":
        return {
            "applied": False,
            "reason": "CONTINUITY_STRATEGY_NONE",
            "promptPrefix": "",
        }
    try:
        from ...codirector.pose_intelligence.compile import compile_pose_motion_conditioning
        from ...codirector.pose_intelligence.persist import load_packet
        from ...db import SessionLocal

        extra = {}
        for ref in batch.references or []:
            if isinstance(ref, dict) and ref.get("poseWorldStatePacketId"):
                extra = ref
                break
        db = SessionLocal()
        try:
            packet = load_packet(db, project_id)
        finally:
            db.close()
        compiled = compile_pose_motion_conditioning(
            packet,
            supports_prompt_continuation=bool(getattr(caps, "supportsPromptContinuation", True)),
        )
        if extra.get("poseWorldStatePacketId"):
            compiled["sourcePosePacketId"] = extra.get("poseWorldStatePacketId")
        return compiled
    except Exception:
        return {"applied": False, "reason": "POSE_INTELLIGENCE_UNAVAILABLE", "promptPrefix": ""}
