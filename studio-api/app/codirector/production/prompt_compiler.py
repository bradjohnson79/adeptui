"""Generator-specific prompt compilers. Layer C is synthesized from Layer B only.

MiniMax H3 uses the live knowledge markdown for capability guidance, but the
prompt body is compiled from `DirectorSceneIntent` — never from the creator's
raw instruction and never from generator-specific scene templates.
"""

from __future__ import annotations

import re
from typing import Protocol

from .canonical_tags import suffixed_tag_variants
from .contracts import DirectorSceneIntent, ResolvedReference, SceneProductionSpec
from .errors import PromptCompileError
from .instruction_copy import contains_instruction_copy, strip_instruction_copy
from .scene_breakdown import build_director_scene_intent, synthesize_cinematic_action

_SECTION_RE = re.compile(r"^(SHOT|ENVIRONMENT|SUBJECTS|SPATIAL RELATIONSHIPS|ACTION|MOTION|CAMERA|CONTINUITY / REFERENCE PRESERVATION|NEGATIVE / EXCLUSION CONSTRAINTS)\s*$")

_RUNTIME_TOKEN_RE = re.compile(
    r"\b(?:\d+(?:\.\d+)?\s*-?\s*seconds?\b|\d{1,2}\s*:\s*\d{1,2}\b|megapixels?\b|\b\d+(?:\.\d+)?\s*mp\b|\b\d+\s+batches?\b|"
    r"\bminimax\b|\bh3\b|\bltx\b|\bseedance\b|\bframe\s+ratio\b|\bsingle\s+batch\b|\bruntime\s+of\b)",
    re.I,
)

_META_SETTINGS_LINE_RE = re.compile(
    r"\b(?:runtime|execution)\s+settings?\b"
    r"|\bno\s+(?:generator\s+names?|aspect\s+ratios?|batch\s+counts?|megapixels?|durations?|runtime)\b"
    r"|\bignore\s+(?:the\s+)?(?:runtime|execution|generator|batch|aspect)\b",
    re.I,
)


def _clean_constraint_line(line: str) -> str:
    """Constraint sections carry cinematic prohibitions only.

    Meta-instructions about runtime/execution settings ("Ignore runtime
    settings (20 seconds, 2 batches, …)") are dropped outright — runtime
    metadata lives in execution settings, never in prompt prose. Residual
    runtime tokens are stripped from surviving lines; degenerate fragments
    ("No.") are discarded.
    """
    text = (line or "").strip()
    if not text or _META_SETTINGS_LINE_RE.search(text):
        return ""
    text = _RUNTIME_TOKEN_RE.sub("", text)
    text = re.sub(r"\s{2,}", " ", text).strip(" ,;:-")
    text = re.sub(r"\(\s*\)", "", text).strip(" ,;:-")
    if re.fullmatch(r"(?:no|not|never)\.?", text, re.I):
        return ""
    if len(text) < 4 or not re.search(r"[a-z]", text, re.I):
        return ""
    return text

_IMAGE_TOKEN_RE = re.compile(r"\bImage\s*\d+\b", re.I)
_FROM_IMAGE_TOKEN_RE = re.compile(r"\s*\bfrom\s+Image\s*\d+\b", re.I)

# Leading discourse markers/adverbs are staging flavour, not content — two
# sentences differing only by one of these stage the same event.
_ACTION_LEADING_MARKER_RE = re.compile(
    r"^(?:suddenly|slowly|then|next|finally|meanwhile|afterwards?|gradually|"
    r"abruptly|quietly|quickly|immediately|instantly)[,\s]+",
    re.I,
)


def _dedupe_action_sentences(action: str) -> str:
    """No sentence may be staged twice inside one ACTION block.

    Beats are whole-description deduped upstream, but a merged beat can still
    LEAD with a sentence another beat states verbatim ("A concentrated red
    energy beam blasts … door. Hot fragments …") — the compiled prose then
    stages the event twice (live Scene 3 defect, peer round-7). Drop later
    duplicates after normalization (leading discourse markers, case,
    whitespace); first occurrence wins. Sentences are compared per ACTION
    block (each batch window dedupes independently); separators are
    preserved. Very short sentences (<= 12 normalized chars, e.g. "Silence.")
    are exempt, matching the E2E duplicate guard's tolerance.
    """
    seen: set[str] = set()
    out: list[str] = []
    pieces = re.split(r"(?<=[.!?])(\s+)", action or "")
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        separator = pieces[index + 1] if index + 1 < len(pieces) else ""
        key = _ACTION_LEADING_MARKER_RE.sub("", sentence.strip().lower())
        key = re.sub(r"\s+", " ", key).strip(" .")
        if key and len(key) > 12 and key in seen:
            continue  # drop the duplicate sentence and its separator
        seen.add(key)
        out.append(sentence)
        out.append(separator)
    return "".join(out).strip()


def _sanitize_image_tokens(line: str, references: list[ResolvedReference]) -> str:
    """Rewrite creator-prose picture ordinals ("from Image 1", "Image 2") to
    canonical identity.

    Canonical Tag Law: prompt-facing identity is the canonical tag only —
    internal reference-image ordinals never leak into compiled prompt text.
    When the line names a bound asset, the tag is attached in place of the
    ordinal; otherwise the dangling "from Image N" tail is dropped.
    """
    if not _IMAGE_TOKEN_RE.search(line or ""):
        return line
    lowered = line.lower()
    tags: list[str] = []
    for ref in references:
        tag = (ref.canonical_tag or "").strip()
        if not tag:
            continue
        name = (ref.display_name or ref.query or "").strip().lower()
        needles = {name} if name else set()
        head = name.split()[0] if name else ""
        if len(head) > 3:
            needles.add(head)
        if any(needle and needle in lowered for needle in needles) and tag not in tags:
            tags.append(tag)
    cleaned = _FROM_IMAGE_TOKEN_RE.sub("", line)
    cleaned = _IMAGE_TOKEN_RE.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    had_period = cleaned.endswith(".")
    cleaned = cleaned.rstrip(".").rstrip()
    if not cleaned:
        return ""
    if tags:
        cleaned = f"{cleaned} ({', '.join(tags)})"
    if had_period:
        cleaned += "."
    return cleaned


class GeneratorPromptCompiler(Protocol):
    def compile(
        self,
        spec: SceneProductionSpec,
        references: list[ResolvedReference],
    ) -> str: ...

    def compile_batch(
        self,
        spec: SceneProductionSpec,
        references: list[ResolvedReference],
        *,
        batch_index: int,
        batch_count: int,
    ) -> str: ...



def _verified_continuity_lines(spec: SceneProductionSpec, batch_index: int) -> list[str]:
    """Read VerifiedContinuityMemory for Batch N-1 (same Take/revision only)."""
    if batch_index <= 0:
        return []
    take_id = str(getattr(spec, "take_id", "") or "").strip()
    revision = str(getattr(spec, "scene_revision", "") or "").strip()
    project_id = str(getattr(spec, "project_id", "") or "").strip()
    scene_id = str(getattr(spec, "scene_id", "") or "").strip()
    if not (project_id and scene_id and take_id and revision):
        return []
    try:
        from ..verified_continuity_memory import (
            continuity_refine_lines,
            read_verified_continuity,
        )
    except Exception:
        return []
    prior = read_verified_continuity(
        project_id=project_id,
        scene_id=scene_id,
        take_id=take_id,
        revision=revision,
        batch_index=batch_index - 1,
    )
    return continuity_refine_lines(prior)


def _locked_dialogue_lines_for_batch(spec: SceneProductionSpec, batch_index: int) -> list[str]:
    """Prefer locked Dialogue Manifest window lines — Omni never supplies these."""
    manif = getattr(spec, "dialogue_manifest", None)
    if not isinstance(manif, dict):
        return []
    lines = manif.get("lines") or []
    out: list[str] = []
    for line in lines:
        if not isinstance(line, dict):
            continue
        # Optional per-batch filter when batchIndex present on line
        bi = line.get("batchIndex")
        if bi is not None and int(bi) != int(batch_index):
            continue
        speaker = str(line.get("speakerName") or line.get("speaker") or "").strip()
        text = str(line.get("text") or "").strip()
        if not text:
            continue
        out.append(f'{speaker}: "{text}"' if speaker else text)
    return out


def extract_prompt_section(prompt: str, heading: str) -> str:
    lines = (prompt or "").splitlines()
    capturing = False
    collected: list[str] = []
    wanted = heading.strip().upper()
    for line in lines:
        token = line.strip().upper()
        if _SECTION_RE.match(line.strip()):
            if capturing:
                break
            capturing = token == wanted or token.startswith(wanted)
            continue
        if capturing:
            collected.append(line)
    return "\n".join(collected).strip()


def _found(references: list[ResolvedReference], asset_type: str) -> list[ResolvedReference]:
    return [item for item in references if item.status == "found" and item.asset_type == asset_type]


def _knowledge_excerpt(generator_id: str) -> str:
    from ..knowledgebase.video_generators import load_video_generator_knowledge

    kb = load_video_generator_knowledge(generator_id)
    if not kb.loaded:
        return ""
    return kb.spec_text


def _ensure_intent(spec: SceneProductionSpec, references: list[ResolvedReference]) -> DirectorSceneIntent:
    """Compile-time safety net. Understanding with LLM happens in the orchestrator;
    the compile path is deterministic Layer B → Layer C only."""
    if spec.director_intent is not None and spec.director_intent.action_text.strip():
        return spec.director_intent
    intent = build_director_scene_intent(spec, references, allow_llm=False)
    spec.director_intent = intent
    if not spec.scene_intent or spec.scene_intent == spec.source_user_prompt:
        spec.scene_intent = intent.opening_state or intent.action_text[:240]
    return intent


def _action_text(intent: DirectorSceneIntent) -> str:
    action = strip_instruction_copy(intent.action_text or "")
    if contains_instruction_copy(action):
        action = strip_instruction_copy(action)
    if contains_instruction_copy(action) or not action:
        raise PromptCompileError("Cinematic ACTION still contained user-request copy.")
    if _RUNTIME_TOKEN_RE.search(action):
        action = _RUNTIME_TOKEN_RE.sub("", action)
        action = re.sub(r"\s{2,}", " ", action).strip()
    if not action:
        raise PromptCompileError("Cinematic ACTION was empty after runtime-metadata stripping.")
    return _dedupe_action_sentences(action)


def _batch_window(spec: SceneProductionSpec, batch_index: int, batch_count: int) -> tuple[float, float]:
    # OWNER-PROTECTED (Timeline Batch Architecture Guard). Windows come from
    # spec.batchWindows (capability-driven planner) — every batch prompts only
    # its own window, never the full scene recipe. 12B window-note wording
    # (en dashes, no "batch" in ACTION prose) is a pinned contract.
    """Temporal window for one batch, from the capability-driven plan.

    Prefers spec.batchWindows (planned by generator_capability against the
    generator's certified single-generation window). The even split remains
    only as the fallback for direct compiler callers that never ran the
    planner — and it must still fit the certified single-generation window:
    the fallback never fabricates an over-window batch (capability law).
    """
    windows = spec.batchWindows or []
    if len(windows) >= max(int(batch_count or 1), 1) and 0 <= batch_index < len(windows):
        w = windows[batch_index]
        return float(w.get("start", 0.0)), float(w.get("end", 0.0))
    total = max(float(spec.duration_seconds or 10.0), 1.0)
    count = max(int(batch_count or 1), 1)
    per = total / count
    if count > 1:
        from .generator_capability import GeneratorCapabilityError, resolve_max_single_generation_seconds

        try:
            max_window = resolve_max_single_generation_seconds(spec.generator_id)
        except (GeneratorCapabilityError, Exception) as exc:  # noqa: BLE001 — fail closed on any registry failure
            raise GeneratorCapabilityError(
                f"Batch windows are missing for a {count}-batch scene and the certified "
                f"single-generation window could not be resolved for {spec.generator_id!r} "
                f"({exc}) — run the capability planner before compiling batch prompts."
            ) from exc
        if per > max_window + 1e-6:
            raise GeneratorCapabilityError(
                f"Even-split fallback window {per:g}s exceeds the certified single-generation "
                f"window {max_window:g}s for {spec.generator_id!r} — run the capability planner "
                "before compiling batch prompts."
            )
    return round(batch_index * per, 2), round((batch_index + 1) * per, 2)


def _beats_in_window(
    intent: DirectorSceneIntent,
    spec: SceneProductionSpec,
    batch_index: int,
    batch_count: int,
) -> list[int]:
    """PRIMARY beat indices for this Execution Window (start-in-window).

    OVERLAP CARRY is handled separately via `_overlap_carry_for_window` —
    continue/in-progress wording only; NEVER re-fire the whole beat
    (Scene 3 / Sample F double-stage guard / Brad HARD LOCK).
    """
    return _project_window(intent, spec, batch_index, batch_count).primary_beat_indices


def _overlap_carry_for_window(
    intent: DirectorSceneIntent,
    spec: SceneProductionSpec,
    batch_index: int,
    batch_count: int,
) -> list[str]:
    """Continue/in-progress lines for beats that span into this window."""
    return list(_project_window(intent, spec, batch_index, batch_count).carry_lines)


def _project_window(
    intent: DirectorSceneIntent,
    spec: SceneProductionSpec,
    batch_index: int,
    batch_count: int,
):
    from .execution_windows import project_beats_two_tier

    count = max(int(batch_count or 1), 1)
    start, end = _batch_window(spec, batch_index, count)
    return project_beats_two_tier(
        scene_beats=list(intent.scene_beats or []),
        timed_beats=list(intent.timed_beats or []),
        window_start=start,
        window_end=end,
        scene_duration=float(spec.duration_seconds or 10.0),
        batch_index=batch_index,
        batch_count=count,
    )


def _scoped_action(
    intent: DirectorSceneIntent,
    spec: SceneProductionSpec,
    batch_count: int,
    batch_index: int,
) -> str:
    """ACTION synthesized from the full intent or this batch's staged beats.

    Beat allocation uses the batch's temporal window (capability plan when
    spec.batchWindows is populated). A beat belongs to exactly one batch — the
    one where it starts — so already-completed primary choreography never
    re-appears in a later batch's prompt (long-scene invariant).
    """
    if batch_count <= 1:
        return _action_text(intent)
    beat_ids = _beats_in_window(intent, spec, batch_index, batch_count)
    scoped = intent.model_copy(deep=True)
    scoped.scene_beats = [beat for beat in intent.scene_beats if beat.index in set(beat_ids)]
    scoped.dialogue = [
        line
        for line in intent.dialogue
        if line.beat_index is None or line.beat_index in set(beat_ids)
    ]
    # Reveal gates persist across batches while the gate event is still ahead
    # of (or inside) this window; once the reveal beat lies entirely before
    # the window, the gate is stale and is dropped from ACTION language.
    window_start = min(beat_ids) if beat_ids else 0
    scoped.reveals = [
        reveal
        for reveal in intent.reveals
        if reveal.hidden_until_beat is None or reveal.hidden_until_beat >= window_start
    ]
    action = strip_instruction_copy(synthesize_cinematic_action(scoped))
    # OVERLAP CARRY — continue/in-progress only; never re-fire PRIMARY beats.
    carry_lines = _overlap_carry_for_window(intent, spec, batch_index, batch_count)
    if carry_lines:
        action = (action + "\n" if action else "") + " ".join(carry_lines)

    if not action:
        action = _action_text(intent)
    return _dedupe_action_sentences(action)


class MiniMaxH3PromptCompiler:
    """Compile SceneSpec into MiniMax H3 R2V prose from DirectorSceneIntent, not user dump."""

    def compile(self, spec: SceneProductionSpec, references: list[ResolvedReference]) -> str:
        return self.compile_batch(spec, references, batch_index=0, batch_count=1)

    def compile_batch(
        self,
        spec: SceneProductionSpec,
        references: list[ResolvedReference],
        *,
        batch_index: int,
        batch_count: int,
    ) -> str:
        knowledge = _knowledge_excerpt(spec.generator_id or "minimax-h3")
        if not knowledge:
            raise PromptCompileError("MiniMax H3 knowledge could not be loaded.")

        intent = _ensure_intent(spec, references)
        envs = _found(references, "environment")
        props = _found(references, "prop")
        chars = _found(references, "character")

        env_line = ""
        if intent.environment.verified and intent.environment.tag:
            env_line = (
                f"ENVIRONMENT\n"
                f"{intent.environment.tag} is the place. "
                f"Preserve the approved {intent.environment.name} environment."
            )
        elif envs:
            env = envs[0]
            env_line = (
                f"ENVIRONMENT\n"
                f"{env.canonical_tag or env.display_name} is the place. "
                f"Preserve the approved {env.display_name} environment."
            )

        subject_lines: list[str] = []
        for subject in intent.subjects:
            if not subject.verified or not subject.tag:
                continue
            if (subject.asset_type or "") == "character":
                subject_lines.append(
                    f"{subject.tag} — preserve the approved character identity of {subject.name}. Do not redesign."
                )
            else:
                subject_lines.append(
                    f"{subject.tag} — preserve the approved appearance of {subject.name}. Do not redesign."
                )
        if not subject_lines:
            for prop in props:
                if prop.canonical_tag:
                    subject_lines.append(
                        f"{prop.canonical_tag} — preserve the approved appearance of {prop.display_name}."
                    )
            for char in chars:
                if char.canonical_tag:
                    subject_lines.append(
                        f"{char.canonical_tag} — preserve the approved character identity of {char.display_name}."
                    )

        spatial_lines = list(intent.spatial_rules)
        for rel in spec.scale_relationships:
            if rel.prompt_language and rel.prompt_language not in spatial_lines:
                spatial_lines.append(rel.prompt_language)

        plan = intent.camera_plan
        shot = plan.shot_type or intent.shot_type or spec.camera.shot_type or "cinematic"
        movement = plan.movement or spec.camera.movement or "controlled cinematic movement"
        framing = plan.framing or spec.camera.framing or "wide"
        target = plan.target

        if batch_count > 1:
            start, end = _batch_window(spec, batch_index, batch_count)
            beat_ids = _beats_in_window(intent, spec, batch_index, batch_count)
            action = _scoped_action(intent, spec, batch_count, batch_index)
        window_note = (
            f"Duration:\n"
            f"Seconds: {start:g}-{end:g}. This segment covers story seconds "
            f"{start:g}–{end:g} of the scene."
            + (
                "\nThis is the first part of the scene — the story continues after it. "
                "End mid-motion at a natural continuation point; do not compress the "
                "whole scene into this segment."
                if batch_index == 0
                else (
                    f"\nCONTINUATION\nThis segment continues directly from the final state of "
                    f"the previous segment (story seconds {start:g}–{end:g}). Do not restart the "
                    f"camera move, walk, or action from the beginning; advance the remaining "
                    f"scene beats only."
                )
            )
        )

        scoped_beats = (
            [b for b in intent.scene_beats if beat_ids is None or b.index in beat_ids]
            if batch_count > 1
            else list(intent.scene_beats)
        )
        motion_bits: list[str] = []
        for beat in scoped_beats:
            if beat.kind in {"approach", "exit", "transition"} or re.search(
                r"\b(?:walks?|advances?|steps?|runs?|crosses?|enters?|exits?|turns?|rises?|"
                r"drifts?|glides?|follows?|rotates?|spins?|accelerates?|decelerates?|charges?|"
                r"lunges?|falls?|collapses?|climbs?|descends?|approaches?)\b",
                beat.description,
                re.I,
            ):
                if beat.description not in motion_bits:
                    motion_bits.append(beat.description)
        motion = (
            " ".join(motion_bits[:3])
            or "Controlled, precise motion. Hold the end composition so every bound subject stays readable."
        )
        if intent.stealth_intent and intent.stealth_intent.lower() not in motion.lower():
            motion = f"{motion} {intent.stealth_intent}"

        camera_bits = [f"{shot}"]
        if movement:
            camera_bits.append(movement)
        if target:
            camera_bits.append(f"camera centered on {target}")
        if plan.evolution:
            camera_bits.append(plan.evolution)
        camera_line = "; ".join(bit for bit in camera_bits if bit)

        exclusions: list[str] = []
        for item in intent.exclusions:
            cleaned = _clean_constraint_line(item).rstrip(".")
            if cleaned and cleaned.lower() not in {e.lower() for e in exclusions}:
                exclusions.append(cleaned if cleaned[:1].isupper() else cleaned[:1].upper() + cleaned[1:])
        if intent.subtitle_policy == "none" and not any("subtitle" in e.lower() or "on-screen text" in e.lower() for e in exclusions):
            exclusions.append("No subtitles or on-screen text")
        exclusions.append("No unnecessary camera shake")
        exclusions.append("Do not emit decorative lowercase subject tags or reference-image tokens")
        # P6 QA: silent unless Dialogue Manifest authorizes lines for this batch.
        locked_dlg = _locked_dialogue_lines_for_batch(spec, batch_index)
        if not locked_dlg:
            for silence in (
                "MUTE / SILENT scene: the character does not speak; mouth closed; no lip movement for speech",
                "No spoken dialogue in any language (English or foreign)",
                "No gibberish, invented words, whispering, or mouthing",
                "Audio is ambience and footsteps only — no human voice",
            ):
                if not any(silence.lower() in e.lower() for e in exclusions):
                    exclusions.append(silence)
        exclusions = [e if e.endswith(".") else e + "." for e in exclusions]

        continuity_lines = [
            cleaned
            for cleaned in (
                _clean_constraint_line(sanitized)
                for sanitized in (
                    _sanitize_image_tokens(line, references) for line in intent.continuity_rules
                )
                if sanitized
            )
            if cleaned
        ]
        for reveal in intent.reveals:
            gate = (
                f"Do not reveal {reveal.subject} before {reveal.hidden_until.rstrip('.')}"
                if reveal.hidden_until
                else f"Keep {reveal.subject} hidden until the staged reveal"
            )
            if reveal.reveal_order:
                gate += "; reveal in order: " + " → ".join(reveal.reveal_order)
            continuity_lines.append(gate + ".")
        if not continuity_lines:
            continuity_lines = [
                "Bound pictures are identity and place authority.",
                "Do not invent replacement subjects or a different place.",
            ]
        # OVERLAP CARRY into CONTINUITY (never re-fire beat).
        for cline in _overlap_carry_for_window(intent, spec, batch_index, batch_count):
            if cline and cline not in continuity_lines:
                continuity_lines.append(cline)
        # WAVE 4: VerifiedContinuityMemory refine for Batch N+1 (same Take/revision).
        for vline in _verified_continuity_lines(spec, batch_index):
            if vline and vline not in continuity_lines:
                continuity_lines.append(vline)
        if batch_index > 0:
            light = (
                "Lighting continuity: same corridor practicals, exposure, and color temperature "
                "as the prior same-Take segment; no relight, no exposure flash at the cut."
            )
            if not any("Lighting continuity" in ln for ln in continuity_lines):
                continuity_lines.append(light)
        # WAVE 4: locked Dialogue Manifest lines only (never Omni transcript).
        locked_dlg = _locked_dialogue_lines_for_batch(spec, batch_index)
        if locked_dlg:
            continuity_lines.append(
                "Locked dialogue for this batch (authority — do not improvise): "
                + " | ".join(locked_dlg)
            )

        mood_bit = f" Mood: {intent.mood}." if intent.mood else ""
        # Framing may arrive as a noun ("wide") or a clause ("centered on the
        # door, then on Cade through the steam framing") — only noun forms
        # take the "in … framing" template; clauses are stated directly.
        framing_token = (framing or "").strip().rstrip(".")
        if framing_token and re.match(r"^[a-z]+(?:[\s-](?:shot|angle|view|up))?$", framing_token, re.I):
            framing_bit = f" in {framing_token} framing"
        elif framing_token:
            framing_bit = f", {framing_token}"
        else:
            framing_bit = ""
        sections = {
            "shot": (
                f"SHOT\n{cinematic_cap(shot)}{framing_bit}.{mood_bit} "
                f"Camera: {movement}, keeping bound subjects and the environment as readable spatial anchors."
            ),
            "environment": env_line or "ENVIRONMENT\nUse the bound place reference as location authority.",
            "subjects": "SUBJECTS\n" + ("\n".join(subject_lines) if subject_lines else "Preserve bound reference appearance."),
            "spatial": "SPATIAL RELATIONSHIPS\n" + ("\n".join(spatial_lines) if spatial_lines else "Respect true physical scale of every bound subject."),
            "action": (
                "ACTION\n"
                + (
                    (
                        "MUTE / SILENT: no spoken dialogue in any language; no foreign speech; "
                        "no gibberish; mouth closed; ambience and footsteps only — no human voice.\n"
                    )
                    if not locked_dlg
                    else ""
                )
                + (window_note + chr(10) if window_note else "")
                + action
            ),
            "camera": f"CAMERA\n{camera_line}.",
            "motion": f"MOTION\n{motion}",
            "continuity": "CONTINUITY / REFERENCE PRESERVATION\n" + "\n".join(continuity_lines),
            "exclusions": "NEGATIVE / EXCLUSION CONSTRAINTS\n" + " ".join(exclusions),
        }
        ordered = [
            sections["shot"],
            sections["environment"],
            sections["subjects"],
            sections["spatial"],
            sections["action"],
            sections["motion"],
            sections["camera"],
            sections["continuity"],
            sections["exclusions"],
        ]
        prompt = "\n\n".join(part for part in ordered if part.strip())
        # Suffix-drift rewrite: a drifted tag ("@Echo2") is rewritten to its
        # canonical form — but never by substring. "@Echo2" replaced inside
        # "@Echo20" corrupts it into "@Echo0", and "@Echo20" may BE another
        # reference's canonical tag. Boundary-anchored regex + canonical-tag
        # exclusion only.
        all_tags = {
            (ref.canonical_tag or "").strip() for ref in references
        } - {""}
        for ref in references:
            tag = (ref.canonical_tag or "").strip()
            if not tag:
                continue
            for variant in suffixed_tag_variants(tag):
                if variant in all_tags:
                    continue  # another reference's canonical tag — never rewrite
                prompt = re.sub(re.escape(variant) + r"(?![\w-])", tag, prompt)
        # Canonical Tag Law guarantee: no internal reference-image ordinals in
        # any section, regardless of which layer produced the text.
        if _IMAGE_TOKEN_RE.search(prompt):
            prompt = "\n\n".join(
                "\n".join(
                    _sanitize_image_tokens(line, references) for line in part.splitlines()
                )
                for part in prompt.split("\n\n")
            )
            prompt = re.sub(r"[ \t]{2,}", " ", prompt)
            prompt = re.sub(r"\n{3,}", "\n\n", prompt).strip()
        return prompt


def cinematic_cap(value: str) -> str:
    token = (value or "").strip()
    return token[:1].upper() + token[1:] if token else "Cinematic shot"


class GenericTimelinePromptCompiler:
    """Fallback compiler for generators without a dedicated section template.

    The Canonical Tag Law is generator-agnostic: prompt-facing identity is
    always the canonical tag, never a bare display name. Multi-batch scenes
    are windowed exactly like the H3 path — a two-batch request must never
    collapse into one unscoped full-scene prompt.
    """

    def compile(self, spec: SceneProductionSpec, references: list[ResolvedReference]) -> str:
        intent = _ensure_intent(spec, references)
        action = _dedupe_action_sentences(strip_instruction_copy(intent.action_text or ""))
        names = ", ".join(
            (item.canonical_tag or item.display_name) for item in references if item.status == "found"
        )
        if action:
            return f"{action}\n\nBound references: {names}".strip()
        return f"{spec.scene_intent}\n\nBound references: {names}".strip()

    def compile_batch(
        self,
        spec: SceneProductionSpec,
        references: list[ResolvedReference],
        *,
        batch_index: int,
        batch_count: int,
    ) -> str:
        intent = _ensure_intent(spec, references)
        beat_ids = _beats_in_window(intent, spec, batch_index, batch_count)
        action = _scoped_action(intent, spec, batch_count, batch_index)
        start, end = _batch_window(spec, batch_index, batch_count)
        window_note = (
            f"Duration:\nSeconds: {start:g}-{end:g}. "
            f"This segment covers story seconds {start:g}–{end:g} of the scene."
        )
        if batch_index > 0:
            window_note += (
                f"\nCONTINUATION\nThis segment continues directly from the final state of "
                f"the previous segment (story seconds {start:g}–{end:g}). Do not restart the camera "
                f"move, walk, or action from the beginning; advance the remaining scene beats only."
            )
        names = ", ".join(
            (item.canonical_tag or item.display_name) for item in references if item.status == "found"
        )
        return f"{window_note}\n{action}\n\nBound references: {names}".strip()


_COMPILERS: dict[str, GeneratorPromptCompiler] = {
    "minimax-h3": MiniMaxH3PromptCompiler(),
    "minimax-h3-local": MiniMaxH3PromptCompiler(),
    "minimax-h3-t2v-local": MiniMaxH3PromptCompiler(),
}


def prompt_compiler_for(generator_id: str) -> GeneratorPromptCompiler:
    token = (generator_id or "").strip().lower()
    if token in _COMPILERS:
        return _COMPILERS[token]
    if token.startswith("minimax-h3"):
        return MiniMaxH3PromptCompiler()
    return GenericTimelinePromptCompiler()


def compile_generator_prompt(spec: SceneProductionSpec, references: list[ResolvedReference]) -> str:
    compiler = prompt_compiler_for(spec.generator_id)
    return compiler.compile(spec, references)


_CROSS_BATCH_KEEP_RE = re.compile(
    r"\b(?:hidden|remains?|do not reveal|not yet visible|stays|keeps?|"
    r"continu|preserve|maintain|segment covers)\b",
    re.I,
)


def _action_sentence_key(sentence: str) -> str:
    key = _ACTION_LEADING_MARKER_RE.sub("", (sentence or "").strip().lower())
    return re.sub(r"\s+", " ", key).strip(" .")


def _replace_action_section(prompt: str, action_body: str) -> str:
    old = extract_prompt_section(prompt, "ACTION")
    if not old:
        return prompt
    return prompt.replace(f"ACTION\n{old}", f"ACTION\n{action_body}", 1)


def _dedupe_action_across_batches(prompts: list[str]) -> list[str]:
    """A discrete on-screen event is staged in exactly one batch ACTION.

    Reveal gates and continuity language persist across windows; event
    sentences that already appeared in an earlier batch are dropped from
    later ones (live Sample F kite-launch / Scene 3 steam, peer round-8).
    """
    seen: set[str] = set()
    out: list[str] = []
    for prompt in prompts:
        action = extract_prompt_section(prompt, "ACTION")
        if not action:
            out.append(prompt)
            continue
        kept: list[str] = []
        pieces = re.split(r"(?<=[.!?])(\s+)", action)
        for index in range(0, len(pieces), 2):
            sentence = pieces[index]
            separator = pieces[index + 1] if index + 1 < len(pieces) else ""
            key = _action_sentence_key(sentence)
            if key and len(key) > 12 and key in seen and not _CROSS_BATCH_KEEP_RE.search(sentence):
                continue
            if key and len(key) > 12 and not _CROSS_BATCH_KEEP_RE.search(sentence):
                seen.add(key)
            kept.append(sentence)
            kept.append(separator)
        out.append(_replace_action_section(prompt, "".join(kept).strip()))
    return out


def compile_batch_prompts(
    spec: SceneProductionSpec,
    references: list[ResolvedReference],
) -> list[str]:
    """One compiled prompt per Timeline batch. Single-batch scenes → one prompt."""
    count = max(int(spec.batch_count or 1), 1)
    compiler = prompt_compiler_for(spec.generator_id)
    if count <= 1:
        return [compiler.compile(spec, references)]
    prompts = [
        compiler.compile_batch(spec, references, batch_index=index, batch_count=count)
        for index in range(count)
    ]
    return _dedupe_action_across_batches(prompts)
