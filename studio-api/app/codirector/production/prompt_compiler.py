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
    total = max(float(spec.duration_seconds or 10.0), 1.0)
    count = max(int(batch_count or 1), 1)
    per = total / count
    return round(batch_index * per, 2), round((batch_index + 1) * per, 2)


def _beats_in_window(intent: DirectorSceneIntent, start: float, end: float) -> list[int]:
    """Beat indices whose timed window intersects [start, end)."""
    if not intent.timed_beats or not intent.scene_beats:
        return [beat.index for beat in intent.scene_beats]
    picked: list[int] = []
    for beat in intent.scene_beats:
        if beat.index >= len(intent.timed_beats):
            picked.append(beat.index)
            continue
        timed = intent.timed_beats[beat.index]
        if timed.start_sec < end and timed.end_sec > start:
            picked.append(beat.index)
    return picked


def _scoped_action(intent: DirectorSceneIntent, beat_ids: list[int] | None) -> str:
    """ACTION synthesized from the full intent or a beat subset (batch window)."""
    if beat_ids is None:
        return _action_text(intent)
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
            beat_ids = _beats_in_window(intent, start, end)
            action = _scoped_action(intent, beat_ids)
            window_note = f"This segment covers story seconds {start:g}–{end:g} of the scene."
        else:
            action = _action_text(intent)
            window_note = ""

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

        mood_bit = f" Mood: {intent.mood}." if intent.mood else ""
        sections = {
            "shot": (
                f"SHOT\n{cinematic_cap(shot)} in {framing} framing.{mood_bit} "
                f"Camera: {movement}, keeping bound subjects and the environment as readable spatial anchors."
            ),
            "environment": env_line or "ENVIRONMENT\nUse the bound place reference as location authority.",
            "subjects": "SUBJECTS\n" + ("\n".join(subject_lines) if subject_lines else "Preserve bound reference appearance."),
            "spatial": "SPATIAL RELATIONSHIPS\n" + ("\n".join(spatial_lines) if spatial_lines else "Respect true physical scale of every bound subject."),
            "action": f"ACTION\n{window_note + chr(10) if window_note else ''}{action}",
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
        for ref in references:
            tag = (ref.canonical_tag or "").strip()
            if not tag:
                continue
            for variant in suffixed_tag_variants(tag):
                if variant in prompt:
                    prompt = prompt.replace(variant, tag)
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
    def compile(self, spec: SceneProductionSpec, references: list[ResolvedReference]) -> str:
        intent = _ensure_intent(spec, references)
        action = strip_instruction_copy(intent.action_text or "")
        names = ", ".join(item.display_name for item in references if item.status == "found")
        if action:
            return f"{action}\n\nBound references: {names}".strip()
        return f"{spec.scene_intent}\n\nBound references: {names}".strip()


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


def compile_batch_prompts(
    spec: SceneProductionSpec,
    references: list[ResolvedReference],
) -> list[str]:
    """One compiled prompt per Timeline batch. Single-batch scenes → one prompt."""
    count = max(int(spec.batch_count or 1), 1)
    compiler = prompt_compiler_for(spec.generator_id)
    if count <= 1 or not isinstance(compiler, MiniMaxH3PromptCompiler):
        return [compiler.compile(spec, references)]
    return [
        compiler.compile_batch(spec, references, batch_index=index, batch_count=count)
        for index in range(count)
    ]
